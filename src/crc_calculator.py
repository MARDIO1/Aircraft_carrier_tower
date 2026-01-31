'''
crc_calculator 是适配stm32 F411硬件crc计算的模块
提供通用的crc321计算模块并支持各种数据包格式
'''
import struct
from typing import Union,Optional

class STM32F411CRC:
    '''
    STM32 F411硬件CRC模拟器
    固定参数：
    - 多项式: 0x04C11DB7 (CRC-32/Ethernet)
    - 初值: 0xFFFFFFFF
    - 结果异或: 0x00000000
    - 无输入/输出位反转
    '''
    #CRC32多项式 (0x04C11DB7)
    POLY =  0x04C11DB7

    @staticmethod
    def _crc32_word(crc:int,word:int)->int:
        """计算单个32位字的crc"""
        crc ^= word
        for _ in range(32):
            if crc & 0x80000000:
                crc = ((crc << 1) ^ STM32F411CRC.POLY) & 0XFFFFFFFF
            else:
                crc = (crc << 1) & 0xFFFFFFFF
        return crc
    @staticmethod
    def crc32(data: Union[bytes, bytearray]) -> int:
        """
        crc32 
        
        args:
            data:输入数据(字节序列)
        Returns:
            int :32位crc值
        notes:
            数据自动补0x00到4字节补齐
            按小端序读取

        """
        if not data:
            return 0xFFFFFFFF
        #   转化为字节数组
        if isinstance(data,bytearray):
            data_bytes = bytes(data)
        else:
            data_bytes =data

        # 补0x00到4字节对齐
        padding_len = (4-(len(data_bytes) % 4)) %4
        padded_data = data_bytes + b'\x00' * padding_len

        #初始化CRC
        crc = 0XFFFFFFFF

        #按四字节步进处理
        for i in range(0,len(padded_data),4):
            #小端序读取32位
            chunk = padded_data[i:i+4]
            word = struct.unpack('<I',chunk)[0] #<小端序

            #计算crc
            crc = STM32F411CRC._crc32_word(crc,word)
        return crc
    @staticmethod
    def crc8(data:Union[bytes,bytearray]) -> int:
        """
        crc8 的 Docstring
        
        data: 输入数据（字节序列）
        
        return: int :8位crc(0~255)
        
        """
        crc32_value = STM32F411CRC.crc32(data)
        return crc32_value & 0xFF
     # ==================== 发送端功能 ====================
    @staticmethod
    def add_crc8_to_packet(packet: bytearray,
                          calc_start:int = 0,
                          calc_end: int = -1) -> bytearray:
        """
      安全版:为数据包添加CRC8(使用固定偏移量)
        
        Args:
            packet: 原始数据包（字节数组）
            calc_start: CRC计算起始索引(包含)
            calc_end: CRC计算结束索引(不包含),-1表示到packet末尾
            
        Returns:
            bytearray: 添加了CRC8的新数据包
            
        Note:
            - 使用固定索引而非动态搜索，避免"范围漂移"
            - CRC8插入位置:calc_end索引处
            - 数据包结构：[Header...Data][CRC8][End]
        """
        if calc_end == -1:
            calc_end = len(packet)- 1

        #提取计算crc数据
        data_to_calculate = packet[calc_start:calc_end]

        #计算crc8
        crc8_value = STM32F411CRC.crc8(data_to_calculate)

        new_packet = packet[:calc_end] + bytes([crc8_value]) + packet[calc_end:]
        return  new_packet
    @staticmethod
    def add_crc32_to_packet(packet: bytearray,
                           calc_start: int = 0,
                           calc_end: int = -1) -> bytearray:
        """
        高安全性版为数据包添加完整的CRC324字节
        
        Args:
            packet: 原始数据包（字节数组）
            calc_start: CRC计算起始索引包含
            calc_end: CRC计算结束索引不包含
            
        Returns:
            bytearray: 添加了CRC32的新数据包
            
        Note:
            - 使用完整的32位CRC安全性从1/256提升到1/4,294,967,296
            - 数据包结构：[Header...Data][CRC32(4字节)][End]
        """
        # 确定计算范围
        if calc_end == -1:
            calc_end = len(packet) - 1
        
        # 提取计算CRC的数据
        data_to_calculate = packet[calc_start:calc_end]
        
        # 计算完整的CRC32
        crc32_value = STM32F411CRC.crc32(data_to_calculate)
        
        # 将CRC32转换为4字节（小端序）
        crc32_bytes = struct.pack('<I', crc32_value)
        
        # 在calc_end位置插入CRC32
        new_packet = packet[:calc_end] + crc32_bytes + packet[calc_end:]
        
        return new_packet
    # ==================== 接收端功能 ====================
    @staticmethod
    def verify_crc8(packet:bytearray,crc_position:int = -2,calc_start:int = 0)-> bool:
        """
       接收端:验证数据包的CRC8
        
        Args:
            packet: 完整数据包包含CRC和帧尾
            crc_position: CRC字节在packet中的位置默认倒数第二个
            calc_start: CRC计算起始索引默认0即帧头开始
            
        Returns:
            bool: CRC验证是否通过
            
        Note:
            - 计算数据packet[calc_start:crc_position]不含CRC字节
            - 对比计算出的CRC8 vs packet[crc_position]
        """
        #防御性检查
        if len(packet) <= abs(crc_position):
            return False
        #提取到接收到的crc
        received_crc = packet[crc_position]

        #提取计算中数据
        data_to_calculated =packet[calc_start:crc_position]

        #计算crc
        calculated_crc = STM32F411CRC.crc8(data_to_calculated)
        return calculated_crc == received_crc
    @staticmethod
    def extract_payload(packet:bytearray, header_byte: int = 0xAA, crc_position: int = -2, end_byte: int =0xBB)->Optional[bytes]:
        """
        接收端:从完整数据包中提取有效载荷(通过CRC验证后)
        
        Args:
            packet: 完整数据包
            header_byte: 帧头字节
            crc_position: CRC字节位置
            end_byte: 帧尾字节
            
        Returns:
            Optional[bytes]: 提取的载荷数据,如果验证失败返回None
        """
        if len(packet) < 4:
            return None
        if packet[0] != header_byte or packet[-1] !=end_byte:
            return None
        if not STM32F411CRC.verify_crc8(packet,crc_position=crc_position,calc_start=0):
            return None
        
        payload = packet[1:crc_position]

        return bytes(payload)


def add_crc8_to_packet(packet:bytearray, calc_start:int=0, calc_end:int=-1)->bytearray:
    return STM32F411CRC.add_crc8_to_packet(packet,calc_start,calc_end)
        
def verify_crc8(packet: bytearray, crc_position: int = -2, calc_start: int = 0) -> bool:
    """接收端:验证数据包的CRC8"""
    return STM32F411CRC.verify_crc8(packet, crc_position, calc_start)

def extract_payload_with_crc(packet: bytearray,
                           header_byte: Optional[int] = None,
                           crc_position: int = -2,
                           end_byte: int = 0xBB) -> Optional[bytes]:
    """接收端:从完整数据包中提取有效载荷(通过CRC验证)"""
    return STM32F411CRC.extract_payload(packet, header_byte,  crc_position, end_byte)
    

    
 

 



















