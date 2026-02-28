"""
终端 UI 模块 —— curses 五行固定布局
修复：
  - 逐行刷新（move+clrtoeol）替代全屏 clear，消除闪烁
  - 统一安全 addstr 包装，防止末列溢出崩溃
  - 手动 initscr 初始化，避免子线程内 wrapper 不稳定
  - 移除所有 print() 调用，改用消息队列
"""

import threading
import time
import curses
from datetime import datetime
from protocol import MainState, SubState


# ──────────────────────────────────────────────
#  工具函数
# ──────────────────────────────────────────────

def _display_width(text: str) -> int:
    """估算字符串显示宽度（中文字符占 2 列）"""
    w = 0
    for ch in text:
        code = ord(ch)
        if (0x1100 <= code <= 0x115F or  # Hangul Jamo
                0x2E80 <= code <= 0x303E or  # CJK Radicals / Kangxi
                0x3040 <= code <= 0xA4CF or  # CJK区（含汉字基本区）
                0xA960 <= code <= 0xA97F or
                0xAC00 <= code <= 0xD7FF or
                0xF900 <= code <= 0xFAFF or
                0xFE10 <= code <= 0xFE1F or
                0xFE30 <= code <= 0xFE4F or
                0xFF01 <= code <= 0xFF60 or
                0xFFE0 <= code <= 0xFFE6 or
                0x1B000 <= code <= 0x1B77F or
                0x1F300 <= code <= 0x1FAFF or
                0x20000 <= code <= 0x2FFFD or
                0x30000 <= code <= 0x3FFFD):
            w += 2
        else:
            w += 1
    return w


def _fit_text(text: str, max_width: int) -> str:
    """将文本裁剪到 max_width 列以内（中文安全截断）"""
    if max_width <= 0:
        return ""
    w = 0
    result = []
    for ch in text:
        cw = 2 if _display_width(ch) == 2 else 1
        if w + cw > max_width:
            break
        result.append(ch)
        w += cw
    return "".join(result)


# ──────────────────────────────────────────────
#  Consle 类
# ──────────────────────────────────────────────

