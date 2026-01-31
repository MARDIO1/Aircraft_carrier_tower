#!/usr/bin/env python3
"""
BlackBox测试数据生成器
生成符合60字节BlackBox数据包格式的测试数据，包含状态机字段
"""

import struct
import sys
from pathlib import Path

# 导入项目中的CRC计算器
try:
    from crc_calculator import add_crc8_to_packet
except ImportError:
    print("错误: 无法导入crc_calculator模块")
    print("请确保脚本在项目根目录或src目录中运行")
    sys.exit(1)


def generate_test_blackbox_packet():
    """
    生成一个测试用的BlackBox数据包（60字节）
    
    数据包结构:
    0xCC + timestamp(4) + statemachine(1) + angle(12) + gyro(12) + acc(12) + rudder(16) + CRC(1) + 0xDD
    
    返回:
        bytearray: 60字节的完整数据包
    """
    # 创建原始数据包（不含CRC，但包含帧尾用于计算）
    packet = bytearray()
    
    # 1. 帧头 (1字节)
    packet.append(0xCC)  # 帧头标识
    
    # 2. 时间戳 (4字节, uint32, 小端序)
    # 使用测试值: 1234567890
    timestamp = 1234567890
    packet.extend(struct.pack('<I', timestamp))
    
    # 3. 状态机数据 (1字节, uint8) - 新增字段
    # 使用测试值: 0x55 (二进制01010101)
    statemachine = 0x55
    packet.append(statemachine)
    
    # 4. 角度数据 (12字节, 3个float, 小端序)
    # roll, pitch, yaw (单位: 度)
    angle_roll = 10.5    # 横滚角
    angle_pitch = -5.2   # 俯仰角  
    angle_yaw = 180.0    # 偏航角
    packet.extend(struct.pack('<fff', angle_roll, angle_pitch, angle_yaw))
    
    # 5. 角速度数据 (12字节, 3个float, 小端序)
    # x, y, z (单位: 度/秒)
    gyro_x = 0.1
    gyro_y = 0.2
    gyro_z = 0.3
    packet.extend(struct.pack('<fff', gyro_x, gyro_y, gyro_z))
    
    # 6. 加速度数据 (12字节, 3个float, 小端序)
    # x, y, z (单位: m/s²)
    acc_x = 0.0
    acc_y = 0.0
    acc_z = 9.8  # 模拟重力加速度
    packet.extend(struct.pack('<fff', acc_x, acc_y, acc_z))
    
    # 7. 舵机目标角度 (16字节, 4个float, 小端序)
    # 4个舵机的目标角度 (单位: 度)
    rudder1 = 15.0
    rudder2 = 30.0
    rudder3 = 45.0
    rudder4 = 60.0
    packet.extend(struct.pack('<ffff', rudder1, rudder2, rudder3, rudder4))
    
    # 8. 帧尾 (1字节) - 临时添加，CRC计算时会处理
    packet.append(0xDD)  # 帧尾标识
    
    # 9. 添加CRC校验 (1字节)
    # 计算范围: 从索引0开始，到倒数第2个字节之前（即除帧尾外的所有数据）
    # calc_start=0, calc_end=-1 表示计算 packet[0:-1] 的CRC
    packet_with_crc = add_crc8_to_packet(packet, calc_start=0, calc_end=-1)
    
    return packet_with_crc


