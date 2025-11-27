import threading
import queue
import time
from initial import SerialInitializer

class SerialThread:
    """串口通信线程类，用于处理串口操作以避免阻塞UI线程"""
    
    def __init__(self):
        self.serial_initializer = SerialInitializer()
        self.send_queue = queue.Queue()
        self.receive_queue = queue.Queue()
        self.running = False
        self.thread = None
        self.callbacks = []
        
    def start(self):
        """启动串口线程"""
        if self.running:
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        
    def stop(self):
        """停止串口线程"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        self.serial_initializer.close_serial()
        
    def _run(self):
        """串口线程主循环"""
        while self.running:
            try:
                # 处理发送队列
                if not self.send_queue.empty():
                    data = self.send_queue.get_nowait()
                    if data and self.serial_initializer.is_connected():
                        success = self.serial_initializer.send_data(data)
                        if not success:
                            print("发送数据失败")
                
                # 处理接收数据
                if self.serial_initializer.is_connected():
                    received_data = self.serial_initializer.receive_data(1024)
                    if received_data:
                        self.receive_queue.put(received_data)
                        # 通知回调函数
                        for callback in self.callbacks:
                            try:
                                callback(received_data)
                            except Exception as e:
                                print(f"回调函数执行错误: {e}")
                
                # 短暂休眠以避免过度占用CPU
                time.sleep(0.01)  # 10ms
                
            except Exception as e:
                print(f"串口线程错误: {e}")
                time.sleep(0.1)
                
    def send_data(self, data):
        """发送数据（线程安全）"""
        if self.running and data:
            self.send_queue.put(data)
            return True
        return False
        
    def receive_data(self):
        """接收数据（线程安全）"""
        try:
            return self.receive_queue.get_nowait()
        except queue.Empty:
            return None
            
    def add_receive_callback(self, callback):
        """添加接收数据回调函数"""
        if callback not in self.callbacks:
            self.callbacks.append(callback)
            
    def remove_receive_callback(self, callback):
        """移除接收数据回调函数"""
        if callback in self.callbacks:
            self.callbacks.remove(callback)
            
    def initialize_serial(self, port_name, baudrate=115200):
        """初始化串口连接"""
        return self.serial_initializer.initialize_serial(port_name, baudrate)
        
    def close_serial(self):
        """关闭串口连接"""
        self.serial_initializer.close_serial()
        
    def is_connected(self):
        """检查串口是否连接"""
        return self.serial_initializer.is_connected()
        
    def list_available_ports(self):
        """列出可用端口"""
        return self.serial_initializer.list_available_ports()
