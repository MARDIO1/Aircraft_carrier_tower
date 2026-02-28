"""
终端 UI 模块 —— 纯 ANSI 转义码五行固定布局
不依赖 curses，直接写 sys.stdout，Windows 10+ 原生支持 VT100。

显示布局（行固定，每帧刷新）：
  行0  模式 | 开关 | 风扇 | 舵机 | 导航
  行1  发送帧（最后一次实际发出的 hex）
  行2  接收帧
  行3  调参/TOWER/导航详情
  行4  消息队列
"""

import sys
import os
import threading
import time
from datetime import datetime
from protocol import MainState, SubState

# ─────────────────────────────────────────────
#  Windows VT100 支持初始化（只需调用一次）
# ─────────────────────────────────────────────

def _enable_vt100():
    """在 Windows 终端开启 VT100 转义码支持"""
    if os.name == 'nt':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            # 获取 stdout 句柄
            handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
            mode   = ctypes.c_ulong()
            kernel32.GetConsoleMode(handle, ctypes.byref(mode))
            # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
        except Exception:
            pass  # 已经支持或无法设置，忽略


# ─────────────────────────────────────────────
#  ANSI 工具
# ─────────────────────────────────────────────

# 固定使用的行起始行号（0-based，从终端顶部算）
_UI_TOP_ROW = 1   # 从第1行开始，留出第0行给其他输出（如启动日志）
_NUM_ROWS   = 5


def _move_and_clear(row: int) -> str:
    """生成：移动到指定行首 + 清除该行内容的 ANSI 序列（行号 1-based）"""
    return f"\033[{row};1H\033[2K"


def _display_width(ch: str) -> int:
    """判断单个字符的显示宽度"""
    code = ord(ch)
    if (0x1100 <= code <= 0x115F or
            0x2E80 <= code <= 0x303E or
            0x3040 <= code <= 0xA4CF or
            0xAC00 <= code <= 0xD7FF or
            0xF900 <= code <= 0xFAFF or
            0xFF01 <= code <= 0xFF60 or
            0xFFE0 <= code <= 0xFFE6 or
            0x20000 <= code <= 0x2FFFD):
        return 2
    return 1


def _fit(text: str, max_width: int) -> str:
    """将文本截断到 max_width 列以内（中文安全）"""
    w, out = 0, []
    for ch in text:
        cw = _display_width(ch)
        if w + cw > max_width:
            break
        out.append(ch)
        w += cw
    return "".join(out)


# ─────────────────────────────────────────────
#  Consle
# ─────────────────────────────────────────────