class Consle:
    # 固定行号
    _ROW_STATUS  = 0   # 模式/开关/风扇/舵机
    _ROW_SEND    = 1   # 发送帧
    _ROW_RECEIVE = 2   # 接收帧
    _ROW_TUNING  = 3   # 调参/TOWER/导航
    _ROW_MSG     = 4   # 消息队列

    def __init__(self, uart_sender, initializer, player_input, shared_data=None):
        self.uart_sender  = uart_sender
        self.initializer  = initializer
        self.player_input = player_input
        self.shared_data  = shared_data

        self.running        = False
        self.console_thread = None
        self._stdscr        = None          # curses 窗口句柄（子线程内初始化）

        # 消息队列（最多保留 2 条）
        self._msg_lock    = threading.Lock()
        self.message_queue: list[str] = []
        self.max_messages = 2

        # 变化检测（避免频繁重写消息队列）
        self._last_mode   = None
        self._last_switch = None

        # 输入缓冲（供 _draw_tuning_line 显示）
        self._last_input_buf = ""

    # ──────────── 公共接口 ────────────

    def start_display(self):
        """启动 UI 线程"""
        if self.running:
            return
        self.running = True
        self.console_thread = threading.Thread(
            target=self._console_loop, daemon=True)
        self.console_thread.start()

    def stop_display(self):
        """停止 UI 线程"""
        self.running = False
        if self.console_thread:
            self.console_thread.join(timeout=1.5)
        # 还原终端
        if self._stdscr:
            try:
                curses.nocbreak()
                self._stdscr.keypad(False)
                curses.echo()
                curses.endwin()
            except Exception:
                pass
            self._stdscr = None

    def add_message(self, message: str):
        """线程安全地向消息队列添加一条带时间戳的消息"""
        ts   = datetime.now().strftime("%H:%M:%S")
        full = f"{ts} {message}"
        with self._msg_lock:
            self.message_queue.append(full)
            while len(self.message_queue) > self.max_messages:
                self.message_queue.pop(0)

    # ──────────── 内部：线程主循环 ────────────

    def _console_loop(self):
        """UI 线程：手动初始化 curses，20 Hz 刷新"""
        try:
            stdscr = curses.initscr()
            self._stdscr = stdscr
            curses.noecho()
            curses.cbreak()
            stdscr.keypad(True)
            curses.curs_set(0)
            stdscr.nodelay(True)   # 非阻塞，不让 curses 自己读键

            self.add_message("控制台启动")

            while self.running:
                self._draw_console(stdscr)
                time.sleep(0.05)    # 20 Hz

        except Exception as e:
            # curses 异常时恢复终端，不能用 print（可能 curses 还活着）
            try:
                curses.endwin()
            except Exception:
                pass
            # 此时终端已还原，可以安全 print
            print(f"[Consle] UI 线程异常退出: {e}")
        finally:
            try:
                curses.endwin()
            except Exception:
                pass

    # ──────────── 内部：安全绘制 ────────────

    def _safe_addstr(self, stdscr, row: int, text: str):
        """
        安全地在指定行写入文本：
          1. move + clrtoeol 清除旧内容
          2. 裁剪到终端宽度-1，防止末列溢出
          3. 吞掉所有 curses 异常
        """
        try:
            max_y, max_x = stdscr.getmaxyx()
            if row >= max_y:
                return
            stdscr.move(row, 0)
            stdscr.clrtoeol()
            fitted = _fit_text(text, max_x - 1)
            if fitted:
                stdscr.addstr(row, 0, fitted)
        except curses.error:
            pass

    # ──────────── 内部：整屏绘制 ────────────

    def _draw_console(self, stdscr):
        """每帧调用：逐行刷新，不清屏"""
        self._draw_status_line(stdscr,  self._ROW_STATUS)
        self._draw_send_line(stdscr,    self._ROW_SEND)
        self._draw_receive_line(stdscr, self._ROW_RECEIVE)
        self._draw_tuning_line(stdscr,  self._ROW_TUNING)
        self._draw_message_line(stdscr, self._ROW_MSG)
        try:
            stdscr.refresh()
        except curses.error:
            pass

    # ──────────── 行 0：状态总览 ────────────

    def _draw_status_line(self, stdscr, row: int):
        if not self.shared_data:
            self._safe_addstr(stdscr, row, "模式:--- 开关:--- 风扇:--- 舵机:---")
            return

        sd = self.shared_data
        ms = sd.main_state

        mode_map = {
            MainState.STOP:   "STOP",
            MainState.AUTO:   "AUTO",
            MainState.TOWER:  "TOWER",
            MainState.TUNING: "TUNING",
            MainState.DATA:   "DATA",
        }
        mode_text = f"模式:{mode_map.get(ms, ms.name)}"

        if ms == MainState.TUNING:
            sub_map = {SubState.SERVO: "SERVO", SubState.PID: "PID", SubState.JACOBIAN: "JACOBIAN"}
            mode_text += f"({sub_map.get(sd.sub_state, '?')})"

        switch_text = f"开关:{'ON' if sd.main_switch == 1 else 'OFF'}"
        fan_text    = f"风扇:{sd.fan_speed}"
        servo_str   = ",".join(f"{a:.1f}" for a in sd.servo_angles)
        nav_text    = f"导航:[{sd.nav_row},{sd.nav_col}]"

        line = f"{mode_text} {switch_text} {fan_text} 舵机:[{servo_str}] {nav_text}"
        self._safe_addstr(stdscr, row, line)

        # 状态变化时追加一条消息（避免在 curses 内 print）
        self._check_status_changes(ms, sd.main_switch)

    def _check_status_changes(self, ms: MainState, switch: int):
        mode_val = ms.value
        if mode_val != self._last_mode and self._last_mode is not None:
            names = {
                MainState.STOP.value:   "停止模式",
                MainState.AUTO.value:   "自动模式",
                MainState.TOWER.value:  "塔楼模式",
                MainState.TUNING.value: "调参模式",
                MainState.DATA.value:   "数据模式",
            }
            self.add_message(names.get(mode_val, f"模式:{ms.name}"))
        if switch != self._last_switch and self._last_switch is not None:
            self.add_message(f"开关:{'ON' if switch == 1 else 'OFF'}")
        self._last_mode   = mode_val
        self._last_switch = switch

    # ──────────── 行 1：发送帧 ────────────

    def _draw_send_line(self, stdscr, row: int):
        if not self.uart_sender:
            self._safe_addstr(stdscr, row, "发送:---")
            return
        try:
            hex_data = self.uart_sender.get_hex_data()
            self._safe_addstr(stdscr, row, f"发送:{hex_data}")
        except Exception as e:
            self._safe_addstr(stdscr, row, f"发送:错误 {str(e)[:30]}")

    # ──────────── 行 2：接收帧 ────────────

    def _draw_receive_line(self, stdscr, row: int):
        if not self.shared_data:
            self._safe_addstr(stdscr, row, "接收:未连接")
            return

        sd = self.shared_data

        if sd.main_state == MainState.DATA and sd.blackbox_received:
            ang = sd.blackbox_angle
            gyr = sd.blackbox_gyro
            line = (f"时间戳:{sd.blackbox_timestamp} "
                    f"状态机:0x{sd.blackbox_statemachine:02X} "
                    f"角(r,p,y)=({ang[0]:.2f},{ang[1]:.2f},{ang[2]:.2f}) "
                    f"角速(x,y,z)=({gyr[0]:.2f},{gyr[1]:.2f},{gyr[2]:.2f})")
        else:
            sw    = sd.received_switch
            roll  = sd.received_angle_roll
            pitch = sd.received_angle_pitch
            yaw   = sd.received_angle_yaw
            if sw != 0 or abs(roll) > 0.001 or abs(pitch) > 0.001 or abs(yaw) > 0.001:
                line = f"接收:开关={sw} 角度=({roll:.1f},{pitch:.1f},{yaw:.1f})"
            else:
                line = "接收:无数据"

        self._safe_addstr(stdscr, row, line)

    # ──────────── 行 3：调参 / TOWER / 导航 ────────────

    def _draw_tuning_line(self, stdscr, row: int):
        if not self.shared_data:
            return

        sd  = self.shared_data
        ms  = sd.main_state
        inp = getattr(self.player_input, "input_buffer", "")

        # DATA 模式第二行
        if ms == MainState.DATA and sd.blackbox_received:
            acc    = sd.blackbox_acc
            rudder = sd.blackbox_rudder
            line   = (f"加速度=({acc[0]:.2f},{acc[1]:.2f},{acc[2]:.2f}) "
                      f"舵机=[{rudder[0]:.2f},{rudder[1]:.2f},{rudder[2]:.2f},{rudder[3]:.2f}]")
            self._safe_addstr(stdscr, row, line)
            return

        # TOWER 模式
        if ms == MainState.TOWER:
            pressed = self.player_input.get_tower_bits_display()
            hex_data = self.player_input.get_tower_bits_hex()
            keys_str = ", ".join(pressed) if pressed else "无"
            self._safe_addstr(stdscr, row, f"TOWER按键:{keys_str}  数据:{hex_data}")
            return

        # TUNING 模式
        if ms == MainState.TUNING:
            ss      = sd.sub_state
            nav_row = sd.nav_row
            nav_col = sd.nav_col

            if ss == SubState.SERVO:
                idx = nav_col if 0 <= nav_col < len(sd.servo_angles) else 0
                val = sd.servo_angles[idx]
                line = f"舵机[{idx}]:{val:.1f}"
                if inp:
                    line += f"  [输入:{inp}]"
                self._safe_addstr(stdscr, row, line)

                # 输入变化时通知（只通知一次）
                if inp != self._last_input_buf:
                    self._last_input_buf = inp

            elif ss == SubState.PID:
                if nav_row < len(sd.pid_name) and nav_col < len(sd.param_names):
                    pname = sd.pid_name[nav_row]
                    param = sd.param_names[nav_col]
                    val   = sd.pid_param[nav_row][nav_col]
                    line  = f"{pname}.{param}={val:.3f}"
                    if inp:
                        line += f"  [输入:{inp}]"
                    self._safe_addstr(stdscr, row, line)

            elif ss == SubState.JACOBIAN:
                if nav_row < 3 and nav_col < 4:
                    val  = sd.jacobian_matrix[nav_row][nav_col]
                    line = f"J[{nav_row},{nav_col}]:{val:.3f}"
                    if inp:
                        line += f"  [输入:{inp}]"
                    self._safe_addstr(stdscr, row, line)
            return

        # 其他模式：导航提示
        line = f"导航:行={sd.nav_row},列={sd.nav_col}  (方向键导航, Enter确认)"
        self._safe_addstr(stdscr, row, line)

    # ──────────── 行 4：消息 ────────────

    def _draw_message_line(self, stdscr, row: int):
        with self._msg_lock:
            msgs = list(self.message_queue[-2:])
        line = "  ".join(msgs) if msgs else ""
        self._safe_addstr(stdscr, row, line)
