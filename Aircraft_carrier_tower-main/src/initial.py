import serial
import serial.tools.list_ports

class SerialInitializer:
    def __init__(self):
        self.serial_port = None
        self.baudrate = 115200
        self.timeout = 1
    
    def list_available_ports(self):
        """列出可用的COM端口"""
        ports = serial.tools.list_ports.comports()
        port_list = []
        for port in ports:
            port_list.append({
                'device': port.device,
                'description': port.description,
                'hwid': port.hwid
            })
        return port_list
    
    def initialize_serial(self, port_name, baudrate=115200):
        """初始化串口连接
        Args:
            port_name: str COM端口名称 (如 'COM3')
            baudrate: int 波特率，默认115200
        Returns:
            bool: 初始化是否成功
        """
        try:
            self.serial_port = serial.Serial(
                port=port_name,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout
            )
            self.baudrate = baudrate
            return True
        except Exception as e:
            print(f"串口初始化失败: {e}")
            return False
    
    def close_serial(self):
        """关闭串口连接"""
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            self.serial_port = None
    
    def send_data(self, data):
        """发送数据
        Args:
            data: bytes 要发送的数据
        Returns:
            bool: 发送是否成功
        """
        if not self.serial_port or not self.serial_port.is_open:
            print("串口未连接")
            return False
        
        try:
            self.serial_port.write(data)
            return True
        except Exception as e:
            print(f"发送数据失败: {e}")
            return False
    
    def receive_data(self, size=1024):
        """接收数据
        Args:
            size: int 接收缓冲区大小
        Returns:
            bytes: 接收到的数据
        """
        if not self.serial_port or not self.serial_port.is_open:
            print("串口未连接")
            return None
        
        try:
            data = self.serial_port.read(size)
            return data if data else None
        except Exception as e:
            print(f"接收数据失败: {e}")
            return None
    
    def is_connected(self):
        """检查串口是否连接"""
        return self.serial_port and self.serial_port.is_open