def print_packet_analysis(packet):
    """分析并打印数据包内容"""
    print("=" * 60)
    print("BlackBox测试数据包分析")
    print("=" * 60)
    
    # 验证数据包长度
    print(f"数据包长度: {len(packet)} 字节")
    if len(packet) != 60:
        print(f"警告: 数据包长度应为60字节，实际为{len(packet)}字节")
    
    print("\n1. 原始十六进制数据:")
    hex_str = ' '.join(f'{b:02X}' for b in packet)
    # 每16字节换行显示
    for i in range(0, len(packet), 16):
        chunk = packet[i:i+16]
        chunk_hex = ' '.join(f'{b:02X}' for b in chunk)
        print(f"   {i:02d}-{i+len(chunk)-1:02d}: {chunk_hex}")
    
    print("\n2. 数据包结构分析:")
    
    # 帧头
    print(f"   帧头 (0): 0x{packet[0]:02X} {'✓' if packet[0] == 0xCC else '✗'}")
    
    # 时间戳 (字节1-4)
    timestamp = struct.unpack('<I', packet[1:5])[0]
    print(f"   时间戳 (1-4): {timestamp}")
    
    # 状态机数据 (字节5)
    statemachine = packet[5]
    print(f"   状态机 (5): 0x{statemachine:02X} ({statemachine})")
    
    # 角度 (字节6-17)
    angle = struct.unpack('<fff', packet[6:18])
    print(f"   角度 (6-17): roll={angle[0]:.2f}°, pitch={angle[1]:.2f}°, yaw={angle[2]:.2f}°")
    
    # 角速度 (字节18-29)
    gyro = struct.unpack('<fff', packet[18:30])
    print(f"   角速度 (18-29): x={gyro[0]:.2f}°/s, y={gyro[1]:.2f}°/s, z={gyro[2]:.2f}°/s")
    
    # 加速度 (字节30-41)
    acc = struct.unpack('<fff', packet[30:42])
    print(f"   加速度 (30-41): x={acc[0]:.2f}m/s², y={acc[1]:.2f}m/s², z={acc[2]:.2f}m/s²")
    
    # 舵机角度 (字节42-57)
    rudder = struct.unpack('<ffff', packet[42:58])
    print(f"   舵机角度 (42-57): [{rudder[0]:.2f}°, {rudder[1]:.2f}°, {rudder[2]:.2f}°, {rudder[3]:.2f}°]")
    
    # CRC (字节58)
    crc = packet[58]
    print(f"   CRC (58): 0x{crc:02X}")
    
    # 帧尾 (字节59)
    frame_end = packet[59]
    print(f"   帧尾 (59): 0x{frame_end:02X} {'✓' if frame_end == 0xDD else '✗'}")
    
    print("\n3. 数据验证:")
    print(f"   总字节数: {len(packet)}/60 {'✓' if len(packet) == 60 else '✗'}")
    print(f"   帧头正确: {'✓' if packet[0] == 0xCC else '✗'}")
    print(f"   帧尾正确: {'✓' if packet[59] == 0xDD else '✗'}")


def save_to_file(packet, filename="test_blackbox.bin"):
    """保存数据包到二进制文件"""
    try:
        with open(filename, 'wb') as f:
            f.write(packet)
        print(f"\n数据包已保存到: {filename}")
        print(f"文件大小: {Path(filename).stat().st_size} 字节")
        return True
    except Exception as e:
        print(f"保存文件失败: {e}")
        return False


def generate_python_code(packet):
    """生成Python字节数组代码"""
    print("\n" + "=" * 60)
    print("Python字节数组代码 (可直接复制使用):")
    print("=" * 60)
    
    print("test_packet = bytearray([")
    for i in range(0, len(packet), 12):
        chunk = packet[i:i+12]
        hex_values = ', '.join(f'0x{b:02X}' for b in chunk)
        print(f"    {hex_values},")
    print("])")
    
    print("\n使用示例:")
    print("```python")
    print("# 发送测试数据包")
    print("import serial")
    print("ser = serial.Serial('COM3', 115200)  # 根据实际情况修改串口")
    print("ser.write(test_packet)")
    print("ser.close()")
    print("```")


def main():
    """主函数"""
    print("BlackBox测试数据生成器")
    print("生成60字节数据包，包含状态机字段")
    print("-" * 60)
    
    try:
        # 生成测试数据包
        print("正在生成测试数据包...")
        test_packet = generate_test_blackbox_packet()
        
        # 分析数据包
        print_packet_analysis(test_packet)
        
        # 保存到文件
        save_to_file(test_packet)
        
        # 生成Python代码
        generate_python_code(test_packet)
        
        print("\n" + "=" * 60)
        print("生成完成！")
        print("=" * 60)
        print("\n使用说明:")
        print("1. 使用串口工具发送 test_blackbox.bin 文件")
        print("2. 或复制上面的Python代码直接发送")
        print("3. 在DATA模式下查看接收到的数据")
        
    except Exception as e:
        print(f"生成测试数据包时出错: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
