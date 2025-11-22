#!/usr/bin/env python3
"""
增强版地面站功能测试脚本
测试所有新功能：协议编码/解码、风扇控制、舵机控制、可视化指示器
"""

import sys
import os

# 添加src目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from protocol import Protocol
from playerInput import PlayerInput

def test_protocol_encoding():
    """测试协议编码功能"""
    print("=" * 60)
    print("测试协议编码功能")
    print("=" * 60)
    
    protocol = Protocol()
    
    # 测试用例
    test_cases = [
        (0, 0, [90, 90, 90, 90]),      # 关闭状态
        (1, 500, [90, 90, 90, 90]),    # 开启状态，中等风扇
        (1, 1000, [0, 45, 90, 135]),   # 全速风扇，不同舵机角度
        (1, 250, [180, 0, 90, 45]),    # 低风扇，极限舵机角度
    ]
    
    for i, (switch, fan_rpm, servo_angles) in enumerate(test_cases, 1):
        print(f"\n测试用例 {i}:")
        print(f"  开关: {switch}, 风扇: {fan_rpm}RPM, 舵机: {servo_angles}")
        
        # 编码数据
        encoded = protocol.encode_up_frame(switch, fan_rpm, servo_angles)
        if encoded:
            print(f"  编码成功: {len(encoded)} 字节")
            print(f"  十六进制: {encoded.hex()}")
            
            # 验证数据包结构
            if len(encoded) == 14:
                print("  ✓ 数据包长度正确 (14字节)")
            else:
                print("  ✗ 数据包长度错误")
                
            # 验证包头包尾
            if encoded[0] == 0xAA and encoded[-2] == 0xBB:
                print("  ✓ 包头包尾正确")
            else:
                print("  ✗ 包头包尾错误")
        else:
            print("  ✗ 编码失败")

def test_protocol_decoding():
    """测试协议解码功能"""
    print("\n" + "=" * 60)
    print("测试协议解码功能")
    print("=" * 60)
    
    protocol = Protocol()
    
    # 创建模拟下行数据包
    import struct
    
    # 模拟传感器数据
    gyro_data = {
        'gx': 1.23, 'gy': -2.34, 'gz': 3.45,
        'ax': 0.12, 'ay': -0.23, 'az': 9.81,
        'mx': 25.6, 'my': -12.3, 'mz': 48.7
    }
    
    # 编码下行数据包
    header = 0xCC
    last_switch = 1
    tail = 0xDD
    
    # 打包数据（不包括CRC）
    packet_without_crc = struct.pack('<B B 9f B',
                        header,
                        last_switch,
                        gyro_data['gx'],
                        gyro_data['gy'],
                        gyro_data['gz'],
                        gyro_data['ax'],
                        gyro_data['ay'],
                        gyro_data['az'],
                        gyro_data['mx'],
                        gyro_data['my'],
                        gyro_data['mz'],
                        tail)
    
    # 计算CRC
    crc = protocol._calculate_crc8(packet_without_crc)
    full_packet = packet_without_crc + bytes([crc])
    
    print(f"模拟下行数据包: {len(full_packet)} 字节")
    print(f"十六进制: {full_packet.hex()}")
    
    # 解码数据包
    decoded = protocol._decode_down_frame_fast(full_packet)
    if decoded:
        print("✓ 解码成功")
        print(f"  开关状态: {decoded['last_switch']}")
        print(f"  陀螺仪: gx={decoded['gyro_data']['gx']:.2f}, gy={decoded['gyro_data']['gy']:.2f}, gz={decoded['gyro_data']['gz']:.2f}")
        print(f"  加速度: ax={decoded['gyro_data']['ax']:.2f}, ay={decoded['gyro_data']['ay']:.2f}, az={decoded['gyro_data']['az']:.2f}")
        print(f"  磁力计: mx={decoded['gyro_data']['mx']:.2f}, my={decoded['gyro_data']['my']:.2f}, mz={decoded['gyro_data']['mz']:.2f}")
    else:
        print("✗ 解码失败")

