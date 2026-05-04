"""
黑箱数据记录器
用于记录接收到的BlackBox数据到CSV文件
"""

import csv
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional
from protocol import ProtocolData


class BlackBoxLogger:
    """BlackBox数据记录器"""
    
    def __init__(self, max_records: int =3000, log_dir: str = "blackbox_logs"):
        """
        初始化记录器
        
        Args:
            max_records: 最大记录条数，达到后自动停止
            log_dir: 日志文件存储目录
        """
        self.max_records = max_records
        self.record_count = 0
        self.is_logging = False
        self.log_file = None
        self.csv_writer = None
        self.log_dir = log_dir
        self._last_timestamp = -1
        self.seen_timestamps = set()

        # 确保日志目录存在
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
    
    def start_logging(self) -> bool:
        """
        开始记录（进入DATA模式时自动调用）
        
        Returns:
            bool: 是否成功开始记录
        """
        if self.is_logging:
            return False  # 已经在记录中
            
        try:
            # 创建新的日志文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"blackbox_{timestamp}.csv"
            filepath = os.path.join(self.log_dir, filename)
            
            self.log_file = open(filepath, 'w', newline='', encoding='utf-8')
            self.csv_writer = csv.writer(self.log_file)
            
            # 写入CSV标题行 - 列顺序与 log_data() 中 row 的写入顺序严格对应
            # packet_timestamp  → blackbox_timestamp  （主时间戳，row 第0列）
            # packet_timestamp2 → blackbox_timestamp2 （第二时间戳，row 第1列）
            headers = [
                'packet_timestamp',   # 数据包主时间戳（blackbox_timestamp，4字节无符号整数）
                'packet_timestamp2',  # 第二时间戳（blackbox_timestamp2）
                'statemachine',
                'angle_roll', 'angle_pitch', 'angle_yaw',
                'gyro_x', 'gyro_y', 'gyro_z',
                'acc_x', 'acc_y', 'acc_z',
                'torque_x','torque_y','torque_z',
                'rudder1', 'rudder2', 'rudder3', 'rudder4'
            ]
            self.csv_writer.writerow(headers)

            self.record_count = 0
            self._last_timestamp = -1
            self.seen_timestamps.clear()
            self.is_logging = True

            print(f"开始黑箱记录: {filename}")
            print(f"最大记录条数: {self.max_records}")
            return True
            
        except Exception as e:
            print(f"开始记录失败: {e}")
            self._cleanup()
            return False
    
    def stop_logging(self) -> bool:
        """
        停止记录
        
        Returns:
            bool: 是否成功停止记录
        """
        if not self.is_logging:
            return False  # 不在记录中
            
        try:
            self._cleanup()
            self.is_logging = False
            print(f"停止黑箱记录，共记录{self.record_count}条数据")
            return True
            
        except Exception as e:
            print(f"停止记录失败: {e}")
            return False
    
    def toggle_logging(self) -> bool:
        """
        切换记录状态（L键功能）
        
        Returns:
            bool: 切换后的记录状态（True=正在记录，False=已停止）
        """
        if self.is_logging:
            self.stop_logging()
            return False
        else:
            self.start_logging()
            return True
    
    def log_data(self, timestamp: float, protocol_data: ProtocolData) -> bool:
        """
        记录一条BlackBox数据
        
        Args:
            timestamp: 时间戳（秒）- 保留参数用于向后兼容，但不再使用
            protocol_data: 协议数据对象，包含数据包时间戳
            
        Returns:
            bool: 是否成功记录
        """
        if not self.is_logging:
            return False  # 未在记录中，静默返回
        if self.record_count >= self.max_records:
            return False  # 已达上限，静默返回（stop_logging 已在达到上限时打印过提示）
            
        try:
            # 记录数据包时间戳（4字节无符号整数）
            packet_timestamp = protocol_data.blackbox_timestamp

            # timestamp循环检测：飞控可能会循环发送整个BlackBox的记录，如果发现当前时间戳在本次记录中已存在，则代表一个周期接收完毕。
            if packet_timestamp in self.seen_timestamps:
                print(f"检测到循环timestamp {packet_timestamp}（已接收过），智能截断，自动停止记录CSV！")
                self.stop_logging()
                return False
            
            self.seen_timestamps.add(packet_timestamp)
            self._last_timestamp = packet_timestamp

            # 准备数据行，精度小数点后三位 - 只记录59字节数据包中实际包 含的数据
            row = [
                str(packet_timestamp),  # 数据包时间戳（原始整数值）
                str(protocol_data.blackbox_timestamp2),
                str(protocol_data.blackbox_statemachine),
                f"{protocol_data.blackbox_angle[0]:.3f}",
                f"{protocol_data.blackbox_angle[1]:.3f}",
                f"{protocol_data.blackbox_angle[2]:.3f}",
                f"{protocol_data.blackbox_gyro[0]:.3f}",
                f"{protocol_data.blackbox_gyro[1]:.3f}",
                f"{protocol_data.blackbox_gyro[2]:.3f}",
                f"{protocol_data.blackbox_acc[0]:.3f}",
                f"{protocol_data.blackbox_acc[1]:.3f}",
                f"{protocol_data.blackbox_acc[2]:.3f}",
                f"{protocol_data.blackbox_torque[0]:.3f}",
                f"{protocol_data.blackbox_torque[1]:.3f}",
                f"{protocol_data.blackbox_torque[2]:.3f}",
                f"{protocol_data.blackbox_rudder[0]:.3f}",
                f"{protocol_data.blackbox_rudder[1]:.3f}",
                f"{protocol_data.blackbox_rudder[2]:.3f}",
                f"{protocol_data.blackbox_rudder[3]:.3f}"
            ]
            
            # 写入CSV
            self.csv_writer.writerow(row)
            
            # 立即flush确保数据写入磁盘
            if self.log_file:
                self.log_file.flush()
            
            self.record_count += 1
            
            # 调试信息
            if self.record_count % 100 == 0:
                print(f"已记录 {self.record_count} 条数据到CSV")
            
            # 检查是否达到上限
            if self.record_count >= self.max_records:
                print(f"已达到最大记录条数({self.max_records})，自动停止记录")
                self.stop_logging()
                return False
                
            return True
            
        except Exception as e:
            print(f"记录数据失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取记录器状态
        
        Returns:
            Dict: 包含记录状态的字典
        """
        return {
            'is_logging': self.is_logging,
            'record_count': self.record_count,
            'max_records': self.max_records,
            'remaining': self.max_records - self.record_count if self.is_logging else 0
        }
    
    def _cleanup(self):
        """清理资源"""
        if self.log_file:
            try:
                self.log_file.flush()
                self.log_file.close()
                print(f"文件已关闭: {self.log_file.name}")
            except Exception as e:
                print(f"关闭文件时出错: {e}")
            finally:
                self.log_file = None
                self.csv_writer = None
    
    def __del__(self):
        """析构函数，确保文件关闭"""
        self._cleanup()


# 测试函数
def test_blackbox_logger():
    """测试黑箱记录器"""
    print("测试BlackBoxLogger...")
    
    logger = BlackBoxLogger(max_records=5)  # 测试用5条
    
    # 测试开始记录
    if logger.start_logging():
        print("✓ 开始记录成功")
    else:
        print("✗ 开始记录失败")
    
    # 创建测试数据
    test_data = ProtocolData()
    test_data.blackbox_timestamp = 1234567890  # 测试数据包时间戳
    test_data.blackbox_angle = [1.234567, 2.345678, 3.456789]
    test_data.blackbox_gyro = [4.567890, 5.678901, 6.789012]
    test_data.blackbox_acc = [7.890123, 8.901234, 9.012345]
    test_data.blackbox_rudder = [16.789012, 17.890123, 18.901234, 19.012345]
    
    # 记录测试数据
    for i in range(6):  # 尝试记录6条，应该在第5条后自动停止
        success = logger.log_data(time.time() + i, test_data)
        status = logger.get_status()
        print(f"记录第{i+1}条: {'成功' if success else '失败'}, 状态: {status}")
    
    # 测试停止
    logger.stop_logging()
    print("测试完成")


if __name__ == "__main__":
    test_blackbox_logger()
