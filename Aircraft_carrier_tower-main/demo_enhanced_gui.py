#!/usr/bin/env python3
"""
增强版地面站GUI演示脚本
演示所有新功能：风扇转速控制、舵机角度控制、可视化状态指示器
"""

import sys
import os
import time
import threading
from datetime import datetime

# 添加src目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from protocol import Protocol
from playerInput import PlayerInput
from GUI_enhanced import EnhancedGroundStationGUI

class MockSerialInitializer:
    """模拟串口初始化器，用于演示"""
    def __init__(self):
        self.serial_port = None
        self.baudrate = 115200
        self.timeout = 1
        self.is_mock_connected = False
        self.receive_thread = None
        self.gui = None
        self.protocol = None
        self.demo_data = {
            'gx': 0.0, 'gy': 0.0, 'gz': 0.0,
            'ax': 0.0, 'ay': 0.0, 'az': 9.8,
            'mx': 0.0, 'my': 0.0, 'mz': 50.0
        }
        self.last_switch = 0
        self.is_running = False
    
    def set_gui_and_protocol(self, gui, protocol):
        """设置GUI和协议引用"""
        self.gui = gui
        self.protocol = protocol
    
    def list_available_ports(self):
        """列出模拟的COM端口"""
        return [
            {'device': 'COM3', 'description': '模拟串口1 - 增强版演示'},
            {'device': 'COM4', 'description': '模拟串口2 - 增强版演示'},
            {'device': 'COM5', 'description': '模拟串口3 - 增强版演示'}
        ]
    
    def initialize_serial(self, port_name, baudrate=115200):
        """模拟串口连接"""
        print(f"模拟连接到 {port_name} (波特率: {baudrate})")
        self.is_mock_connected = True
        self.baudrate = baudrate
        
        # 启动模拟数据发送线程
        self.is_running = True
        self.receive_thread = threading.Thread(target=self._mock_data_generator)
        self.receive_thread.daemon = True
        self.receive_thread.start()
        
        return True
    
    def close_serial(self):
        """模拟断开串口连接"""
        print("模拟断开串口连接")
        self.is_mock_connected = False
        self.is_running = False
        if self.receive_thread:
            self.receive_thread.join(timeout=1.0)
    
    def send_data(self, data):
        """模拟发送数据"""
        if not self.is_mock_connected:
            print("模拟串口未连接")
            return False
        
        try:
            # 解析发送的数据
            if len(data) >= 3:
                # 尝试解码为简单命令
                if data[0] == 0xAA and data[-1] == 0xBB:
                    switch_cmd = data[1]
                    self.last_switch = switch_cmd
                    print(f"模拟发送: 开关命令 = {'开启' if switch_cmd == 1 else '关闭'}")
            
            # 尝试解码为完整数据包
            if len(data) == 14:  # 完整上行数据包
                try:
                    header, switch_cmd, fan_rpm, servo1, servo2, servo3, servo4, tail, crc = \
                        struct.unpack('<B B h 4h B B', data)
                    
                    if header == 0xAA and tail == 0xBB:
                        self.last_switch = switch_cmd
                        print(f"模拟发送完整数据:")
                        print(f"  开关状态: {'开启' if switch_cmd == 1 else '关闭'}")
                        print(f"  风扇转速: {fan_rpm} RPM")
                        print(f"  舵机角度: [{servo1}°, {servo2}°, {servo3}°, {servo4}°]")
                except:
                    pass
            
            return True
        except Exception as e:
            print(f"模拟发送数据失败: {e}")
            return False
    
    def receive_data(self, size=1024):
        """模拟接收数据 - 返回空数据，实际数据通过回调发送"""
        return None
    
    def is_connected(self):
        """检查模拟连接状态"""
        return self.is_mock_connected
    
    def _mock_data_generator(self):
        """模拟数据生成器"""
        import math
        import random
        
        print("启动模拟数据生成器")
        
        while self.is_running and self.is_mock_connected:
            try:
                # 生成模拟传感器数据
                t = time.time()
                
                # 陀螺仪数据（带正弦波动）
                self.demo_data['gx'] = math.sin(t * 0.5) * 10.0 + random.uniform(-1, 1)
                self.demo_data['gy'] = math.cos(t * 0.3) * 8.0 + random.uniform(-1, 1)
                self.demo_data['gz'] = math.sin(t * 0.7) * 5.0 + random.uniform(-0.5, 0.5)
                
                # 加速度计数据（重力加速度 + 噪声）
                self.demo_data['ax'] = random.uniform(-0.2, 0.2)
                self.demo_data['ay'] = random.uniform(-0.2, 0.2)
                self.demo_data['az'] = 9.8 + random.uniform(-0.1, 0.1)
                
                # 磁力计数据（地球磁场模拟）
                self.demo_data['mx'] = 20.0 + math.sin(t * 0.2) * 5.0
                self.demo_data['my'] = 5.0 + math.cos(t * 0.4) * 3.0
                self.demo_data['mz'] = 50.0 + math.sin(t * 0.3) * 10.0
                
                # 编码下行数据包
                if self.protocol and self.gui:
                    packet = self._encode_mock_down_packet()
                    if packet:
                        # 模拟接收数据
                        self.gui.check_receive_data()
                
                time.sleep(0.1)  # 100ms更新频率
                
            except Exception as e:
                print(f"模拟数据生成器错误: {e}")
                time.sleep(1)
    
    def _encode_mock_down_packet(self):
        """编码模拟下行数据包"""
        import struct
        
        try:
            # 使用协议类的方法编码数据包
            header = 0xCC
            tail = 0xDD
            
            # 打包数据（不包括CRC）
            packet_without_crc = struct.pack('<B B 9f B',
                                header,
                                self.last_switch,
                                self.demo_data['gx'],
                                self.demo_data['gy'],
                                self.demo_data['gz'],
                                self.demo_data['ax'],
                                self.demo_data['ay'],
                                self.demo_data['az'],
                                self.demo_data['mx'],
                                self.demo_data['my'],
                                self.demo_data['mz'],
                                tail)
            
            # 计算CRC
            crc = self._calculate_crc8_mock(packet_without_crc)
            
            # 完整数据包
            full_packet = packet_without_crc + bytes([crc])
            
            # 直接调用GUI的数据处理
            if self.gui:
                packets = self.protocol.process_receive_data(full_packet)
                for packet in packets:
                    self.gui.display_down_data(packet)
            
            return full_packet
        except Exception as e:
            print(f"编码模拟下行数据包错误: {e}")
            return None
    
    def _calculate_crc8_mock(self, data):
        """模拟CRC-8计算"""
        crc = 0
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x80:
                    crc = (crc << 1) ^ 0x07
                else:
                    crc = (crc << 1)
                crc &= 0xFF
        return crc

