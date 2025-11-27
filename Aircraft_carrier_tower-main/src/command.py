import time
import threading
from serial_thread import SerialThread
from protocol import Protocol


class CommandControl:
    """命令行航模控制器 - 管理串口连接和数据收发"""
    
    def __init__(self):
        """初始化控制器"""
        # 创建串口线程实例，用于多线程串口通信
        self.serial_thread = SerialThread()
        # 创建协议处理器实例，用于数据包编码解码
        self.protocol = Protocol()
        # 运行状态标志，控制主循环
        self.running = False
        # 自动发送间隔，单位秒
        self.send_interval = 0.1
        # 自动发送线程
        self.auto_send_thread = None
        # 自动发送运行标志（使用线程锁保护）
        self.auto_sending = False
        self.auto_send_lock = threading.Lock()
        # 当前控制数据：总开关、风扇转速、4个舵机角度
        # 根据协议要求，油门和舵机角度应该是float类型
        self.current_switch = 0
        self.current_fan_rpm = 0.0
        self.current_servo_angles = [0.0, 0.0, 0.0, 0.0]
        # 接收数据统计
        self.receive_count = 0
        
    def list_ports(self):
        """列出所有可用的串口端口"""
        # 调用串口线程获取端口列表
        ports = self.serial_thread.list_available_ports()
        # 检查是否有可用端口
        if not ports:
            print("未找到可用串口")
            return
            
        # 格式化显示端口信息
        print("可用串口列表:")
        print("-" * 60)
        for i, port in enumerate(ports):
            # 显示端口设备名、描述和硬件ID
            print(f"{i+1}. {port['device']} - {port['description']}")
            print(f"   硬件ID: {port['hwid']}")
        print("-" * 60)
        
    def connect_serial(self, port_name, baudrate=115200):
        """连接指定串口端口"""
        # 检查是否已连接
        if self.serial_thread.is_connected():
            print(f"已连接到 {port_name}，请先断开连接")
            return False
            
        # 尝试初始化串口连接
        print(f"正在连接串口 {port_name}，波特率 {baudrate}...")
        success = self.serial_thread.initialize_serial(port_name, baudrate)
        
        if success:
            # 启动串口通信线程
            self.serial_thread.start()
            # 设置接收数据回调函数
            self.serial_thread.add_receive_callback(self.handle_received_data)
            print(f"成功连接到 {port_name}")
            self.running = True
            return True
        else:
            print(f"连接 {port_name} 失败")
            return False
            
    def disconnect_serial(self):
        """断开串口连接"""
        # 停止自动发送
        self.stop_auto_send()
        # 停止串口线程
        self.serial_thread.stop()
        # 关闭串口连接
        self.serial_thread.close_serial()
        self.running = False
        print("串口连接已断开")
        
    def send_control_data(self, switch_cmd=None, fan_rpm=None, servo_angles=None):
        """发送控制数据到航模"""
        # 检查串口是否连接
        if not self.serial_thread.is_connected():
            print("错误：串口未连接")
            return False
            
        # 更新当前控制数据（如果提供了新值）
        if switch_cmd is not None:
            self.current_switch = switch_cmd
        if fan_rpm is not None:
            self.current_fan_rpm = fan_rpm
        if servo_angles is not None:
            # 确保舵机角度是4个值的列表
            if len(servo_angles) == 4:
                self.current_servo_angles = servo_angles
            else:
                print("错误：舵机角度必须是4个值的列表")
                return False
                
        # 使用协议处理器编码数据包
        try:
            packet = self.protocol.encode_up_frame(
                self.current_switch,
                self.current_fan_rpm,
                self.current_servo_angles
            )
        except Exception as e:
            print(f"数据包编码错误: {e}")
            return False
            
        # 通过串口线程发送数据
        success = self.serial_thread.send_data(packet)
        if success:
            print(f"发送数据: 开关={self.current_switch}, 油门={self.current_fan_rpm}, 舵机={self.current_servo_angles}")
        else:
            print("发送数据失败")
            
        return success
        
    def start_auto_send(self, interval=0.1):
        """启动自动发送模式，按指定间隔发送控制数据"""
        # 检查是否已连接
        if not self.serial_thread.is_connected():
            print("错误：串口未连接")
            return
            
        # 检查是否已在自动发送（使用线程锁保护）
        with self.auto_send_lock:
            if self.auto_sending:
                print("自动发送已在运行")
                return
                
            # 设置发送间隔和运行标志
            self.send_interval = interval
            self.auto_sending = True
        
        # 创建并启动自动发送线程
        self.auto_send_thread = threading.Thread(
            target=self._auto_send_worker,
            daemon=True
        )
        self.auto_send_thread.start()
        print(f"自动发送已启动，间隔: {interval}秒")
        
    def stop_auto_send(self):
        """停止自动发送模式"""
        with self.auto_send_lock:
            if self.auto_sending:
                self.auto_sending = False
                if self.auto_send_thread:
                    self.auto_send_thread.join(timeout=2.0)
                print("自动发送已停止")
            
    def _auto_send_worker(self):
        """自动发送工作线程"""
        while True:
            # 检查是否应该继续运行（使用线程锁保护）
            with self.auto_send_lock:
                should_continue = self.auto_sending and self.serial_thread.is_connected()
                if not should_continue:
                    break
            
            # 发送当前控制数据
            self.send_control_data()
            # 等待指定间隔
            time.sleep(self.send_interval)
            
    def handle_received_data(self, data):
        """处理从航模接收到的数据"""
        # 增加接收计数
        self.receive_count += 1
        
        # 使用协议处理器解析数据
        try:
            parsed_data = self.protocol.process_receive_data(data)
            if parsed_data:
                # 显示解析后的数据
                print(f"接收数据 [{self.receive_count}]: {parsed_data}")
            else:
                # 显示原始数据（十六进制格式）
                hex_data = data.hex().upper()
                print(f"接收原始数据 [{self.receive_count}]: {hex_data}")
        except Exception as e:
            # 显示解析错误和原始数据
            hex_data = data.hex().upper()
            print(f"数据解析错误: {e}")
            print(f"接收原始数据 [{self.receive_count}]: {hex_data}")
            
    def print_status(self):
        """打印当前状态信息"""
        print("\n当前状态:")
        print(f"  串口连接: {'已连接' if self.serial_thread.is_connected() else '未连接'}")
        print(f"  自动发送: {'运行中' if self.auto_sending else '停止'}")
        print(f"  发送间隔: {self.send_interval}秒")
        print(f"  控制数据:")
        print(f"    总开关: {self.current_switch}")
        print(f"    风扇转速: {self.current_fan_rpm}")
        print(f"    舵机角度: {self.current_servo_angles}")
        print(f"  接收数据包: {self.receive_count}个")
        
    def cleanup(self):
        """清理资源"""
        self.stop_auto_send()
        self.disconnect_serial()