class Consle:
    def __init__(self, uart_sender, initializer, player_input, shared_data=None):
        self.uart_sender  = uart_sender
        self.initializer  = initializer
        self.player_input = player_input
        self.shared_data  = shared_data

        self.running        = False
        self.console_thread = None

        # 消息队列（最多 2 条）
        self._msg_lock    = threading.Lock()
        self._messages: list[str] = []

        # 状态变化检测（用于追加消息）
        self._last_mode   = None
        self._last_switch = None

        # 终端宽度缓存（每秒更新一次）
        self._term_width    = 120
        self._width_counter = 0

        _enable_vt100()

    # ─────────── 公共接口 ───────────

    def start_display(self):
        if self.running:
            return
        self.running = True
        # 隐藏光标，避免闪烁
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()
        self.console_thread = threading.Thread(
            target=self._loop, daemon=True)
        self.console_thread.start()

    def stop_display(self):
        self.running = False
        if self.console_thread:
            self.console_thread.join(timeout=1.5)
        # 还原光标
        sys.stdout.write("\033[?25h\n")
        sys.stdout.flush()

    def add_message(self, message: str):
        """线程安全地追加一条带时间戳的消息"""
        ts = datetime.now().strftime("%H:%M:%S")
        with self._msg_lock:
            self._messages.append(f"{ts} {message}")
            while len(self._messages) > 2:
                self._messages.pop(0)

    # ─────────── 内部：主循环 ───────────

    def _loop(self):
        """20 Hz 刷新循环"""
        self.add_message("控制台启动")
        while self.running:
            try:
                self._refresh()
            except Exception:
                pass
            time.sleep(0.05)

    def _refresh(self):
        """一次完整刷新：拼好所有行后一次 write"""
        # 每 20 帧（约 1 秒）更新一次终端宽度
        self._width_counter += 1
        if self._width_counter >= 20:
            self._width_counter = 0
            try:
                self._term_width = os.get_terminal_size().columns
            except OSError:
                self._term_width = 120

        w   = self._term_width - 1
        buf = ["\033[s"]  # 保存光标位置

        for i, line in enumerate(self._build_lines()):
            row = _UI_TOP_ROW + i          # 1-based
            buf.append(_move_and_clear(row))
            buf.append(_fit(line, w))

        buf.append("\033[u")               # 恢复光标位置
        sys.stdout.write("".join(buf))
        sys.stdout.flush()

    def _build_lines(self) -> list[str]:
        """构建 5 行文本内容"""
        return [
            self._line_status(),
            self._line_send(),
            self._line_receive(),
            self._line_detail(),
            self._line_message(),
        ]

    # ─────────── 行 0：状态总览 ───────────

    def _line_status(self) -> str:
        if not self.shared_data:
            return "模式:--- 开关:--- 风扇:--- 舵机:---"

        sd = self.shared_data
        ms = sd.main_state

        mode_names = {
            MainState.STOP:   "STOP",
            MainState.AUTO:   "AUTO",
            MainState.TOWER:  "TOWER",
            MainState.TUNING: "TUNING",
            MainState.DATA:   "DATA",
        }
        mode_str = mode_names.get(ms, ms.name)
        if ms == MainState.TUNING:
            sub_names = {SubState.SERVO: "SERVO", SubState.PID: "PID", SubState.JACOBIAN: "JAC"}
            mode_str += f"({sub_names.get(sd.sub_state, '?')})"

        servo_str = " ".join(f"{a:.1f}" for a in sd.servo_angles)
        line = (f"[{mode_str}]  "
                f"开关:{'ON ' if sd.main_switch == 1 else 'OFF'}  "
                f"风扇:{sd.fan_speed:5d}  "
                f"舵机:[{servo_str}]  "
                f"Nav({sd.nav_row},{sd.nav_col})")

        # 状态变化时追加消息
        self._check_changes(ms, sd.main_switch)
        return line

    def _check_changes(self, ms: MainState, switch: int):
        mv = ms.value
        if self._last_mode is not None and mv != self._last_mode:
            names = {MainState.STOP.value: "→STOP",
                     MainState.AUTO.value: "→AUTO",
                     MainState.TOWER.value: "→TOWER",
                     MainState.TUNING.value: "→TUNING",
                     MainState.DATA.value: "→DATA"}
            self.add_message(names.get(mv, f"→{ms.name}"))
        if self._last_switch is not None and switch != self._last_switch:
            self.add_message(f"开关:{'ON' if switch == 1 else 'OFF'}")
        self._last_mode   = mv
        self._last_switch = switch

    # ─────────── 行 1：发送帧 ───────────

    def _line_send(self) -> str:
        if not self.uart_sender:
            return "TX> --"
        return f"TX> {self.uart_sender.get_hex_data()}"

    # ─────────── 行 2：接收帧 ───────────

    def _line_receive(self) -> str:
        if not self.shared_data:
            return "RX> --"
        sd = self.shared_data

        if sd.main_state == MainState.DATA and sd.blackbox_received:
            a = sd.blackbox_angle
            g = sd.blackbox_gyro
            return (f"RX> ts={sd.blackbox_timestamp} sm=0x{sd.blackbox_statemachine:02X}"
                    f"  ang({a[0]:.1f},{a[1]:.1f},{a[2]:.1f})"
                    f"  gyro({g[0]:.1f},{g[1]:.1f},{g[2]:.1f})")

        sw = sd.received_switch
        r, p, y = sd.received_angle_roll, sd.received_angle_pitch, sd.received_angle_yaw
        if sw or abs(r) > 0.001 or abs(p) > 0.001 or abs(y) > 0.001:
            return f"RX> sw={sw}  ang({r:.1f},{p:.1f},{y:.1f})"
        return "RX> 无数据"

    # ─────────── 行 3：详情 ───────────

    def _line_detail(self) -> str:
        if not self.shared_data:
            return ""
        sd  = self.shared_data
        ms  = sd.main_state
        inp = getattr(self.player_input, "input_buffer", "")

        if ms == MainState.DATA and sd.blackbox_received:
            acc = sd.blackbox_acc
            rud = sd.blackbox_rudder
            return (f"acc({acc[0]:.2f},{acc[1]:.2f},{acc[2]:.2f})"
                    f"  rud[{rud[0]:.1f},{rud[1]:.1f},{rud[2]:.1f},{rud[3]:.1f}]")

        if ms == MainState.TOWER:
            keys = self.player_input.get_tower_bits_display()
            bits = self.player_input.get_tower_bits_hex()
            return f"TOWER keys:[{', '.join(keys) if keys else '无'}]  bits:{bits}"

        if ms == MainState.TUNING:
            ss = sd.sub_state
            r, c = sd.nav_row, sd.nav_col
            if ss == SubState.SERVO:
                idx = c if 0 <= c < 4 else 0
                val = sd.servo_angles[idx]
                base = f"舵机[{idx}]={val:.2f}"
            elif ss == SubState.PID:
                if r < len(sd.pid_name) and c < len(sd.param_names):
                    val  = sd.pid_param[r][c]
                    base = f"{sd.pid_name[r]}.{sd.param_names[c]}={val:.3f}"
                else:
                    base = "PID---"
            elif ss == SubState.JACOBIAN:
                val  = sd.jacobian_matrix[r][c] if r < 3 and c < 4 else 0
                base = f"J[{r},{c}]={val:.3f}"
            else:
                base = ""
            return f"{base}  {'[输入:' + inp + ']' if inp else '(直接输入数字修改)'}"

        if ms == MainState.STOP:
            labels = ["→AUTO", "→TOWER", "→TUNING", "→DATA"]
            idx = sd.nav_row if 0 <= sd.nav_row < 4 else 0
            return f"↑↓选择: {' '.join('['+l+']' if i == idx else l for i, l in enumerate(labels))}  Enter确认"

        return f"Nav({sd.nav_row},{sd.nav_col})"

    # ─────────── 行 4：消息 ───────────

    def _line_message(self) -> str:
        with self._msg_lock:
            msgs = list(self._messages)
        return "  ".join(msgs) if msgs else ""
