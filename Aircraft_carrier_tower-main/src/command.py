import time
import threading
import os
import datetime
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
        
        # 新增日志相关属性
        self.log_file_path = "receive_log.txt"
        self.max_log_lines = 1000  # 最大日志行数
        self.log_enabled = True    # 是否启用日志
        
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
        
    def _write_to_log(self, message):
        """将消息写入日志文件"""
        if not self.log_enabled:
            return
        
        try:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"[{timestamp}] {message}\n"
        
            # 写入日志文件
            with open(self.log_file_path, 'a', encoding='utf-8') as f:
                f.write(log_entry)
            
            # 检查日志文件大小，如果过大则清理
            self._manage_log_size()
        
        except Exception as e:
            print(f"写入日志文件错误: {e}")

    def _manage_log_size(self):
        """管理日志文件大小，防止过大"""
        try:
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        
            # 如果超过最大行数，保留最新的部分
            if len(lines) > self.max_log_lines:
                with open(self.log_file_path, 'w', encoding='utf-8') as f:
                    f.writelines(lines[-self.max_log_lines:])
                
        except Exception as e:
            print(f"管理日志文件大小错误: {e}")

    def show_log(self, lines=20):
        """显示最近的日志内容"""
        try:
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
        
            # 显示最近的指定行数
            recent_lines = all_lines[-lines:] if lines > 0 else all_lines
            print(f"\n最近 {len(recent_lines)} 条接收数据:")
            print("-" * 60)
            for line in recent_lines:
                print(line.strip())
            print("-" * 60)
        
        except FileNotFoundError:
            print("日志文件不存在，尚未接收任何数据")
        except Exception as e:
            print(f"读取日志文件错误: {e}")

    def clear_log(self):
        """清空日志文件"""
        try:
            with open(self.log_file_path, 'w', encoding='utf-8') as f:
                f.write("")
            print("日志文件已清空")
        except Exception as e:
            print(f"清空日志文件错误: {e}")

    def show_log_info(self):
        """显示日志文件信息"""
        try:
            if os.path.exists(self.log_file_path):
                file_size = os.path.getsize(self.log_file_path)
                with open(self.log_file_path, 'r', encoding='utf-8') as f:
                    line_count = len(f.readlines())
                print(f"日志文件: {self.log_file_path}")
                print(f"文件大小: {file_size} 字节")
                print(f"数据行数: {line_count}")
                print(f"最大行数: {self.max_log_lines}")
            else:
                print("日志文件不存在")
        except Exception as e:
            print(f"获取日志文件信息错误: {e}")

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
        if not success:
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
                # 写入日志
                self._write_to_log(f"接收数据 [{self.receive_count}]: {parsed_data}") 
            else:
                # 显示原始数据（十六进制格式）
                hex_data = data.hex().upper()
                self._write_to_log(f"接收原始数据 [{self.receive_count}]: {hex_data}")
        except Exception as e:
            hex_data = data.hex().upper()
            self._write_to_log(f"数据解析错误: {e}")
            self._write_to_log(f"接收原始数据 [{self.receive_count}]: {hex_data}")
            
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
        print(f"  日志状态: {'启用' if self.log_enabled else '禁用'}")
        # 显示日志文件信息
        self.show_log_info()
        
    def cleanup(self):
        """清理资源"""
        self.stop_auto_send()
        self.disconnect_serial()
