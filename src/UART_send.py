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
        self._last_packet = None  # 最近一次成功编码的数据包
        
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
                    # 尝试编码当前控制数据
                    try:
                        packet = encode_data(self.shared_data)
                    except Exception as enc_err:
                        # 编码阶段出现异常时，优先复用上一帧数据，避免打断发送线程
                        print(f"编码控制数据出错，使用上一帧数据继续发送: {enc_err}")
                        packet = None

                    # 如果本帧编码失败或返回None，则尝试发送上一帧数据
                    if packet is None:
                        packet_to_send = self._last_packet
                        # 若还没有上一帧可用，则跳过本次发送
                        if packet_to_send is None:
                            time.sleep(0.02)
                            continue
                        # 不更新last_sent_data，表示这帧是重复发送
                    else:
                        packet_to_send = packet
                        # 获取当前数据状态快照
                        current_data = {
                            "main_switch": self.shared_data.main_switch,
                            "fan_speed": self.shared_data.fan_speed,
                            "servo_angles": self.shared_data.servo_angles.copy()
                        }
                        self.last_sent_data = current_data
                        self._last_packet = packet_to_send

                    # 无论数据是否变化，都按50Hz发送
                    self.serial_port.write(packet_to_send)
                        
                # 控制发送频率
                time.sleep(0.02)  # 50Hz发送间隔 (20ms)
                
            except Exception as e:
                # 串口底层错误属于硬件/连接问题，此时结束发送线程
                print(f"串口发送错误，发送线程已停止: {e}")
                self.running = False
                break
                
    def get_last_sent_info(self):
        """获取最后发送的数据信息"""
        if self.last_sent_data:
            return f"开关:{self.last_sent_data['main_switch']} 风扇:{self.last_sent_data['fan_speed']} 舵机:{self.last_sent_data['servo_angles']}"
        else:
            return "无发送记录"
            
    def get_hex_data(self):
        """获取当前数据的16进制格式"""
        try:
            # 编码数据包
            packet = encode_data(self.shared_data)
            # 转换为16进制字符串
            hex_string = ' '.join([f"{byte:02X}" for byte in packet])
            return hex_string
        except Exception as e:
            return f"编码错误: {e}"
