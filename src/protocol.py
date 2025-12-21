"""
串口通讯协议配置 - 状态机版本
定义地面站与航模之间的数据格式，支持状态机架构
"""

import struct
import time
from enum import Enum
from typing import Optional, List, Tuple, Dict, Any

# ==================== 状态机定义 ====================

class MainState(Enum):
    """主状态枚举"""
    STOP = 0x00      # 停止状态
    AUTO = 0x01      # 自动控制
    TOWER = 0x02     # 塔台控制
    TUNING = 0x03    # 调参模式

class SubState(Enum):
    """子状态枚举（仅用于TUNING模式）"""
    SERVO = 0xA1     # 舵机调参
    PID = 0xA2       # PID调参
    JACOBIAN = 0xA3  # 雅可比矩阵调参

# ==================== 状态转换验证 ====================

class StateTransitionValidator:
    """状态转换验证器"""
    
    @staticmethod
    def can_transition(from_state: MainState, to_state: MainState) -> bool:
        """
        验证主状态转换是否允许
        
        规则：
        1. 所有状态都可以切换到STOP
        2. 只能从STOP切换到TUNING
        3. TUNING可以切换到所有状态
        4. AUTO和TOWER之间可以互相切换
        """
        if to_state == MainState.STOP:
            return True  # 所有状态都可以切换到STOP
        
        if from_state == MainState.STOP:
            return True  # STOP可以切换到任何状态
        
        if from_state == MainState.TUNING:
            return True  # TUNING可以切换到任何状态
        
        # AUTO和TOWER之间可以互相切换
        if from_state in [MainState.AUTO, MainState.TOWER] and to_state in [MainState.AUTO, MainState.TOWER]:
            return True
        
        return False
    
    @staticmethod
    def validate_transition(from_state: MainState, to_state: MainState) -> bool:
        """验证并执行状态转换"""
        if StateTransitionValidator.can_transition(from_state, to_state):
            return True
        else:
            print(f"状态转换错误: 无法从 {from_state.name} 切换到 {to_state.name}")
            return False

# ==================== 编码器基类 ====================

class EncoderBase:
    """编码器基类"""
    
    def encode(self, data: 'ProtocolData') -> Optional[bytearray]:
        """编码数据，返回字节数组或None"""
        raise NotImplementedError("子类必须实现encode方法")
    
    def get_packet_length(self) -> int:
        """返回数据包长度"""
        raise NotImplementedError("子类必须实现get_packet_length方法")

# ==================== 具体编码器实现 ====================

class StopEncoder(EncoderBase):
    """STOP状态编码器"""
    
    def encode(self, data: 'ProtocolData') -> Optional[bytearray]:
        """编码STOP状态数据：0xAA + 0x00 + 0xBB (3字节)"""
        packet = bytearray()
        packet.append(0xAA)  # START_BYTE
        packet.append(0x00)  # STOP状态
        packet.append(0xBB)  # END_BYTE
        return packet
    
    def get_packet_length(self) -> int:
        return 3

class AutoEncoder(EncoderBase):
    """AUTO状态编码器"""
    
    def encode(self, data: 'ProtocolData') -> Optional[bytearray]:
        """编码AUTO状态数据：0xAA + uint8[1] + int16[1] + float32[4] + 0xBB (21字节)"""
        packet = bytearray()
        packet.append(0xAA)  # START_BYTE
        packet.append(data.main_switch & 0xFF)
        packet.extend(struct.pack('<h', data.fan_speed))
        
        for angle in data.servo_angles:
            packet.extend(struct.pack('<f', float(angle)))
        
        packet.append(0xBB)  # END_BYTE
        return packet
    
    def get_packet_length(self) -> int:
        return 21

class TowerEncoder(EncoderBase):
    """TOWER状态编码器"""
    
    def encode(self, data: 'ProtocolData') -> Optional[bytearray]:
        """编码TOWER状态数据：0xAA + uint8[1] + int16[1] + float32[4] + 0xBB (21字节)"""
        packet = bytearray()
        packet.append(0xAA)  # START_BYTE
        packet.append(data.main_switch & 0xFF)
        packet.extend(struct.pack('<h', data.fan_speed))
        
        for angle in data.servo_angles:
            packet.extend(struct.pack('<f', float(angle)))
        
        packet.append(0xBB)  # END_BYTE
        return packet
    
    def get_packet_length(self) -> int:
        return 21

