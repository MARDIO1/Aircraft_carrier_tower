"""
串口接收模块
负责从航模接收数据并解码
"""

import threading
import time
import struct
import serial
import serial.tools.list_ports
from typing import Optional
from protocol import SAVE_TO_FLASH_ACK, decode_data, MainState, verify_crc8
from blackbox_logger import BlackBoxLogger

# 串口断线重连配置
_RECONNECT_INTERVAL = 1.0   # 每次重连尝试间隔（秒）
_RECONNECT_MAX_TRIES = 30   # 最多重试次数
_CH340_SCAN_INTERVAL = 2.0  # CH340 重新扫描间隔（秒）

class UARTReceiver:
    def __init__(self, serial_port, shared_data):
        """
        初始化串口接收器
        Args:
            serial_port: 串口对象
            shared_data: 线程间共享的数据对象 (ProtocolData)
        """
        self.serial_port = serial_port
        self.shared_data = shared_data
        self.running = False
        self.receive_thread = None
        self.receive_buffer = bytearray()
        self.last_receive_time = None
        self.receive_count = 0
        self.error_count = 0
        self._last_rx_packet: Optional[bytes] = None  # AIchange: 缓存最近一次完整76字节帧用于前端hex显示
        self._auto_keyword = "CH340"
        self._initializer_ref = None
        
        # 初始化黑箱记录器
        self.blackbox_logger = BlackBoxLogger(max_records=3000)

    def set_initializer(self, initializer):
        """设置 Initializer 引用，用于动态扫描 CH340 端口"""
        self._initializer_ref = initializer
        
    def start_receiving(self):
        """开始接收数据"""
        if self.running:
            return
            
        self.running = True
        self.receive_thread = threading.Thread(target=self._receive_loop)
        self.receive_thread.daemon = True
        self.receive_thread.start()
        print("串口数据接收已启动")
        
    def stop_receiving(self):
        """停止接收数据"""
        self.running = False
        if self.receive_thread:
            self.receive_thread.join(timeout=1.0)
        print("串口数据接收已停止")
        
    def _receive_loop(self):
        """数据接收循环（带断线自动重连）"""
        last_scan_time = 0.0
        
        while self.running:
            # ── 串口可用性检查 ──
            if not (self.serial_port and self.serial_port.is_open):
                if not self._try_reconnect():
                    print("接收线程：串口重连失败次数已达上限，退出")
                    self.running = False
                    break
                continue
                
            try:
                # 读取可用数据
                if self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    self._process_received_data(data)
                
                # 控制接收频率
                time.sleep(0.001)  # 低延迟轮询，支持 TOWER/DATA 实时黑箱回传
                
            except serial.SerialException as e:
                print(f"串口接收异常（将尝试重连）: {e}")
                self.error_count += 1
                try:
                    self.serial_port.close()
                except Exception:
                    pass
                time.sleep(0.1)
            except Exception as e:
                print(f"串口接收错误: {e}")
                self.error_count += 1
                time.sleep(0.1)  # 出错后稍作等待
                
    def _try_reconnect(self) -> bool:
        """
        智能重连：先尝试恢复原端口，失败后扫描 CH340 新端口。
        支持 CH340 拔插后 COM 号变化的场景。
        """
        port_name = self.serial_port.port if self.serial_port else None
        baudrate = self.serial_port.baudrate if self.serial_port else 115200
        last_scan_time = 0.0
        
        for attempt in range(1, _RECONNECT_MAX_TRIES + 1):
            if not self.running:
                return False
                
            # ── 每 _CH340_SCAN_INTERVAL 秒重新扫描系统 COM 口 ──
            now = time.monotonic()
            if now - last_scan_time >= _CH340_SCAN_INTERVAL:
                last_scan_time = now
                found_port = self._scan_ch340_port()
                if found_port:
                    port_name = found_port
                    baudrate = 115200
                    print(f"CH340 扫描发现新端口: {found_port}")
            
            # ── 尝试打开端口 ──
            try:
                self.serial_port.close()
            except Exception:
                pass
                
            try:
                self.serial_port = serial.Serial(
                    port=port_name,
                    baudrate=baudrate,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=1
                )
                print(f"接收线程：串口 {port_name} 重连成功（第 {attempt} 次尝试）")
                return True
            except Exception:
                target = port_name or "未知"
                print(f"接收线程：串口 {target} 重连失败（{attempt}/{_RECONNECT_MAX_TRIES}），{_RECONNECT_INTERVAL}秒后重试")
                time.sleep(_RECONNECT_INTERVAL)
                
        return False

    def _scan_ch340_port(self) -> str | None:
        """扫描系统 COM 口，查找 CH340 设备。返回端口名或 None。"""
        if self._initializer_ref:
            result = self._initializer_ref.scan_and_find_ch340(self._auto_keyword)
            if result:
                return result
        try:
            ports = serial.tools.list_ports.comports()
            for port in ports:
                if self._auto_keyword.lower() in (port.description or "").lower():
                    return port.device
            for port in ports:
                if self._auto_keyword.lower() in (port.hwid or "").lower():
                    return port.device
        except Exception:
            pass
        return None
                
    def _process_received_data(self, data):
        """处理接收到的原始数据，只处理76字节BlackBox数据包"""
        if not data:
            return
            
        # 将数据添加到缓冲区
        self.receive_buffer.extend(data)

        # 缓冲区防溢出保护：超过上限时保留最后 256 字节（≥3 个完整帧），丢弃最老的垃圾字节
        MAX_BUFFER = 1024
        if len(self.receive_buffer) > MAX_BUFFER:
            self.receive_buffer = self.receive_buffer[-256:]

        self._process_save_flash_ack_frames()

        # 尝试从缓冲区中提取完整的76字节数据包
        while len(self.receive_buffer) >= 76:
            # 查找帧头 0xCC
            start_idx = -1
            for i in range(len(self.receive_buffer) - 75):  # 需要至少59字节
                if self.receive_buffer[i] == 0xCC:  # 帧头
                    start_idx = i
                    break
            
            if start_idx == -1:
                # 没有找到帧头，清空缓冲区
                self.receive_buffer.clear()
                return
                
            # 检查是否有完整的59字节数据包
            if start_idx + 76 > len(self.receive_buffer):
                # 数据包不完整，等待更多数据
                if start_idx > 0:
                    self.receive_buffer = self.receive_buffer[start_idx:]
                return
                
            # 提取完整数据包
            packet = bytes(self.receive_buffer[start_idx:start_idx + 76])
            
            # 检查帧尾
            if packet[-1] != 0xDD:  # 帧尾不匹配
                # 帧尾不匹配，跳过这个帧头
                self.receive_buffer = self.receive_buffer[start_idx + 76:]
                continue
            
            # 解码数据包
            decoded_data = decode_data(packet)
            if decoded_data:
                self._last_rx_packet = packet  # AIchange: 缓存原始76字节帧
                self._update_shared_data(decoded_data)
                self.receive_count += 1
                self.last_receive_time = time.time()
            else:
                self.error_count += 1
            
            # 从缓冲区中移除已处理的数据包
            self.receive_buffer = self.receive_buffer[start_idx + 76:]
                
    def _process_save_flash_ack_frames(self):
        while len(self.receive_buffer) >= 16:
            start_idx = self.receive_buffer.find(0xCC)
            if start_idx < 0:
                if len(self.receive_buffer) > 75:
                    self.receive_buffer = self.receive_buffer[-75:]
                return
            if start_idx > 0:
                del self.receive_buffer[:start_idx]
            if len(self.receive_buffer) < 16:
                return

            packet = bytes(self.receive_buffer[:16])
            if packet[1] == SAVE_TO_FLASH_ACK and packet[-1] == 0xDD:
                if verify_crc8(bytearray(packet), crc_position=-2, calc_start=0):
                    self.shared_data.update_save_flash_ack(packet[2])
                    self.receive_count += 1
                    self.last_receive_time = time.time()
                    print(f"Flash save ack received, status={packet[2]}")
                    continue
                # CRC 失败 → 可能是 BlackBox 帧被误判，不删除，留给主循环处理

            # 帧头已找到但不是 ACK 帧且缓冲区 ≥76 字节：交给主循环解码 BlackBox
            if len(self.receive_buffer) >= 76:
                return
            # 缓冲区不足 76 字节：等更多数据到达再判断，不逐字节删除
            return

    def _update_shared_data(self, decoded_data):
        """将解码后的BlackBox数据更新到共享数据结构中（线程安全）"""
        try:
            # 原子写入：在锁内一次性完成所有黑箱字段赋值
            # 消除显示线程读到"前几个字段是新数据、后几个字段是旧数据"的竞态窗口
            self.shared_data.update_blackbox(decoded_data)

            # 根据状态切换决定是否启动/停止记录
            current_state = self.shared_data.main_state
            if getattr(self, '_last_main_state', None) != current_state:
                if current_state in (MainState.DATA, MainState.TOWER):
                    if self.blackbox_logger and not self.blackbox_logger.is_logging:
                        # 确保重启
                        self.blackbox_logger.seen_timestamps.clear()
                        self.blackbox_logger.start_logging()
                else:
                    if self.blackbox_logger and self.blackbox_logger.is_logging:
                        self.blackbox_logger.stop_logging()
                self._last_main_state = current_state

            # 只有当正在记录时，才将数据写入CSV
            if self.blackbox_logger and self.blackbox_logger.is_logging:
                self.blackbox_logger.log_data(
                    float(decoded_data.blackbox_timestamp),
                    decoded_data
                )

        except Exception as e:
            print(f"更新共享数据错误: {e}")
            self.error_count += 1
            
    def get_last_rx_hex(self) -> Optional[str]:
        """AIchange: 获取最近一次成功接收的76字节原始帧hex字符串"""
        if self._last_rx_packet is None:
            return None
        return " ".join([f"{b:02X}" for b in self._last_rx_packet])

    def get_receive_status(self):
        """获取接收状态信息"""
        status_time = "从未接收" if self.last_receive_time is None else f"{time.time() - self.last_receive_time:.1f}秒前"
        
        return {
            "running": self.running,
            "receive_count": self.receive_count,
            "error_count": self.error_count,
            "last_receive_time": status_time,
            "buffer_size": len(self.receive_buffer),
            "last_rx_hex": self.get_last_rx_hex(),
        }
        
    def get_received_data_summary(self):
        """获取接收数据的摘要信息"""
        if self.shared_data.blackbox_received:
            return {
                "packet_timestamp": str(self.shared_data.blackbox_timestamp),  # 数据包时间戳
                "angle": f"[{self.shared_data.blackbox_angle[0]:.3f}, {self.shared_data.blackbox_angle[1]:.3f}, {self.shared_data.blackbox_angle[2]:.3f}]",
                "gyro": f"[{self.shared_data.blackbox_gyro[0]:.3f}, {self.shared_data.blackbox_gyro[1]:.3f}, {self.shared_data.blackbox_gyro[2]:.3f}]",
                "acc": f"[{self.shared_data.blackbox_acc[0]:.3f}, {self.shared_data.blackbox_acc[1]:.3f}, {self.shared_data.blackbox_acc[2]:.3f}]",
                "rudder": f"[{self.shared_data.blackbox_rudder[0]:.3f}, {self.shared_data.blackbox_rudder[1]:.3f}, {self.shared_data.blackbox_rudder[2]:.3f}, {self.shared_data.blackbox_rudder[3]:.3f}]"
            }
        else:
            return {
                "status": "未接收到BlackBox数据"
            }
            
    def start_blackbox_logging(self):
        """开始黑箱记录（进入DATA模式时调用）"""
        if self.blackbox_logger:
            return self.blackbox_logger.start_logging()
        return False
    
    def stop_blackbox_logging(self):
        """停止黑箱记录"""
        if self.blackbox_logger:
            return self.blackbox_logger.stop_logging()
        return False
    
    def toggle_blackbox_logging(self):
        """切换黑箱记录状态（L键功能）"""
        if self.blackbox_logger:
            return self.blackbox_logger.toggle_logging()
        return False
    
    def get_blackbox_logging_status(self):
        """获取黑箱记录状态"""
        if self.blackbox_logger:
            return self.blackbox_logger.get_status()
        return {
            'is_logging': False,
            'record_count': 0,
            'max_records': 2000,
            'remaining': 0
        }
