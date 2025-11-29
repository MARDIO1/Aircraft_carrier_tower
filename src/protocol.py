"""
串口通讯协议配置
定义地面站与航模之间的数据格式
"""

# 协议常量
START_BYTE = 0xAA
END_BYTE = 0xBB

# 数据结构定义
class ProtocolData:
    def __init__(self):
        self.main_switch = 0  # 总开关: 0或1
        self.fan_speed = 0    # 风扇转速: int16
        self.servo_angles = [0, 0, 0, 0]  # 4个舵机角度: int16数组

def encode_data(data):
    """
    将数据编码为串口发送格式
    格式: 0xAA + uint8[1]总开关 + int16[1]风扇转速 + int16[4]舵机角度 + 0xBB
    """
    packet = bytearray()
    
    # 起始字节
    packet.append(START_BYTE)
    
    # 总开关 (1字节)
    packet.append(data.main_switch & 0xFF)
    
    # 风扇转速 (2字节, 小端序)
    packet.extend(data.fan_speed.to_bytes(2, 'little', signed=True))
    
    # 4个舵机角度 (各2字节, 小端序)
    for angle in data.servo_angles:
        packet.extend(angle.to_bytes(2, 'little', signed=True))
    
    # 结束字节
    packet.append(END_BYTE)
    
    return packet

def decode_data(packet):
    """
    解码接收到的数据包
    """
    if len(packet) < 12:  # 最小包长度检查
        return None
    
    if packet[0] != START_BYTE or packet[-1] != END_BYTE:
        return None
    
    data = ProtocolData()
    
    # 解析总开关
    data.main_switch = packet[1]
    
    # 解析风扇转速
    data.fan_speed = int.from_bytes(packet[2:4], 'little', signed=True)
    
    # 解析4个舵机角度
    for i in range(4):
        start_idx = 4 + i * 2
        end_idx = start_idx + 2
        data.servo_angles[i] = int.from_bytes(packet[start_idx:end_idx], 'little', signed=True)
    
    return data