class ServoEncoder(EncoderBase):
    """SERVO调参编码器"""
    
    def encode(self, data: 'ProtocolData') -> Optional[bytearray]:
        """编码SERVO调参数据：  0xAA + 0xA1 + float[4] + 0xBB (19字节)"""
        packet = bytearray()
       
        packet.append(0xAA)  # START_BYTE
        packet.append(0xA1)  # SERVO子状态
        
        for angle in data.servo_angles:
            packet.extend(struct.pack('<f', float(angle)))
        
        packet.append(0xBB)  # END_BYTE
        return packet
    
    def get_packet_length(self) -> int:
        return 19

class PIDEncoder(EncoderBase):
    """PID调参编码器"""
    
    def encode(self, data: 'ProtocolData') -> Optional[bytearray]:
        """编码PID调参数据：  0xAA + 0xA2 + pid_index + float[6] + 0xBB"""
        if data.selected_pid < 0 or data.selected_pid >= len(data.pid_param):
            print(f"错误：PID索引{data.selected_pid}超出范围(0-{len(data.pid_param)-1})")
            return None
        
        packet = bytearray()
       
        packet.append(0xAA)  # START_BYTE
        packet.append(0xA2)  # PID子状态
        packet.append(data.selected_pid & 0xFF)  # PID索引 (0-6)
        
        # 发送选中的PID参数组（6个参数）
        for param_value in data.pid_param[data.selected_pid]:
            packet.extend(struct.pack('<f', float(param_value)))
        
        packet.append(0xBB)  # END_BYTE
        return packet
    
    def get_packet_length(self) -> int:
        return 1 + 1 + 1 + 6*4 + 1  # 0xAA + 0xA2 + pid_index + 6*float + 0xBB

class JacobianEncoder(EncoderBase):
    """Jacobian调参编码器"""
    
    def encode(self, data: 'ProtocolData') -> Optional[bytearray]:
        """编码Jacobian调参数据：0xAA + 0xA3 + float[3][4] + 0xBB"""
        packet = bytearray()
        
        packet.append(0xAA)  # START_BYTE
        packet.append(0xA3)  # JACOBIAN标记
        
        # 发送3x4矩阵
        for row in data.jacobian_matrix:
            for value in row:
                packet.extend(struct.pack('<f', float(value)))
        
        packet.append(0xBB)  # END_BYTE
        return packet
    
    def get_packet_length(self) -> int:
        return 1 + 1 + 3*4*4 + 1  # 0xAA + 0xA3 + 12*float + 0xBB

# ==================== 编码器工厂 ====================

class EncoderFactory:
    """编码器工厂，根据状态创建对应的编码器"""
    
    _encoders = {
        MainState.STOP: StopEncoder(),
        MainState.AUTO: AutoEncoder(),
        MainState.TOWER: TowerEncoder(),
        SubState.SERVO: ServoEncoder(),
        SubState.PID: PIDEncoder(),
        SubState.JACOBIAN: JacobianEncoder(),
    }
    
    @staticmethod
    def get_encoder(state: Any) -> Optional[EncoderBase]:
        """获取状态对应的编码器"""
        return EncoderFactory._encoders.get(state)

# ==================== 协议数据结构 ====================

