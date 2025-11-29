"""
串口发送模块
负责将键盘信号通过USB串口TTL发送
"""

import threading
import time
from protocol import encode_data

class UARTSender:
    def __init__(self, serial_port, shared_data):
        """
        初始化串口发送器
        Args:
            serial_port: 串口对象
            shared_data: 线程间共享的数据对象
        """
        self.serial_port = serial_port
        self.shared_data = shared_data
        self.running = False
        self.send_thread = None
        self.last_sent_data = None
        
    def start_sending(self):
        """开始发送数据"""
        if self.running:
            return
            
        self.running = True
        self.send_thread = threading.Thread(target=self._send_loop)
        self.send_thread.daemon = True
        self.send_thread.start()
        print("串口数据发送已启动")
        
    def stop_sending(self):
        """停止发送数据"""
        self.running = False
        if self.send_thread:
            self.send_thread.join(timeout=1.0)
        print("串口数据发送已停止")
        
    def _send_loop(self):
        """数据发送循环"""
        while self.running:
            try:
                if self.serial_port and self.serial_port.is_open:
                    # 编码数据包
                    packet = encode_data(self.shared_data)
                    
                    # 检查数据是否有变化
                    current_data = {
                        "main_switch": self.shared_data.main_switch,
                        "fan_speed": self.shared_data.fan_speed,
                        "servo_angles": self.shared_data.servo_angles.copy()
                    }
                    
                    # 只有当数据变化时才发送
                    if current_data != self.last_sent_data:
                        self.serial_port.write(packet)
                        self.last_sent_data = current_data
                        print(f"发送数据: 开关={current_data['main_switch']}, 风扇={current_data['fan_speed']}, 舵机={current_data['servo_angles']}")
                        
                # 控制发送频率
                time.sleep(0.02)  # 50Hz发送间隔 (20ms)
                
            except Exception as e:
                print(f"串口发送错误: {e}")
                break
                
    def get_last_sent_info(self):
        """获取最后发送的数据信息"""
        if self.last_sent_data:
            return f"开关:{self.last_sent_data['main_switch']} 风扇:{self.last_sent_data['fan_speed']} 舵机:{self.last_sent_data['servo_angles']}"
        else:
            return "无发送记录"
