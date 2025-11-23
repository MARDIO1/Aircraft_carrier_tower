import struct

class Protocol:
    def __init__(self):
        self.ground_header = 0xAA
        self.ground_footer = 0xBB
        self.aircraft_header = 0xCC
        self.aircraft_footer = 0xDD
    
    def encode_ground_data(self, throttle, control_surfaces):
        """编码地面站发送数据
        Args:
            throttle: float 油门值
            control_surfaces: list[float] 4个舵面角度值
        Returns:
            bytes: 编码后的数据包
        """
        if len(control_surfaces) != 4:
            raise ValueError("control_surfaces must contain exactly 4 values")
        
        data = struct.pack('f', throttle)
        for surface in control_surfaces:
            data += struct.pack('f', surface)
        
        packet = bytes([self.ground_header]) + data + bytes([self.ground_footer])
        return packet
    
    def decode_ground_data(self, data):
        """解码地面站接收数据
        Args:
            data: bytes 接收到的数据
        Returns:
            tuple: (throttle, control_surfaces) 或 None
        """
        expected_length = 1 + 5*4 + 1  # header + 5 floats + footer
        if len(data) != expected_length:
            return None
        
        if data[0] != self.ground_header or data[-1] != self.ground_footer:
            return None
        
        throttle = struct.unpack('f', data[1:5])[0]
        control_surfaces = [
            struct.unpack('f', data[5:9])[0],
            struct.unpack('f', data[9:13])[0],
            struct.unpack('f', data[13:17])[0],
            struct.unpack('f', data[17:21])[0]
        ]
        
        return throttle, control_surfaces
    
    def encode_aircraft_data(self, custom_data):
        """编码航模发送数据
        Args:
            custom_data: int 自定义数据
        Returns:
            bytes: 编码后的数据包
        """
        data = struct.pack('i', custom_data)
        packet = bytes([self.aircraft_header]) + data + bytes([self.aircraft_footer])
        return packet
    
    def decode_aircraft_data(self, data):
        """解码航模接收数据
        Args:
            data: bytes 接收到的数据
        Returns:
            int: 自定义数据 或 None
        """
        if len(data) != 1 + 4 + 1:  # header + 1 int + footer
            return None
        
        if data[0] != self.aircraft_header or data[-1] != self.aircraft_footer:
            return None
        
        custom_data = struct.unpack('i', data[1:5])[0]
        return custom_data