class ProtocolData:
    """协议数据结构，线程间共享"""
    
    def __init__(self):
        # 主状态和子状态
        self.main_state = MainState.STOP
        self.sub_state = SubState.SERVO
        
        # 控制参数
        self.main_switch = 0  # 总开关: 0=STOP, 1=AUTO, 2=TOWER
        self.fan_speed = 0    # 风扇转速
        self.servo_angles = [0.0, 0.0, 0.0, 0.0]  # 4个舵机角度
        
        # 调参参数
        self.selected_pid = 0  # 当前选中的PID索引
        self.selected_param = 0  # 当前选中的参数索引
        self.pid_param = [
            # 内环主翼，内环尾翼
            [9.0, 0.0, 0.0, 0.0, 35.0, -35.0],  # 内环主翼
            [9.0, 0.0, 0.0, 0.0, 35.0, -35.0],  # 内环尾翼
            # 姿态环：roll, pitch, yaw
            [0.1, 0.0, 0.0, 0.0, 5.0, -5.0],    # roll
            [0.1, 0.0, 0.0, 0.0, 5.0, -5.0],    # pitch
            [1.0, 0.0, 0.0, 0.0, 5.0, -5.0],    # yaw
            # 外环
            [9.0, 0.0, 0.0, 0.0, 35.0, -35.0],  # 外环方向yaw
            [9.0, 0.0, 0.0, 0.0, 35.0, -35.0],  # 外环高度
        ]
        
        # PID名称映射
        self.pid_name = [
            "内环主翼",      # 0
            "内环尾翼",      # 1
            "姿态环-roll",   # 2
            "姿态环-pitch",  # 3
            "姿态环-yaw",    # 4
            "外环-yaw",      # 5
            "外环-高度",     # 6
        ]
        
        # 参数名称映射
        self.param_names = ["kp", "ki", "kd", "积分限幅", "正输出限幅", "负输出限幅"]
        
        # Jacobian矩阵
        self.jacobian_matrix = [
            [0.0, 0.0, 0.0, 0.0],  # 第1行
            [0.0, 0.0, 0.0, 0.0],  # 第2行
            [0.0, 0.0, 0.0, 0.0]   # 第3行
        ]
        
        # 导航状态
        self.nav_row = 0  # 当前导航行
        self.nav_col = 0  # 当前导航列
        self.nav_confirm = False  # 是否已确认
        
        # 接收数据
        self.received_switch = 0
        self.received_angle_roll = 0.0
        self.received_angle_pitch = 0.0
        self.received_angle_yaw = 0.0
        self.last_received_time = None
    
    def set_main_state(self, new_state: MainState) -> bool:
        """设置主状态，验证转换规则"""
        if StateTransitionValidator.validate_transition(self.main_state, new_state):
            self.main_state = new_state
            return True
        return False
    
    def set_sub_state(self, new_state: SubState) -> None:
        """设置子状态（仅用于TUNING模式）"""
        if self.main_state == MainState.TUNING:
            self.sub_state = new_state
    
    def get_current_encoder(self) -> Optional[EncoderBase]:
        """获取当前状态对应的编码器"""
        if self.main_state == MainState.TUNING:
            return EncoderFactory.get_encoder(self.sub_state)
        else:
            return EncoderFactory.get_encoder(self.main_state)

# ==================== 向后兼容函数 ====================

def encode_data(data: ProtocolData) -> Optional[bytearray]:
    """
    向后兼容的编码函数
    使用状态机架构编码数据
    """
    encoder = data.get_current_encoder()
    if encoder:
        return encoder.encode(data)
    return None



def decode_data(packet: bytearray) -> Optional[ProtocolData]:
    """
    解码从航模接收到的数据包
    格式: 0xCC + uint8开关 + float[3]角度 + 0xDD (15字节)
    """
    if len(packet) != 15:
        return None
    
    if packet[0] != 0xCC or packet[-1] != 0xDD:
        return None
    
    data = ProtocolData()
    
    try:
        data.received_switch = packet[1]
        data.received_angle_roll, data.received_angle_pitch, data.received_angle_yaw = struct.unpack('<fff', packet[2:14])
        data.last_received_time = time.time()
        return data
    except Exception as e:
        print(f"数据解码错误: {e}")
        return None

# ==================== 状态机管理类 ====================

