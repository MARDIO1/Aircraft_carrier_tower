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
            available_ports.append(port.device)
        return available_ports
    
    def initialize_serial(self, com_port=None):
        """
        初始化串口连接
        Args:
            com_port: 指定的COM口，如果为None则自动选择第一个可用端口
        """
        available_ports = self.list_available_ports()
        
        if not available_ports:
            raise Exception("未找到可用的COM口")
        
        if com_port:
            if com_port not in available_ports:
                raise Exception(f"指定的COM口 {com_port} 不可用")
            self.com_port = com_port
        else:
            # 自动选择第一个可用端口
            self.com_port = available_ports[0]
        
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
    
    def set_preset_state(self, preset_num):
        """设置预设状态"""
        if preset_num == 1:
            # 预设状态1
            self.protocol_data.main_switch = 1
            self.protocol_data.fan_speed = 1000
            self.protocol_data.servo_angles = [500, 500, 500, 500]
        elif preset_num == 2:
            # 预设状态2
            self.protocol_data.main_switch = 1
            self.protocol_data.fan_speed = 2000
            self.protocol_data.servo_angles = [1000, 1000, 1000, 1000]
        else:
            print(f"未知的预设状态: {preset_num}")
