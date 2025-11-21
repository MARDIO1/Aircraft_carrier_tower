import struct

class Protocol:
    def __init__(self):
        # 上行数据包常量（地面站 → 制导镖）
        self.UP_HEADER = 0xAA
        self.UP_TAIL = 0xBB
        self.UP_FRAME_SZ = 14  # header(1) + switch(1) + fan_rpm(2) + servo[4](8) + tail(1) + crc(1) = 14
        
        # 下行数据包常量（制导镖 → 地面站）
        self.DOWN_HEADER = 0xCC
        self.DOWN_TAIL = 0xDD
        self.DOWN_FRAME_SZ = 40  # header(1) + last_switch(1) + gyro[9](36) + tail(1) + crc(1) = 40
        
        # 兼容性常量
        self.ground_header = self.UP_HEADER
        self.ground_footer = self.UP_TAIL
        self.aircraft_header = self.DOWN_HEADER
        self.aircraft_footer = self.DOWN_TAIL
        self.cmd_on = 0x01
        self.cmd_off = 0x00
        
        # 接收缓冲区
        self.receive_buffer = bytearray()
    
    def _calculate_crc8(self, data):
        """
        计算CRC-8校验和
        使用多项式: x^8 + x^2 + x + 1 (0x07)
        """
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
    
    def encode_up_frame(self, switch_cmd, fan_rpm, servo_angles):
        """
        编码上行数据包（地面站 → 制导镖）
        完全匹配C结构定义：header + switch_cmd + fan_rpm + servo[4] + tail + crc
        Args:
            switch_cmd: int 总开关 (0=关, 1=开)
            fan_rpm: int 风扇转速 (0-1000)
            servo_angles: list 4个舵机角度 [0-180, 0-180, 0-180, 0-180]
        Returns:
            bytes: 14字节数据包
        """
        try:
            # 使用小端序打包数据（不包括CRC）
            packet_without_crc = struct.pack('<B B h 4h B',
                                self.UP_HEADER,    # 0xAA
                                switch_cmd,        # 总开关
                                fan_rpm,           # 风扇转速
                                servo_angles[0],   # 舵机1角度
                                servo_angles[1],   # 舵机2角度
                                servo_angles[2],   # 舵机3角度
                                servo_angles[3],   # 舵机4角度
                                self.UP_TAIL)      # 0xBB
            
            # 计算CRC（对整个数据包计算，包括包头包尾）
            crc = self._calculate_crc8(packet_without_crc)
            
            # 添加CRC字节
            full_packet = packet_without_crc + bytes([crc])
            
            return full_packet
        except Exception as e:
            print(f"编码上行数据包错误: {e}")
            return None
    
    def process_receive_data(self, data):
        """
        处理接收数据，支持数据流解析
        优化版本：使用缓冲区管理，避免数据丢失
        Args:
            data: bytes 接收到的原始数据
        Returns:
            list: 解析出的有效数据包列表
        """
        if not data:
            return []
        
        # 添加到缓冲区
        self.receive_buffer.extend(data)
        
        valid_packets = []
        
        # 处理缓冲区中的数据
        while len(self.receive_buffer) >= 3:  # 至少需要包头+1字节数据+包尾
            # 查找包头
            header_pos = -1
            for i in range(len(self.receive_buffer) - 2):
                if self.receive_buffer[i] == self.DOWN_HEADER:
                    header_pos = i
                    break
            
            if header_pos == -1:
                # 没有找到有效包头，清空缓冲区
                self.receive_buffer.clear()
                break
            
            # 移除包头之前的数据
            if header_pos > 0:
                self.receive_buffer = self.receive_buffer[header_pos:]
            
            # 检查是否有完整的数据包
            if len(self.receive_buffer) >= self.DOWN_FRAME_SZ:
                packet_data = bytes(self.receive_buffer[:self.DOWN_FRAME_SZ])
                
                # 尝试解码数据包
                decoded = self._decode_down_frame_fast(packet_data)
                if decoded is not None:
                    valid_packets.append(decoded)
                    # 移除已处理的数据
                    self.receive_buffer = self.receive_buffer[self.DOWN_FRAME_SZ:]
                else:
                    # 解码失败，跳过这个包头
                    self.receive_buffer = self.receive_buffer[1:]
            else:
                # 数据不完整，等待更多数据
                break
        
        return valid_packets
    
    def _decode_down_frame_fast(self, data):
        """
        解码下行数据包（制导镖 → 地面站）
        完全匹配C结构定义：header + last_switch + gyro[9] + tail + crc
        Args:
            data: bytes 接收到的数据
        Returns:
            dict: 包含last_switch和gyro数据的字典，或None
        """
        if len(data) != self.DOWN_FRAME_SZ:
            return None
        
        try:
            # 解析完整40字节数据包
            # header(1) + last_switch(1) + gyro[9](36) + tail(1) + crc(1) = 40
            header, last_switch, gx, gy, gz, ax, ay, az, mx, my, mz, tail, crc = \
                struct.unpack('<B B 9f B B', data)
            
            # 验证包头包尾
            if header != self.DOWN_HEADER or tail != self.DOWN_TAIL:
                return None
            
            # 验证CRC（可选，但推荐用于数据完整性检查）
            data_without_crc = data[:-1]  # 去掉CRC字节
            calculated_crc = self._calculate_crc8(data_without_crc)
            if calculated_crc != crc:
                print(f"CRC校验失败: 期望{calculated_crc:02X}, 实际{crc:02X}")
                # 可以选择返回None或继续处理（根据可靠性要求）
                # return None
            
            return {
                'last_switch': last_switch,
                'gyro_data': {
                    'gx': gx, 'gy': gy, 'gz': gz,  # 陀螺仪
                    'ax': ax, 'ay': ay, 'az': az,  # 加速度计
                    'mx': mx, 'my': my, 'mz': mz   # 磁力计
                }
            }
        except Exception as e:
            print(f"解码下行数据包错误: {e}")
            return None
    
    # 兼容性函数（保持现有代码正常工作）
    def encode_ground_command(self, is_on):
        """编码地面站开启/关闭命令（兼容现有代码）"""
        switch_cmd = self.cmd_on if is_on else self.cmd_off
        return self.encode_up_frame(switch_cmd, 0, [90, 90, 90, 90])
    
    def decode_ground_command(self, data):
        """解码地面站开启/关闭命令（兼容现有代码）"""
        if len(data) != 3:
            return None
        if data[0] != self.ground_header or data[-1] != self.ground_footer:
            return None
        return data[1] == self.cmd_on
    
    def encode_aircraft_status(self, is_on):
        """编码航模状态（兼容现有代码）"""
        status_byte = self.cmd_on if is_on else self.cmd_off
        packet = bytes([self.aircraft_header, status_byte, self.aircraft_footer])
        return packet
    
    def decode_aircraft_status(self, data):
        """解码航模状态（兼容现有代码）"""
        # 尝试解码完整下行数据包
        packets = self.process_receive_data(data)
        if packets:
            return packets[0]['last_switch'] == 1
        
        # 回退到简单解码
        if len(data) != 3:
            return None
        if data[0] != self.aircraft_header or data[-1] != self.aircraft_footer:
            return None
        return data[1] == self.cmd_on
    
    def clear_buffer(self):
        """清空接收缓冲区"""
        self.receive_buffer.clear()