def main():
    """主演示函数"""
    print("=" * 60)
    print("增强版地面站GUI演示")
    print("=" * 60)
    print("功能演示:")
    print("1. 可视化状态指示器（连接状态、系统状态）")
    print("2. 风扇转速控制与可视化指示")
    print("3. 舵机角度控制与可视化指示") 
    print("4. 传感器数据实时显示")
    print("5. 完整数据包发送/接收")
    print("=" * 60)
    
    # 初始化组件
    protocol = Protocol()
    player_input = PlayerInput()
    mock_serial = MockSerialInitializer()
    
    # 创建增强版GUI
    gui = EnhancedGroundStationGUI(protocol, mock_serial, player_input)
    mock_serial.set_gui_and_protocol(gui, protocol)
    
    print("启动增强版GUI...")
    print("请操作GUI界面测试以下功能:")
    print("- 连接模拟串口 (COM3)")
    print("- 调整系统开关滑块")
    print("- 调整风扇转速滑块 (0-1000 RPM)")
    print("- 调整4个舵机角度滑块 (0-180°)")
    print("- 观察可视化状态指示器的变化")
    print("- 查看传感器数据的实时更新")
    print("- 使用'发送完整数据'按钮测试完整协议")
    
    # 运行GUI
    try:
        gui.run()
    except KeyboardInterrupt:
        print("\n演示结束")
    except Exception as e:
        print(f"GUI运行错误: {e}")

if __name__ == "__main__":
    import struct  # 确保struct模块可用
    main()
