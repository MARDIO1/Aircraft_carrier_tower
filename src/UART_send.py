"""
串口发送模块
负责将键盘信号通过USB串口TTL发送
"""

import threading
import time
import serial
import serial.tools.list_ports
from protocol import encode_data

# 串口断线重连配置
_RECONNECT_INTERVAL = 1.0   # 每次重连尝试间隔（秒）
_RECONNECT_MAX_TRIES = 30   # 最多重试次数（30次 × 1秒 = 30秒后放弃）
_CH340_SCAN_INTERVAL = 2.0  # CH340 重新扫描间隔（秒），用于 COM 号变化时的动态发现

class UARTSender:
    def __init__(self, serial_port, shared_data):
        """
        初始化串口发送器
        Args:
            serial_port: 串口对象
            shared_data: 线程间共享的数据对象
        """
        self.serial_port = serial_port
        self.shared_data = shared_data
        self.running = False
        self.send_thread = None
        self.last_sent_data = None
        self._last_packet = None  # 最近一次成功编码的数据包
        self._auto_keyword = "CH340"  # 用于动态扫描 CH340 的关键词
        self._initializer_ref = None  # 可选：指向 Initializer 实例的引用，用于 scan_and_find_ch340
        
    def set_initializer(self, initializer):
        """设置 Initializer 引用，用于动态扫描 CH340 端口"""
        self._initializer_ref = initializer
        if initializer and initializer.com_port:
            self.port_name = initializer.com_port
        
    def start_sending(self):
        """开始发送数据"""
        if self.running:
            return
            
        self.running = True
        self.send_thread = threading.Thread(target=self._send_loop)
        self.send_thread.daemon = True
        self.send_thread.start()
        print("串口数据发送已启动")
        
    def stop_sending(self):
        """停止发送数据"""
        self.running = False
        if self.send_thread:
            self.send_thread.join(timeout=1.0)
        print("串口数据发送已停止")
        
    def _send_loop(self):
        """
        数据发送循环（50Hz，补偿式定时 + 断线自动重连）

        A3 精确频率：用 perf_counter 补偿式定时，消除 Windows sleep 精度误差。
        A1 断线重连：串口异常后不退出线程，每秒尝试重新打开，最多 _RECONNECT_MAX_TRIES 次。
        """
        SEND_INTERVAL = 0.02  # 50Hz = 20ms

        next_tick = time.perf_counter()

        while self.running:
            # ── A3：补偿式定时 ──────────────────────────────────────────
            now = time.perf_counter()
            sleep_time = next_tick - now
            if sleep_time > 0:
                time.sleep(sleep_time)
            next_tick += SEND_INTERVAL
            # 防止长时间阻塞后 next_tick 严重落后导致连续空转
            if next_tick < time.perf_counter() - SEND_INTERVAL:
                next_tick = time.perf_counter() + SEND_INTERVAL

            # ── A1：串口可用性检查 ──────────────────────────────────────
            if not (self.serial_port and self.serial_port.is_open):
                if not self._try_reconnect():
                    # 重连彻底失败，退出线程
                    print("串口重连失败次数已达上限，发送线程退出")
                    self.running = False
                    break
                continue  # 重连成功后从下一个 tick 开始正常发送

            # ── 编码 ────────────────────────────────────────────────────
            try:
                with self.shared_data._lock:
                    packet = encode_data(self.shared_data)
            except Exception as enc_err:
                print(f"编码控制数据出错，使用上一帧数据继续发送: {enc_err}")
                packet = None

            if packet is None:
                packet_to_send = self._last_packet
                if packet_to_send is None:
                    continue  # 还没有任何可用帧，跳过本次
            else:
                packet_to_send = packet
                self.last_sent_data = {
                    "main_switch": self.shared_data.main_switch,
                    "fan_speed": self.shared_data.fan_speed,
                    "servo_angles": self.shared_data.servo_angles.copy(),
                }
                self._last_packet = packet_to_send

            # ── 发送 ────────────────────────────────────────────────────
            try:
                self.serial_port.write(packet_to_send)
            except serial.SerialException as e:
                print(f"串口写入失败，尝试重连: {e}")
                try:
                    self.serial_port.close()
                except Exception:
                    pass

    def _try_reconnect(self) -> bool:
        """
        智能重连：先尝试恢复原端口，失败后扫描 CH340 新端口。
        支持 CH340 拔插后 COM 号变化的场景。
        成功返回 True，彻底失败返回 False。
        """
        port_name = self.serial_port.port if self.serial_port else None
        baudrate = self.serial_port.baudrate if self.serial_port else 115200
        last_scan_time = 0.0  # 控制 CH340 扫描频率

        # 第1阶段：尝试在原端口重连（前几次快速尝试）
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
                print(f"串口 {port_name} 重连成功（第 {attempt} 次尝试）")
                return True
            except Exception:
                target = port_name or "未知"
                print(f"串口 {target} 重连失败（{attempt}/{_RECONNECT_MAX_TRIES}），{_RECONNECT_INTERVAL}秒后重试")
                time.sleep(_RECONNECT_INTERVAL)

        return False

    def _scan_ch340_port(self) -> str | None:
        """扫描系统 COM 口，查找 CH340 设备。返回端口名或 None。"""
        # 优先使用 Initializer 的 scan_and_find_ch340
        if self._initializer_ref:
            result = self._initializer_ref.scan_and_find_ch340(self._auto_keyword)
            if result:
                return result
        # 兜底：自己扫描
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
                
    def get_last_sent_info(self):
        """获取最后发送的数据信息"""
        if self.last_sent_data:
            return f"开关:{self.last_sent_data['main_switch']} 风扇:{self.last_sent_data['fan_speed']} 舵机:{self.last_sent_data['servo_angles']}"
        else:
            return "无发送记录"
            
    def get_hex_data(self):
        """获取最近一次成功发送的数据包的16进制格式，不重新编码控制数据。"""
        if not self._last_packet:
            return None
        return " ".join([f"{byte:02X}" for byte in self._last_packet])