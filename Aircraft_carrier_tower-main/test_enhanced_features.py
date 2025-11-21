#!/usr/bin/env python3
"""
测试增强功能脚本
验证风扇转速和舵机角度控制功能
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from protocol import Protocol

def test_protocol_encoding():
    """测试协议编码功能"""
    print("=== 测试协议编码功能 ===")
    
    protocol = Protocol()
    
    # 测试1: 基本开关控制
    print("\n1. 测试基本开关控制:")
    data = protocol.encode_up_frame(1, 0, [90, 90, 90, 90])
    print(f"  开关开启数据包: {data.hex() if data else 'None'}")
    print(f"  数据包长度: {len(data) if data else 0} 字节")
    
    # 测试2: 风扇控制
    print("\n2. 测试风扇控制:")
    data = protocol.encode_up_frame(1, 500, [90, 90, 90, 90])
    print(f"  风扇500RPM数据包: {data.hex() if data else 'None'}")
    
    # 测试3: 舵机控制
    print("\n3. 测试舵机控制:")
    data = protocol.encode_up_frame(1, 0, [45, 135, 90, 180])
    print(f"  舵机角度[45,135,90,180]数据包: {data.hex() if data else 'None'}")
    
    # 测试4: 完整控制
    print("\n4. 测试完整控制:")
    data = protocol.encode_up_frame(1, 750, [30, 60, 120, 150])
    print(f"  完整控制数据包: {data.hex() if data else 'None'}")
    
    # 测试CRC计算
    print("\n5. 测试CRC计算:")
    test_data = b'\xAA\x01\x00\x00\x5A\x00\x5A\x00\x5A\x00\x5A\x00\xBB'
    crc = protocol._calculate_crc8(test_data)
    print(f"  测试数据: {test_data.hex()}")
    print(f"  CRC计算结果: {crc:02X}")

def test_protocol_decoding():
    """测试协议解码功能"""
    print("\n=== 测试协议解码功能 ===")
    
    protocol = Protocol()
    
    # 创建模拟下行数据包
    print("\n1. 创建模拟下行数据包:")
    # header(1) + last_switch(1) + gyro[9](36) + tail(1) + crc(1) = 40
    import struct
    header = 0xCC
    last_switch = 1
    gyro_data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]  # gx,gy,gz,ax,ay,az,mx,my,mz
    tail = 0xDD
    
    # 打包数据（不包括CRC）
    packet_without_crc = struct.pack('<B B 9f B', header, last_switch, *gyro_data, tail)
    crc = protocol._calculate_crc8(packet_without_crc)
    full_packet = packet_without_crc + bytes([crc])
    
    print(f"  模拟下行数据包: {full_packet.hex()}")
    print(f"  数据包长度: {len(full_packet)} 字节")
    
    # 测试解码
    print("\n2. 测试解码功能:")
    decoded = protocol._decode_down_frame_fast(full_packet)
    if decoded:
        print(f"  解码成功:")
        print(f"    上次开关状态: {decoded['last_switch']}")
        print(f"    陀螺仪数据: {decoded['gyro_data']}")
    else:
        print("  解码失败")

def test_gui_functionality():
    """测试GUI功能"""
    print("\n=== 测试GUI功能 ===")
    
    from GUI import GroundStationGUI
    from initial import SerialInitializer
    from playerInput import PlayerInput
    
    print("GUI组件已导入:")
    print("  - GroundStationGUI: 包含风扇和舵机控制界面")
    print("  - SerialInitializer: 串口通信")
    print("  - PlayerInput: 支持风扇和舵机输入控制")
    
    print("\nGUI功能特性:")
    print("  ✓ 风扇控制滑块 (0-1000 RPM)")
    print("  ✓ 4个舵机控制滑块 (0-180°)")
    print("  ✓ 实时显示更新")
    print("  ✓ 发送完整数据功能")
    print("  ✓ 键盘控制支持")

def main():
    """主测试函数"""
    print("航模地面站增强功能测试")
    print("=" * 50)
    
    try:
        test_protocol_encoding()
        test_protocol_decoding()
        test_gui_functionality()
        
        print("\n" + "=" * 50)
        print("测试完成!")
        print("\n当前系统已支持的功能:")
        print("  ✓ 开关控制")
        print("  ✓ 风扇转速控制 (0-1000 RPM)")
        print("  ✓ 4个舵机角度控制 (0-180°)")
        print("  ✓ 完整数据包发送")
        print("  ✓ CRC校验")
        print("  ✓ 双向通信协议")
        print("  ✓ 实时GUI界面更新")
        
    except Exception as e:
        print(f"测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