def test_player_input():
    """测试玩家输入功能"""
    print("\n" + "=" * 60)
    print("测试玩家输入功能")
    print("=" * 60)
    
    player_input = PlayerInput()
    
    # 测试初始状态
    throttle, surfaces, fan_rpm, servo_angles = player_input.get_control_data()
    print(f"初始状态:")
    print(f"  油门: {throttle}")
    print(f"  舵面: {surfaces}")
    print(f"  风扇: {fan_rpm}RPM")
    print(f"  舵机: {servo_angles}")
    
    # 测试设置风扇和舵机
    print("\n设置风扇和舵机控制:")
    player_input.set_fan_servo_controls(750, [45, 90, 135, 180])
    throttle, surfaces, fan_rpm, servo_angles = player_input.get_control_data()
    print(f"  风扇: {fan_rpm}RPM")
    print(f"  舵机: {servo_angles}")
    
    # 测试键盘输入
    print("\n模拟键盘输入:")
    test_keys = [
        ('q', True),  # 增加风扇
        ('1', True),  # 增加舵机1
        ('3', True),  # 增加舵机2
    ]
    
    for key, pressed in test_keys:
        player_input.set_keyboard_input(key, pressed)
        throttle, surfaces, fan_rpm, servo_angles = player_input.get_control_data()
        print(f"  按键 '{key}': 风扇={fan_rpm}RPM, 舵机={servo_angles}")

def test_visualization_logic():
    """测试可视化逻辑"""
    print("\n" + "=" * 60)
    print("测试可视化逻辑")
    print("=" * 60)
    
    def test_fan_color(rpm):
        """测试风扇颜色逻辑"""
        if rpm == 0:
            return "#cccccc"
        elif rpm < 300:
            return "#4CAF50"  # 绿色
        elif rpm < 700:
            return "#FFC107"  # 黄色
        else:
            return "#f44336"  # 红色
    
    def test_servo_color(angle):
        """测试舵机颜色逻辑"""
        if angle == 90:
            return "#4CAF50"  # 绿色
        elif 80 <= angle <= 100:
            return "#2196F3"  # 蓝色
        elif 60 <= angle < 80 or 100 < angle <= 120:
            return "#FFC107"  # 黄色
        else:
            return "#f44336"  # 红色
    
    # 测试风扇颜色
    print("风扇转速颜色测试:")
    test_fan_rpms = [0, 100, 299, 300, 500, 699, 700, 800, 1000]
    for rpm in test_fan_rpms:
        color = test_fan_color(rpm)
        print(f"  {rpm:4d} RPM -> {color}")
    
    # 测试舵机颜色
    print("\n舵机角度颜色测试:")
    test_angles = [0, 45, 60, 75, 80, 90, 100, 110, 120, 135, 180]
    for angle in test_angles:
        color = test_servo_color(angle)
        print(f"  {angle:3d}° -> {color}")

def test_compatibility():
    """测试兼容性功能"""
    print("\n" + "=" * 60)
    print("测试兼容性功能")
    print("=" * 60)
    
    protocol = Protocol()
    
    # 测试简单命令编码
    print("简单命令编码测试:")
    for is_on in [False, True]:
        data = protocol.encode_ground_command(is_on)
        status = "开启" if is_on else "关闭"
        print(f"  {status}: {data.hex() if data else '编码失败'}")
    
    # 测试简单状态解码
    print("\n简单状态解码测试:")
    test_packets = [
        bytes([0xCC, 0x01, 0xDD]),  # 开启状态
        bytes([0xCC, 0x00, 0xDD]),  # 关闭状态
    ]
    
    for packet in test_packets:
        status = protocol.decode_aircraft_status(packet)
        if status is not None:
            status_text = "开启" if status else "关闭"
            print(f"  {packet.hex()} -> {status_text}")
        else:
            print(f"  {packet.hex()} -> 解码失败")

def main():
    """主测试函数"""
    print("增强版地面站功能测试")
    print("=" * 60)
    
    # 运行所有测试
    test_protocol_encoding()
    test_protocol_decoding()
    test_player_input()
    test_visualization_logic()
    test_compatibility()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    main()
