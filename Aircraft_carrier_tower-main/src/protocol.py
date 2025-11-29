import struct

class Protocol:
    def __init__(self):
        # 上行数据包常量（地面站 → 制导镖）
        self.UP_HEADER = 0xAA
        self.UP_TAIL = 0xBB
        self.UP_FRAME_SZ = 13  # header(1) + switch(1) + fan_rpm(2) + servo[4](8) + tail(1)  = 13
        
        # 下行数据包常量（制导镖 → 地面站）
        self.DOWN_HEADER = 0xCC
        self.DOWN_TAIL = 0xDD
        self.DOWN_FRAME_SZ = 39 # header(1) + last_switch(1) + gyro[9](36) + tail(1)  = 39
        
        # 数据包大小配置
        self.data_packet_mode = "full"  # "full" 或 "compact"
        self.send_frequency = 50  # Hz
        
        # 兼容性常量
        self.ground_header = self.UP_HEADER
        self.ground_footer = self.UP_TAIL
        self.aircraft_header = self.DOWN_HEADER
        self.aircraft_footer = self.DOWN_TAIL
        self.cmd_on = 0x01
        self.cmd_off = 0x00
        self.cmd_unlock = 0x02
        
        # 接收缓冲区
        self.receive_buffer = bytearray()
    
  
    def encode_up_frame(self, switch_cmd, fan_rpm, servo_angles):
        """
        编码上行数据包（地面站 → 制导镖）
        完全匹配C结构定义：header + switch_cmd + fan_rpm + servo[4] + tail
        Args:
            switch_cmd: int 总开关 (0=关, 1=开, 2=特殊模式) 
            fan_rpm: int 风扇转速 (0-1000)
            servo_angles: list 4个舵机角度 [0-180, 0-180, 0-180, 0-180]
        Returns:
            bytes: 14字节数据包
        """
        try:
            # 将浮点数转换为整数以匹配struct格式
            fan_rpm_int = int(fan_rpm)  # 转换为整数
            servo_angles_int = [int(angle) for angle in servo_angles]  # 转换为整数列表
            
            # 使用小端序打包数据（不包括CRC）
            packet_without_crc = struct.pack('<B B h 4h B',
                                self.UP_HEADER,    # 0xAA
                                switch_cmd,        # 总开关
                                fan_rpm_int,       # 风扇转速（已转换为整数）
                                servo_angles_int[0],   # 舵机1角度（已转换为整数）
                                servo_angles_int[1],   # 舵机2角度（已转换为整数）
                                servo_angles_int[2],   # 舵机3角度（已转换为整数）
                                servo_angles_int[3],   # 舵机4角度（已转换为整数）
                                self.UP_TAIL)      # 0xBB
            
            return packet_without_crc
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
        while len(self.receive_buffer) >= self.DOWN_FRAME_SZ:
            # 查找包头
            header_pos = -1
            for i in range(len(self.receive_buffer) - self.DOWN_FRAME_SZ + 1):
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
        完全匹配C结构定义：header + last_switch + gyro[9] + tail 
        Args:
            data: bytes 接收到的数据
        Returns:
            dict: 包含last_switch和gyro数据的字典，或None
        """
        if len(data) != self.DOWN_FRAME_SZ:
            return None
        
        try:
            # 解析39字节数据包
            # header(1) + last_switch(1) + gyro[9](36) + tail(1) = 39
            # 格式：1字节header + 1字节last_switch + 9个float(每个4字节) + 1字节tail
            header, last_switch, gx, gy, gz, ax, ay, az, mx, my, mz, tail = \
                struct.unpack('<B B 9f B', data)
            
            # 验证包头包尾
            if header != self.DOWN_HEADER or tail != self.DOWN_TAIL:
                return None
            
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
