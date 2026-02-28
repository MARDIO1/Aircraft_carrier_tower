"""
键盘输入捕获模块
负责捕获键盘信号并更新共享数据，支持二维数组导航。
使用 keyboard 库全局钩子，在子线程中轮询。
"""

import keyboard
import threading
import time
from protocol import ProtocolData, MainState, SubState, StateMachineManager

# ──────────────────────────────────────────────
#  TOWER 模式：40键 → 5字节 bit 映射
# ──────────────────────────────────────────────
TOWER_KEY_MAP: dict[str, int] = {
    # 26个字母: bit 0-25
    'a': 0,  'b': 1,  'c': 2,  'd': 3,  'e': 4,
    'f': 5,  'g': 6,  'h': 7,  'i': 8,  'j': 9,
    'k': 10, 'l': 11, 'm': 12, 'n': 13, 'o': 14,
    'p': 15, 'q': 16, 'r': 17, 's': 18, 't': 19,
    'u': 20, 'v': 21, 'w': 22, 'x': 23, 'y': 24,
    'z': 25,
    # 10个数字: bit 26-35
    '0': 26, '1': 27, '2': 28, '3': 29, '4': 30,
    '5': 31, '6': 32, '7': 33, '8': 34, '9': 35,
    # 修饰键: bit 36-39
    'shift': 36, 'ctrl': 37, 'alt': 38, 'tab': 39,
}

# ──────────────────────────────────────────────
#  PlayerInput
# ──────────────────────────────────────────────

