"""
初始化模块
负责串口初始化、COM口配置和协议加载
"""

import serial
import serial.tools.list_ports
from protocol import ProtocolData

class Initializer:
    def __init__(self):
        self.serial_port = None
        self.com_port = None
        self.baud_rate = 115200
        self.protocol_data = ProtocolData()
        
    def list_available_ports(self):
        """列出所有可用的COM口"""
        ports = serial.tools.list_ports.comports()
        available_ports = []
        for port in ports:
            available_ports.append({
                'device': port.device,
                'name': port.name,
                'description': port.description,
                'hwid': port.hwid
            })
        return available_ports
    
    def display_available_ports(self):
        """显示所有可用COM口信息"""
        available_ports = self.list_available_ports()
        
        if not available_ports:
            print("未找到可用的COM口")
            return []
        
        print("检测到以下可用COM口:")
        for i, port in enumerate(available_ports):
            print(f"  {i+1}. {port['device']} - {port['description']}")
        
        return available_ports
    
    def initialize_serial(self, com_port="COM16"):
        """
        初始化串口连接
        Args:
            com_port: 指定的COM口，如果为None则自动选择可用端口
        """
        # 首先显示所有可用端口
        available_ports = self.display_available_ports()
        
        if not available_ports:
            print("串口初始化失败: 未找到可用的COM口")
            return False
        
        # 提取设备名称列表
        port_devices = [port['device'] for port in available_ports]
        
        if com_port:
            if com_port not in port_devices:
                print(f"串口初始化失败: 指定的COM口 {com_port} 不可用")
                print(f"可用端口: {port_devices}")
                return False
            self.com_port = com_port
        else:
            # 自动选择第一个可用端口
            self.com_port = port_devices[0]
            print(f"自动选择COM口: {self.com_port}")
        
        try:
            # 初始化串口连接
            self.serial_port = serial.Serial(
                port=self.com_port,
                baudrate=self.baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1
            )
            print(f"串口初始化成功: {self.com_port}, 波特率: {self.baud_rate}")
            return True
        except Exception as e:
            print(f"串口初始化失败: {e}")
            print(f"请检查COM口 {self.com_port} 是否被其他程序占用或设备是否连接")
            return False
    
    def close_serial(self):
        """关闭串口连接"""
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            print("串口已关闭")
    
    def get_current_config(self):
        """获取当前配置信息"""
        return {
            "com_port": self.com_port,
            "baud_rate": self.baud_rate,
            "protocol_data": self.protocol_data
        }
    
    
