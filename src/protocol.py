"""
已懂
串口通讯协议配置
定义地面站与航模之间的数据格式
"""

import struct
import time

# 协议常量
START_BYTE = 0xAA  # 发送数据起始字节
END_BYTE = 0xBB    # 发送数据结束字节
RECV_START_BYTE = 0xCC  # 接收数据起始字节
RECV_END_BYTE = 0xDD    # 接收数据结束字节
PID_START_BYTE = 0xEE
PID_END_BYTE = 0xFF

# 数据结构定义
class ProtocolData:
    def __init__(self):
        # 发送数据（地面站→航模）
        self.main_switch = 0  # 总开关: 0或1
        self.fan_speed = 0    # 风扇转速: int16
        self.servo_angles = [0.0, 0.0, 0.0, 0.0]  # 4个舵机角度: float32数组
        
        #新增模式
        self.current_mode ='RUN' #有运行，停止和调参三种模式tuning
        self.tuning_active=False
        self.selected_pid=0 #这里对应的是pid类型索引种类目前是roll，pitch和右后左后左前右前
        self.selected_param=0 #当前选中的参数索引（0=kp,1=ki,2=kd,3=积分限幅，4=输出正限幅，5=积分负限幅

        self.pid_param=[
            #姿态坏：roll,pitch,yaw,  yaw还没实现
            [0.1, 0.0, 0.0, 0.0, 5.0, -5.0],  #roll
            [0.1, 0.0, 0.0, 0.0 ,5.0, -5.0],  #pitch
            #[1.0, 0.0, 0.0, 0.0 ,5.0,-5.0],  #yaw
            #舵面环:右后br，右前bl，左前fl，左后fr
            [9.0, 0.0, 0.0, 0.0, 35.0, -35.0],#br
            [9.0, 0.0, 0.0, 0.0, 35.0, -35.0],#bl
            [9.0, 0.0, 0.0, 0.0, 35.0, -35.0],#fl
            [9.0, 0.0, 0.0, 0.0, 35.0, -35.0],#fr
        ]

        #pid名称映射（用于显示）
        self.pid_name = [
            "姿态-横滚",   #0
            "姿态-俯仰",   #1
            "舵面-右后",   #2
            "舵面-左后",   #3
            "舵面-左前",   #4
            "舵面-右前",   #5
        ]
        #参数名称映射
        self.param_names = ["kp","ki","kd","积分限幅","正输出限幅","负输出限幅"]

        # 接收数据（航模→地面站）
        self.received_switch = 0  # 接收到的开关状态
        self.received_acc_x = 0.0  # 加速度 X (m/s²)
        self.received_acc_y = 0.0  # 加速度 Y (m/s²)
        self.received_acc_z = 0.0  # 加速度 Z (m/s²)
        self.received_gyro_x   = 0.0  # 陀螺仪 X (rad/s)
        self.received_gyro_y = 0.0  # 陀螺仪 Y (rad/s)
        self.received_gyro_z = 0.0  # 陀螺仪 Z (rad/s)
        self.received_angle_roll = 0.0   # 角度 Roll
        self.received_angle_pitch = 0.0  # 角度 Pitch
        self.received_angle_yaw = 0.0    # 角度 Yaw
        self.last_received_time = None  # 最后接收时间

def pid_encode_data(data):
    """
    格式：0xEE + uint8[1]种类索引 self.selected_pid +uint8[1]名称索引self.selected_param +float32[1]5x6中的一个value +0xFF
    """
    if data.selected_pid < 0 or data.selected_pid >= len(data.pid_param):
        print(f"错误：PID索引{data.selected_pid}超出范围(0-{len(data.pid_param)-1})")
        return None
    if data.selected_param < 0 or data.selected_param >= len(data.pid_param[0]):
        print(f"错误：参数索引{data.selected_param}超出范围(0-{len(data.pid_param[0])-1})")
        return None
    packet = bytearray()

    #帧头
    packet.append(PID_START_BYTE)

    #种类索引（1字节）0~1 姿态rpy 2~5舵面
    packet.append(data.selected_pid & 0xFF)
    
    #名称索引（1字节）
    packet.append(data.selected_param & 0xFF)

    #选中pid的6个参数中其中一个（4字节）
    param_value = data.pid_param[data.selected_pid][data.selected_param]
    packet.extend(struct.pack('<f',float(param_value)))
    
    #帧尾
    packet.append(PID_END_BYTE)

    return packet
            
def encode_data(data):
    """
    将数据编码为串口发送格式（地面站→航模）
    格式: 0xAA + uint8[1]总开关 + int16[1]风扇转速 + float32[4]舵机角度 + 0xBB
    """
    if data.tuning_active and data.current_mode == 'tuning':
        return pid_encode_data(data)
    else:
        packet = bytearray()
    
        # 起始字节
        packet.append(START_BYTE)
    
        # 总开关 (1字节)
        packet.append(data.main_switch & 0xFF)
    
        # 风扇转速 (2字节, 小端序)
        packet.extend(struct.pack('<h', data.fan_speed))  # '<h' = 有符号短整型
    
        # 4个舵机角度 (各4字节, 小端序, float32)
        for angle in data.servo_angles:
            packet.extend(struct.pack('<f', float(angle)))
    
        # 结束字节
        packet.append(END_BYTE)
    
        return packet
    

def decode_data(packet):
    """
    解码从航模接收到的数据包（航模→地面站）
    格式: 0xCC + uint8开关 + float[3]加速度 + float[3]陀螺仪 + float[3]角度 + 0xDD
    总长度: 39字节 (1+1+12+12+12+1)暂改为15字节
    """
    # 检查数据包长度
    if len(packet) != 15:
        return None
    
    # 检查起始和结束字节
    if packet[0] != RECV_START_BYTE or packet[-1] != RECV_END_BYTE:
        return None
    
    data = ProtocolData()
    
    try:
        # 解析开关状态 (第1字节)
        data.received_switch = packet[1]
        
        # 解析加速度数据 (3个float, 每个4字节，小端序)
        # 字节位置: 2-13 (12字节)
        #data.received_acc_x,data.received_acc_y,data.received_acc_z = struct.unpack('<fff', packet[2:14])
        
        
        # 解析陀螺仪数据 (3个float, 每个4字节，小端序)
        # 字节位置: 14-25 (12字节)
        #data.received_gyro_x,data.received_gyro_y,data.received_gyro_z = struct.unpack('<fff', packet[14:26])
       
        
        # 解析角度数据 (3个float, 每个4字节，小端序)
        # 字节位置: 26-37 (12字节)
        data.received_angle_roll,data.received_angle_pitch,data.received_angle_yaw = struct.unpack('<fff', packet[2:14])
      
        
        # 更新最后接收时间
        data.last_received_time = time.time()
        
        return data
        
    except Exception as e:
        print(f"数据解码错误: {e}")
        return None