class StateMachineManager:
    """状态机管理器"""
    
    def __init__(self, protocol_data: ProtocolData):
        self.data = protocol_data
        
        # 导航配置
        self.nav_config = {
            MainState.STOP: {
                'rows': 3,  # 行数：AUTO、TOWER、TUNING三个选项
                'cols': 1,  # 列数：一维数组
                'labels': ['切换到AUTO模式', '切换到TOWER模式', '切换到TUNING模式'],
                'target_states': [MainState.AUTO, MainState.TOWER, MainState.TUNING]
            },
            MainState.AUTO: {
                'rows': 2,  # 行数：状态行 + 参数行
                'cols': 4,  # 列数：开关、风扇、舵机1-4
                'labels': ['开关', '风扇', '舵机1', '舵机2', '舵机3', '舵机4'],
                'target_states': None
            },
            MainState.TOWER: {
                'rows': 2,
                'cols': 4,
                'labels': ['开关', '风扇', '舵机1', '舵机2', '舵机3', '舵机4'],
                'target_states': None
            },
            MainState.TUNING: {
                'rows': 3,  # 行数：子模式选择 + 参数选择 + 数值输入
                'cols': 1,  # 列数：一维数组
                'labels': ['舵机调参', 'PID调参', 'Jacobian调参'],
                'target_states': [SubState.SERVO, SubState.PID, SubState.JACOBIAN]
            }
        }
    
    def get_nav_info(self) -> Dict[str, Any]:
        """获取当前导航信息"""
        if self.data.main_state not in self.nav_config:
            return {'rows': 0, 'cols': 0, 'labels': [], 'row': 0, 'col': 0}
        
        config = self.nav_config[self.data.main_state]
        return {
            'rows': config['rows'],
            'cols': config['cols'],
            'labels': config['labels'],
            'row': self.data.nav_row,
            'col': self.data.nav_col,
            'confirm': self.data.nav_confirm
        }
    
    def navigate_up(self) -> None:
        """向上导航"""
        if self.data.main_state in self.nav_config:
            config = self.nav_config[self.data.main_state]
            if self.data.nav_row > 0:
                self.data.nav_row -= 1
    
    def navigate_down(self) -> None:
        """向下导航"""
        if self.data.main_state in self.nav_config:
            config = self.nav_config[self.data.main_state]
            if self.data.nav_row < config['rows'] - 1:
                self.data.nav_row += 1
    
    def navigate_left(self) -> None:
        """向左导航"""
        if self.data.main_state in self.nav_config:
            config = self.nav_config[self.data.main_state]
            if self.data.nav_col > 0:
                self.data.nav_col -= 1
    
    def navigate_right(self) -> None:
        """向右导航"""
        if self.data.main_state in self.nav_config:
            config = self.nav_config[self.data.main_state]
            if self.data.nav_col < config['cols'] - 1:
                self.data.nav_col += 1
    
    def toggle_confirm(self) -> None:
        """切换确认状态"""
        self.data.nav_confirm = not self.data.nav_confirm
    
    def handle_enter(self) -> bool:
        """处理Enter键，返回是否状态改变"""
        if self.data.main_state == MainState.STOP:
            # 在STOP状态下，Enter用于切换到选中的状态
            config = self.nav_config[MainState.STOP]
            if 0 <= self.data.nav_row < len(config['target_states']):
                target_state = config['target_states'][self.data.nav_row]
                if self.data.set_main_state(target_state):
                    # 重置导航位置
                    self.data.nav_row = 0
                    self.data.nav_col = 0
                    self.data.nav_confirm = False
                    return True
            return False
        elif self.data.main_state == MainState.TUNING:
            # 在TUNING模式下，Enter用于选择子模式
            if self.data.nav_row == 0:
                self.data.set_sub_state(SubState.SERVO)
            elif self.data.nav_row == 1:
                self.data.set_sub_state(SubState.PID)
            elif self.data.nav_row == 2:
                self.data.set_sub_state(SubState.JACOBIAN)
            return True
        else:
            # 在其他模式下，Enter用于确认导航位置
            self.toggle_confirm()
            return False
    
    def handle_number_input(self, number: int) -> None:
        """处理数字输入"""
        if self.data.main_state == MainState.TUNING:
            if self.data.sub_state == SubState.PID:
                # 在PID调参模式下，数字用于选择参数
                if 0 <= number < len(self.data.pid_param[0]):
                    self.data.selected_param = number
            elif self.data.sub_state == SubState.JACOBIAN:
                # 在Jacobian调参模式下，数字用于输入矩阵值
                row = self.data.nav_row
                col = self.data.nav_col
                if 0 <= row < 3 and 0 <= col < 4:
                    self.data.jacobian_matrix[row][col] = float(number)
        else:
            # 在其他模式下，数字用于设置参数值
            if self.data.nav_col == 0:  # 开关
                self.data.main_switch = number
            elif self.data.nav_col == 1:  # 风扇
                self.data.fan_speed = number
            elif 2 <= self.data.nav_col <= 5:  # 舵机
                servo_index = self.data.nav_col - 2
                self.data.servo_angles[servo_index] = float(number)
    
    def get_current_selection(self) -> str:
        """获取当前选择的项目描述"""
        if self.data.main_state not in self.nav_config:
            return "无导航"
        
        config = self.nav_config[self.data.main_state]
        if self.data.main_state == MainState.TUNING:
            if self.data.nav_row == 0:
                return "舵机调参模式"
            elif self.data.nav_row == 1:
                return f"PID调参: {self.data.pid_name[self.data.selected_pid]}"
            elif self.data.nav_row == 2:
                return f"Jacobian调参: 行{self.data.nav_row},列{self.data.nav_col}"
        else:
            label_index = self.data.nav_row * config['cols'] + self.data.nav_col
            if label_index < len(config['labels']):
                return config['labels'][label_index]
        
        return "未知选择"
