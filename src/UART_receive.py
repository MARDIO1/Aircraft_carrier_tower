"""
串口接收模块
负责从航模接收数据并解码
"""

import threading
import time
import struct
from protocol import decode_data

class UARTReceiver:
    def __init__(self, serial_port, shared_data):
        """
        初始化串口接收器
        Args:
            serial_port: 串口对象
            shared_data: 线程间共享的数据对象 (ProtocolData)
        """
        self.serial_port = serial_port
        self.shared_data = shared_data
        self.running = False
        self.receive_thread = None
        self.receive_buffer = bytearray()
        self.last_receive_time = None
        self.receive_count = 0
        self.error_count = 0
        
    def start_receiving(self):
        """开始接收数据"""
        if self.running:
            return
            
        self.running = True
        self.receive_thread = threading.Thread(target=self._receive_loop)
        self.receive_thread.daemon = True
        self.receive_thread.start()
        print("串口数据接收已启动")
        
    def stop_receiving(self):
        """停止接收数据"""
        self.running = False
        if self.receive_thread:
            self.receive_thread.join(timeout=1.0)
        print("串口数据接收已停止")
        
    def _receive_loop(self):
        """数据接收循环"""
        while self.running:
            try:
                if self.serial_port and self.serial_port.is_open:
                    # 读取可用数据
                    if self.serial_port.in_waiting > 0:
                        data = self.serial_port.read(self.serial_port.in_waiting)
                        self._process_received_data(data)
                
                # 控制接收频率
                time.sleep(0.01)  # 100Hz检查频率
                
            except Exception as e:
                print(f"串口接收错误: {e}")
                self.error_count += 1
                time.sleep(0.1)  # 出错后稍作等待
                
    def _process_received_data(self, data):
        """处理接收到的原始数据"""
        if not data:
            return
            
        # 将数据添加到缓冲区
        self.receive_buffer.extend(data)
        
        # 尝试从缓冲区中提取完整的数据包
        while len(self.receive_buffer) >= 15:  # 数据包最小长度
            # 查找起始字节 0xCC
            start_idx = -1
            for i in range(len(self.receive_buffer) - 14):  # 需要至少39字节
                if self.receive_buffer[i] == 0xCC:  # RECV_START_BYTE
                    start_idx = i
                    break
            
            if start_idx == -1:
                # 没有找到起始字节，清空缓冲区
                self.receive_buffer.clear()
                return
                
            # 检查是否有完整的数据包
            if start_idx + 15 > len(self.receive_buffer):
                # 数据包不完整，等待更多数据
                # 移除起始字节之前的数据
                if start_idx > 0:
                    self.receive_buffer = self.receive_buffer[start_idx:]
                return
                
            # 提取完整数据包
            packet = bytes(self.receive_buffer[start_idx:start_idx + 15])
            
            # 检查结束字节
            if packet[-1] == 0xDD:  # RECV_END_BYTE
                # 解码数据包
                decoded_data = decode_data(packet)
                if decoded_data:
                    self._update_shared_data(decoded_data)
                    self.receive_count += 1
                    self.last_receive_time = time.time()
                else:
                    self.error_count += 1
                
                # 从缓冲区中移除已处理的数据包
                self.receive_buffer = self.receive_buffer[start_idx + 15:]
            else:
                # 结束字节不匹配，跳过这个起始字节
                self.receive_buffer = self.receive_buffer[start_idx + 1:]
                
    def _update_shared_data(self, decoded_data):
        """将解码后的数据更新到共享数据结构中"""
        try:
            # 更新接收到的开关状态
            self.shared_data.received_switch = decoded_data.received_switch
            
            # 更新加速度数据
            
            # 更新陀螺仪数据
            #self.shared_data.received_gyro_x = decoded_data.received_gyro_x
           # self.shared_data.received_gyro_y = decoded_data.received_gyro_y
            #self.shared_data.received_gyro_z = decoded_data.received_gyro_z
            
            # 更新角度数据
            self.shared_data.received_angle_roll = decoded_data.received_angle_roll
            self.shared_data.received_angle_pitch = decoded_data.received_angle_pitch
            self.shared_data.received_angle_yaw = decoded_data.received_angle_yaw
            
            # 更新最后接收时间
            self.shared_data.last_received_time = decoded_data.last_received_time
            
        except Exception as e:
            print(f"更新共享数据错误: {e}")
            self.error_count += 1
            
    def get_receive_status(self):
        """获取接收状态信息"""
        status_time = "从未接收" if self.last_receive_time is None else f"{time.time() - self.last_receive_time:.1f}秒前"
        
        return {
            "running": self.running,
            "receive_count": self.receive_count,
            "error_count": self.error_count,
            "last_receive_time": status_time,
            "buffer_size": len(self.receive_buffer)
        }
        
    def get_received_data_summary(self):
        """获取接收数据的摘要信息"""
        return {
            "switch": self.shared_data.received_switch,
            #"acceleration": f"[{self.shared_data.received_acc_x:.2f}, {self.shared_data.received_acc_y:.2f}, {self.shared_data.received_acc_z:.2f}]",
           # "gyro": f"[{self.shared_data.received_gyro_x:.2f}, {self.shared_data.received_gyro_y:.2f}, {self.shared_data.received_gyro_z:.2f}]",
            "angles": f"[{self.shared_data.received_angle_roll:.2f}, {self.shared_data.received_angle_pitch:.2f}, {self.shared_data.received_angle_yaw:.2f}]"
        }
