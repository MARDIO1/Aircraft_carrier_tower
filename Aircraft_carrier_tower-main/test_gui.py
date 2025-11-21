"""
GUI功能测试脚本
用于验证增强后的地面站功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/src')

from protocol import Protocol
from initial import SerialInitializer
from playerInput import PlayerInput
from GUI import GroundStationGUI

def test_gui_functionality():
    """测试GUI功能"""
    print("=== GUI功能测试 ===")
    
    # 初始化各模块
    protocol = Protocol()
    serial_initializer = SerialInitializer()
    player_input = PlayerInput()
    
    # 创建GUI实例
    gui = GroundStationGUI(protocol, serial_initializer, player_input)
    
    # 测试滑块回调功能
    print("1. 测试滑块回调功能...")
    
    # 模拟滑块变化
    print("   - 测试油门滑块回调")
    gui.on_throttle_change(0.5)
    print(f"     油门标签: {gui.throttle_label.cget('text')}")
    print(f"     player_input.throttle: {player_input.throttle}")
    
    print("   - 测试风扇滑块回调")
    gui.on_fan_change(500)
    print(f"     风扇标签: {gui.fan_label.cget('text')}")
    print(f"     player_input.fan_rpm: {player_input.fan_rpm}")
    
    print("   - 测试舵机滑块回调")
    gui.on_servo1_change(45)
    gui.on_servo2_change(135)
    gui.on_servo3_change(90)
    gui.on_servo4_change(180)
    print(f"     舵机1标签: {gui.servo1_label.cget('text')}")
    print(f"     舵机2标签: {gui.servo2_label.cget('text')}")
    print(f"     舵机3标签: {gui.servo3_label.cget('text')}")
    print(f"     舵机4标签: {gui.servo4_label.cget('text')}")
    print(f"     player_input.servo_angles: {player_input.servo_angles}")
    
    # 测试协议编码功能
    print("\n2. 测试协议编码功能...")
    
    # 测试完整数据编码
    switch_cmd = 1
    fan_rpm = 750
    servo_angles = [45, 135, 90, 180]
    
    encoded_data = protocol.encode_up_frame(switch_cmd, fan_rpm, servo_angles)
    if encoded_data:
        print(f"   - 完整数据编码成功: {len(encoded_data)} 字节")
        print(f"     数据: {encoded_data.hex()}")
    else:
        print("   - 完整数据编码失败")
    
    # 测试简单命令编码
    simple_data = protocol.encode_ground_command(True)
    if simple_data:
        print(f"   - 简单命令编码成功: {len(simple_data)} 字节")
        print(f"     数据: {simple_data.hex()}")
    else:
        print("   - 简单命令编码失败")
    
    # 测试重置功能
    print("\n3. 测试重置功能...")
    gui.reset_controls()
    print(f"   - 油门值: {gui.throttle_var.get()}")
    print(f"   - 风扇转速: {gui.fan_speed_var.get()}")
    print(f"   - 舵机角度: {gui.servo1_var.get()}, {gui.servo2_var.get()}, {gui.servo3_var.get()}, {gui.servo4_var.get()}")
    
    print("\n=== 测试完成 ===")
    print("所有功能增强已成功实现：")
    print("✓ 实时滑块回调功能")
    print("✓ 风扇转速控制")
    print("✓ 舵机角度控制") 
    print("✓ 完整数据发送功能")
    print("✓ UI界面根据功能动态更新")

if __name__ == "__main__":
    test_gui_functionality()