class PlayerInput:
    def __init__(self, shared_data: ProtocolData):
        self.shared_data   = shared_data
        self.state_manager = StateMachineManager(shared_data)
        self.running       = False
        self.input_thread  = None

        # TOWER 模式 5 字节 bit 位
        self.tower_key_bits = bytearray(5)

        # 数值输入缓冲区
        self.input_buffer   = ""
        self.input_decimal  = False

        # 预设状态（数字键 1-9 在 AUTO 模式下触发）
        self.preset_states: dict[int, dict] = {
            1: {"main_switch": 1, "fan_speed": 1000, "servo_angles": [0.0, 0.0, 0.0, 0.0]},
            2: {"main_switch": 1, "fan_speed": 1500, "servo_angles": [0.0, 0.0, 0.0, 0.0]},
            3: {"main_switch": 1, "fan_speed": 1300, "servo_angles": [0.0, 0.0, 0.0, 0.0]},
            4: {"main_switch": 1, "fan_speed": 1400, "servo_angles": [0.0, 0.0, 0.0, 0.0]},
            5: {"main_switch": 1, "fan_speed": 1600, "servo_angles": [0.0, 0.0, 0.0, 0.0]},
            6: {"main_switch": 1, "fan_speed": 1700, "servo_angles": [0.0, 0.0, 0.0, 0.0]},
            7: {"main_switch": 1, "fan_speed": 1800, "servo_angles": [0.0, 0.0, 0.0, 0.0]},
            8: {"main_switch": 1, "fan_speed": 1900, "servo_angles": [0.0, 0.0, 0.0, 0.0]},
            9: {"main_switch": 1, "fan_speed": 1990, "servo_angles": [0.0, 0.0, 0.0, 0.0]},
        }

        # uart_receiver 引用（由外部注入，用于黑箱记录控制）
        self.uart_receiver = None

        # 导航变化时清空输入缓冲
        self.state_manager.register_navigation_callback(self._on_navigation_changed)

    # ──────────── 生命周期 ────────────

    def start_capture(self):
        """开始捕获键盘输入"""
        if self.running:
            return
        self.running = True
        self.input_thread = threading.Thread(
            target=self._input_loop, daemon=True)
        self.input_thread.start()

    def stop_capture(self):
        """停止捕获键盘输入"""
        self.running = False
        keyboard.unhook_all()
        if self.input_thread:
            self.input_thread.join(timeout=1.0)
        self.state_manager.unregister_navigation_callback(self._on_navigation_changed)

    def set_uart_receiver(self, uart_receiver):
        """注入 UART 接收器，用于控制黑箱记录"""
        self.uart_receiver = uart_receiver

    # ──────────── 内部：输入循环 ────────────

    def _input_loop(self):
        keyboard.on_press(self._on_key_press)
        while self.running:
            time.sleep(0.05)

    # ──────────── 按键路由 ────────────

    def _on_key_press(self, event):
        if not self.running:
            return
        try:
            key = event.name.lower() if event.name else ''
            if self.shared_data.main_state == MainState.TOWER:
                self._handle_tower_key(key)
            else:
                self._handle_normal_key(key)
        except Exception:
            pass  # 静默处理，防止异常打断 UI

    def _handle_tower_key(self, key: str):
        """TOWER 模式按键处理"""
        if key == 'esc':
            # 若 bit 全零则退出 TOWER，否则先清零
            if all(b == 0 for b in self.tower_key_bits):
                self.state_manager.handle_escape()
            else:
                self.tower_key_bits = bytearray(5)
                self.shared_data.tower_key_bits = self.tower_key_bits
            return

        if key == 'space':
            self._toggle_main_switch()
            return

        # 方向键 / Enter：保留导航能力
        nav = {'up': self.state_manager.navigate_up,
               'down': self.state_manager.navigate_down,
               'left': self.state_manager.navigate_left,
               'right': self.state_manager.navigate_right,
               'enter': self.state_manager.handle_enter}
        if key in nav:
            nav[key]()
            return

        # 修饰键名称统一
        normalized = self._normalize_modifier(key)
        if normalized in TOWER_KEY_MAP:
            bit_idx = TOWER_KEY_MAP[normalized]
            self.tower_key_bits[bit_idx // 8] ^= (1 << (bit_idx % 8))
            self.shared_data.tower_key_bits = bytes(self.tower_key_bits)

    def _handle_normal_key(self, key: str):
        """非 TOWER 模式按键处理"""
        sd = self.shared_data

        # 导航
        nav = {'up': self.state_manager.navigate_up,
               'down': self.state_manager.navigate_down,
               'left': self.state_manager.navigate_left,
               'right': self.state_manager.navigate_right}
        if key in nav:
            nav[key]()
            return

        if key == 'enter':
            self.state_manager.handle_enter()
            return

        if key == 'esc':
            self.state_manager.handle_escape()
            return

        # 空格：总开关（AUTO 模式）
        if key == 'space' and sd.main_state == MainState.AUTO:
            self._toggle_main_switch()
            return

        # D：STOP → DATA
        if key == 'd' and sd.main_state == MainState.STOP:
            self._switch_to_data()
            return

        # L：DATA 模式切换黑箱记录
        if key == 'l' and sd.main_state == MainState.DATA:
            self._toggle_blackbox_logging()
            return

        # 数字键
        if key in '0123456789':
            if sd.main_state == MainState.AUTO:
                num = int(key)
                if num in self.preset_states:
                    self._set_preset_state(num)
            else:
                self._add_digit(key)
            return

        # 小数点 / 退格
        if key == '.':
            self._add_decimal_point()
        elif key == 'backspace':
            self._delete_input_char()

    # ──────────── 输入缓冲 ────────────

    def _add_digit(self, digit: str):
        self.input_buffer += digit
        self._update_param_from_buffer()

    def _add_decimal_point(self):
        if not self.input_decimal:
            self.input_buffer = (self.input_buffer or "0") + "."
            self.input_decimal = True
            self._update_param_from_buffer()

    def _delete_input_char(self):
        if self.input_buffer:
            if self.input_buffer[-1] == '.':
                self.input_decimal = False
            self.input_buffer = self.input_buffer[:-1]
            self._update_param_from_buffer()

    def _clear_input_buffer(self):
        self.input_buffer  = ""
        self.input_decimal = False

    def _on_navigation_changed(self, nav_row: int, nav_col: int):
        """导航位置变化时清空输入缓冲"""
        self._clear_input_buffer()

    def _update_param_from_buffer(self):
        """将缓冲区内容实时写入对应参数"""
        if not self.input_buffer or self.input_buffer.endswith('.'):
            return
        try:
            value = float(self.input_buffer)
        except ValueError:
            return

        sd = self.shared_data
        if sd.main_state == MainState.TUNING:
            ss = sd.sub_state
            if ss == SubState.PID:
                r, c = sd.nav_row, sd.nav_col
                if r < len(sd.pid_param) and c < len(sd.pid_param[0]):
                    sd.pid_param[r][c] = value
            elif ss == SubState.JACOBIAN:
                r, c = sd.nav_row, sd.nav_col
                if r < 3 and c < 4:
                    sd.jacobian_matrix[r][c] = value
            elif ss == SubState.SERVO:
                idx = sd.nav_col
                if 0 <= idx < 4:
                    sd.servo_angles[idx] = value
        else:
            # AUTO / STOP 等模式：按导航列更新
            c = sd.nav_col
            if c == 0:
                sd.main_switch = int(value)
            elif c == 1:
                sd.fan_speed = int(value)
            elif 2 <= c <= 5:
                sd.servo_angles[c - 2] = value

    # ──────────── 模式切换 ────────────

    def _toggle_main_switch(self):
        ms = self.shared_data.main_state
        if ms == MainState.STOP:
            self.shared_data.set_main_state(MainState.AUTO)
            self.shared_data.main_switch = 1
        elif ms in (MainState.AUTO, MainState.TOWER):
            self.shared_data.set_main_state(MainState.STOP)
            self.shared_data.main_switch = 0
            self.shared_data.fan_speed = 0
            self.shared_data.servo_angles = [0.0, 0.0, 0.0, 0.0]

    def _switch_to_data(self):
        if self.shared_data.set_main_state(MainState.DATA):
            self._clear_input_buffer()
            self._start_blackbox_logging()

    def _toggle_blackbox_logging(self):
        if not (self.uart_receiver):
            return
        self.uart_receiver.toggle_blackbox_logging()

    def _start_blackbox_logging(self):
        if self.uart_receiver:
            self.uart_receiver.start_blackbox_logging()

    def _set_preset_state(self, preset_num: int):
        preset = self.preset_states[preset_num]
        sd = self.shared_data
        sd.main_switch   = preset["main_switch"]
        sd.fan_speed     = preset["fan_speed"]
        sd.servo_angles  = preset["servo_angles"].copy()
        if preset["main_switch"] == 0:
            sd.set_main_state(MainState.STOP)
        elif sd.main_state not in (MainState.AUTO, MainState.TOWER):
            sd.set_main_state(MainState.AUTO)

    # ──────────── 辅助 ────────────

    @staticmethod
    def _normalize_modifier(key: str) -> str:
        """统一修饰键名称（keyboard 库可能返回 'left shift' 等）"""
        if 'shift' in key:   return 'shift'
        if 'ctrl'  in key or 'control' in key: return 'ctrl'
        if 'alt'   in key:   return 'alt'
        if key == 'tab':     return 'tab'
        return key

    def get_tower_bits_display(self) -> list[str]:
        """返回当前按下的 TOWER 按键名称列表（用于 UI 显示）"""
        pressed = []
        for key_name, bit_idx in TOWER_KEY_MAP.items():
            if self.tower_key_bits[bit_idx // 8] & (1 << (bit_idx % 8)):
                pressed.append(key_name.upper())
        return pressed

    def get_tower_bits_hex(self) -> str:
        """返回 5 字节的十六进制字符串（用于调试/UI）"""
        return ' '.join(f'{b:02X}' for b in self.tower_key_bits)

    def get_current_input(self) -> dict:
        """获取当前输入状态快照（外部查询接口）"""
        sd = self.shared_data
        return {
            "main_switch":   sd.main_switch,
            "fan_speed":     sd.fan_speed,
            "servo_angles":  sd.servo_angles.copy(),
            "nav_row":       sd.nav_row,
            "nav_col":       sd.nav_col,
            "input_buffer":  self.input_buffer,
            "main_state":    sd.main_state.name,
            "sub_state":     sd.sub_state.name if sd.main_state == MainState.TUNING else "N/A",
        }
