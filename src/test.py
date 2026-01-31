import struct

def stm32_f411_hardware_simulator(data: bytes) -> int:
    poly = 0x04C11DB7
    crc = 0xFFFFFFFF # F411 强制初值
    
    # 【关键修正】：STM32 硬件处理不满 4 字节的最后一个字时
    # 实际上是按照内存对齐读取的。
    padding_len = (4 - (len(data) % 4)) % 4
    padded_data = data + b'\x00' * padding_len
    
    for i in range(0, len(padded_data), 4):
        # F411 硬件直接读取 32位寄存器，即小端序读取
        word = struct.unpack('<I', padded_data[i:i+4])[0]
        
        crc ^= word
        for _ in range(32):
            if crc & 0x80000000:
                crc = ((crc << 1) ^ poly) & 0xFFFFFFFF
            else:
                crc = (crc << 1) & 0xFFFFFFFF
    return crc & 0xFF

# 测试你提供的那串数据
raw_hex = "CC E8 03 00 00 00 00 80 3F 00 00 00 40 00 00 40 40 CD CC CC 3D CD CC 4C 3E 9A 99 99 3E CD CC 1C 41 00 00 00 00 00 00 00 00 00 00 70 41 00 00 70 C1 00 00 20 41 00 00 20 C1"
packet_57 = bytearray.fromhex(raw_hex)

correct_crc8 = stm32_f411_hardware_simulator(packet_57)
print(f"数据长度: {len(packet_57)}")
print(f"经过模拟器计算，正确的 CRC8 应该是: 0x{correct_crc8:02X}")