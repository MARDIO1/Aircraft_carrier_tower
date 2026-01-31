"""
串口接收模块
负责从航模接收数据并解码
"""

import threading
import time
import struct
from protocol import decode_data
from blackbox_logger import BlackBoxLogger

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
        
        # 初始化黑箱记录器
        self.blackbox_logger = BlackBoxLogger(max_records=2000)
        
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
        """处理接收到的原始数据，只处理59字节BlackBox数据包"""
        if not data:
            return
            
        # 将数据添加到缓冲区
        self.receive_buffer.extend(data)
        
        # 尝试从缓冲区中提取完整的59字节数据包
        while len(self.receive_buffer) >= 59:
            # 查找帧头 0xCC
            start_idx = -1
            for i in range(len(self.receive_buffer) - 58):  # 需要至少59字节
                if self.receive_buffer[i] == 0xCC:  # 帧头
                    start_idx = i
                    break
            
            if start_idx == -1:
                # 没有找到帧头，清空缓冲区
                self.receive_buffer.clear()
                return
                
            # 检查是否有完整的59字节数据包
            if start_idx + 59 > len(self.receive_buffer):
                # 数据包不完整，等待更多数据
                if start_idx > 0:
                    self.receive_buffer = self.receive_buffer[start_idx:]
                return
                
            # 提取完整数据包
            packet = bytes(self.receive_buffer[start_idx:start_idx + 59])
            
            # 检查帧尾
            if packet[-1] != 0xDD:  # 帧尾不匹配
                # 帧尾不匹配，跳过这个帧头
                self.receive_buffer = self.receive_buffer[start_idx + 59:]
                continue
            
            # 解码数据包
            decoded_data = decode_data(packet)
            if decoded_data:
                self._update_shared_data(decoded_data)
                self.receive_count += 1
                self.last_receive_time = time.time()
            else:
                self.error_count += 1
            
            # 从缓冲区中移除已处理的数据包
            self.receive_buffer = self.receive_buffer[start_idx + 59:]
                
    def _update_shared_data(self, decoded_data):
        """将解码后的BlackBox数据更新到共享数据结构中"""
        try:
            # 更新BlackBox数据 - 只更新59字节数据包中实际包含的字段
            self.shared_data.blackbox_timestamp = decoded_data.blackbox_timestamp
            self.shared_data.blackbox_angle = decoded_data.blackbox_angle
            self.shared_data.blackbox_gyro = decoded_data.blackbox_gyro
            self.shared_data.blackbox_acc = decoded_data.blackbox_acc
            self.shared_data.blackbox_rudder = decoded_data.blackbox_rudder
            self.shared_data.blackbox_received = True
            
            # 更新最后接收时间
            self.shared_data.last_received_time = decoded_data.last_received_time
            
            # 记录到黑箱文件
            if self.blackbox_logger:
                # 传递数据包时间戳作为第一个参数（虽然log_data方法不再使用它）
                # 保持向后兼容性
                self.blackbox_logger.log_data(
                    float(decoded_data.blackbox_timestamp),  # 转换为float以匹配方法签名
                    decoded_data
                )
            
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
        if self.shared_data.blackbox_received:
            return {
                "packet_timestamp": str(self.shared_data.blackbox_timestamp),  # 数据包时间戳
                "angle": f"[{self.shared_data.blackbox_angle[0]:.3f}, {self.shared_data.blackbox_angle[1]:.3f}, {self.shared_data.blackbox_angle[2]:.3f}]",
                "gyro": f"[{self.shared_data.blackbox_gyro[0]:.3f}, {self.shared_data.blackbox_gyro[1]:.3f}, {self.shared_data.blackbox_gyro[2]:.3f}]",
                "acc": f"[{self.shared_data.blackbox_acc[0]:.3f}, {self.shared_data.blackbox_acc[1]:.3f}, {self.shared_data.blackbox_acc[2]:.3f}]",
                "rudder": f"[{self.shared_data.blackbox_rudder[0]:.3f}, {self.shared_data.blackbox_rudder[1]:.3f}, {self.shared_data.blackbox_rudder[2]:.3f}, {self.shared_data.blackbox_rudder[3]:.3f}]"
            }
        else:
            return {
                "status": "未接收到BlackBox数据"
            }
            
    def start_blackbox_logging(self):
        """开始黑箱记录（进入DATA模式时调用）"""
        if self.blackbox_logger:
            return self.blackbox_logger.start_logging()
        return False
    
    def stop_blackbox_logging(self):
        """停止黑箱记录"""
        if self.blackbox_logger:
            return self.blackbox_logger.stop_logging()
        return False
    
    def toggle_blackbox_logging(self):
        """切换黑箱记录状态（L键功能）"""
        if self.blackbox_logger:
            return self.blackbox_logger.toggle_logging()
        return False
    
    def get_blackbox_logging_status(self):
        """获取黑箱记录状态"""
        if self.blackbox_logger:
            return self.blackbox_logger.get_status()
        return {
            'is_logging': False,
            'record_count': 0,
            'max_records': 2000,
            'remaining': 0
        }
