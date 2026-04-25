"""
键盘输入捕获模块 - 二维数组导航版本
负责捕获键盘信号并更新共享数据，支持二维数组导航
"""

import keyboard
import threading
import time
import json
from pathlib import Path
from protocol import ProtocolData, MainState, SubState, StateMachineManager, PID_TYPE_ENCODING
from auto_tune import AutoTuner

class PlayerInput:
    def __init__(self, shared_data):
        """
        初始化键盘输入捕获
        Args:
            shared_data: 线程间共享的数据对象 (ProtocolData实例)
        """
        self.shared_data = shared_data
        self.state_manager = StateMachineManager(shared_data)
        self.running = False
        self.input_thread = None
        self.auto_tuner = AutoTuner(self.shared_data)
        self.auto_tune_thread = None
        self.auto_tuning = False
        
        # 输入缓冲区
        self.input_buffer = ""
        self.input_decimal = False
        self.last_input_buffer = ""

        # 调参模式参数记忆（跨重启）
        base_dir = Path(__file__).resolve().parent.parent
        # 舵机调参
        self.servo_persist_file = base_dir / "servo_params.json"
        self.last_tuned_servo_angles = [0.0, 0.0, 0.0, 0.0]
        # 前馈调参
        self.feedforward_persist_file = base_dir / "feedforward_params.json"
        self.last_tuned_feedforward = [0.0, 0.0, 0.0, 0.0]
        # PID 调参（7x6 矩阵）
        self.pid_persist_file = base_dir / "pid_params.json"
        self.last_tuned_pid_param = [row.copy() for row in self.shared_data.pid_param]
        # Jacobian 调参（3x4 矩阵）
        self.jacobian_persist_file = base_dir / "jacobian_params.json"
        self.last_tuned_jacobian = [row.copy() for row in self.shared_data.jacobian_matrix]

        # 加载上次调参结果（如有），仅覆盖各自模式下的初始值
        self._load_last_tuned_servo_angles()
        self._load_last_tuned_feedforward()
        self._load_last_tuned_pid_param()
        self._load_last_tuned_jacobian()
        
        # 预设状态：数字 1-9 对应风扇 1000、1100、1200 ... 1800
        self.preset_states = {
            1: {"main_switch": 1, "fan_speed": 1000, "servo_angles": [0.0, 0.0, 0.0, 0.0]},
            2: {"main_switch": 1, "fan_speed": 1100, "servo_angles": [0.0, 0.0, 0.0, 0.0]},
            3: {"main_switch": 1, "fan_speed": 1200, "servo_angles": [0.0, 0.0, 0.0, 0.0]},
            4: {"main_switch": 1, "fan_speed": 1300, "servo_angles": [0.0, 0.0, 0.0, 0.0]},
            5: {"main_switch": 1, "fan_speed": 1400, "servo_angles": [0.0, 0.0, 0.0, 0.0]},
            6: {"main_switch": 1, "fan_speed": 1500, "servo_angles": [0.0, 0.0, 0.0, 0.0]},
            7: {"main_switch": 1, "fan_speed": 1600, "servo_angles": [0.0, 0.0, 0.0, 0.0]},
            8: {"main_switch": 1, "fan_speed": 1700, "servo_angles": [0.0, 0.0, 0.0, 0.0]},
            9: {"main_switch": 1, "fan_speed": 1800, "servo_angles": [0.0, 0.0, 0.0, 0.0]},
        }
        
        # 注册导航回调
        self.state_manager.register_navigation_callback(self._on_navigation_changed)
        
    def start_capture(self):
        """开始捕获键盘输入"""
        if self.running:
            return
            
        self.running = True
        self.input_thread = threading.Thread(target=self._input_loop)
        self.input_thread.daemon = True
        self.input_thread.start()
        
    def stop_capture(self):
        """停止捕获键盘输入"""
        self.running = False
        if self.input_thread:
            self.input_thread.join(timeout=1.0)
        # 注销导航回调
        self.state_manager.unregister_navigation_callback(self._on_navigation_changed)
            
    def _input_loop(self):
        """键盘输入循环"""
        keyboard.on_press(self._on_key_press)
        
        while self.running:
            time.sleep(0.1)
    
    def _on_key_press(self, event):
        """按键事件处理"""
        if not self.running:
            return
            
        try:
            key = event.name

            # 一键自动调参热键：F8（PID）
            if key == 'f8':
                self._start_pid_auto_tune()
                return

            # 一键自动调参热键：F9（舵机 + 前馈）
            if key == 'f9':
                self._start_auto_tune()
                return
            
            # 导航控制
            if key == 'up':
                self.state_manager.navigate_up()
            elif key == 'down':
                self.state_manager.navigate_down()
            elif key == 'left':
                self.state_manager.navigate_left()
            elif key == 'right':
                self.state_manager.navigate_right()
            elif key == 'enter':
                # 若存在输入缓冲，优先提交参数，避免误触发状态切换
                if self._commit_input_buffer_if_ready():
                    return

                # 检测是否“进入舵机调参确认态”，进入时恢复上次调好的舵机参数
                prev_main_state = self.shared_data.main_state
                prev_sub_state = self.shared_data.sub_state
                prev_confirm = self.shared_data.nav_confirm
                self.state_manager.handle_enter()

                # 通过导航进入DATA模式时，自动开启黑箱记录
                entered_data = (
                    prev_main_state != MainState.DATA
                    and self.shared_data.main_state == MainState.DATA
                )
                if entered_data:
                    print("已通过导航切换到DATA模式")
                    self._start_blackbox_logging()

                # 进入TUNING时先恢复一次舵机记忆参数，避免界面继续显示四个0
                entered_tuning = (
                    prev_main_state != MainState.TUNING
                    and self.shared_data.main_state == MainState.TUNING
                )
                if entered_tuning:
                    self._apply_last_tuned_servo_angles()

                entered_servo_confirm = (
                    self.shared_data.main_state == MainState.TUNING
                    and self.shared_data.sub_state == SubState.SERVO
                    and self.shared_data.nav_confirm
                    and not (
                        prev_main_state == MainState.TUNING
                        and prev_sub_state == SubState.SERVO
                        and prev_confirm
                    )
                )
                if entered_servo_confirm:
                    self._apply_last_tuned_servo_angles()
                # 进入其他调参子模式的确认态时，同样恢复各自的记忆参数
                entered_ff_confirm = (
                    self.shared_data.main_state == MainState.TUNING
                    and self.shared_data.sub_state == SubState.FEEDFORWARD
                    and self.shared_data.nav_confirm
                    and not (
                        prev_main_state == MainState.TUNING
                        and prev_sub_state == SubState.FEEDFORWARD
                        and prev_confirm
                    )
                )
                if entered_ff_confirm:
                    self._apply_last_tuned_feedforward()

                entered_pid_confirm = (
                    self.shared_data.main_state == MainState.TUNING
                    and self.shared_data.sub_state == SubState.PID
                    and self.shared_data.nav_confirm
                    and not (
                        prev_main_state == MainState.TUNING
                        and prev_sub_state == SubState.PID
                        and prev_confirm
                    )
                )
                if entered_pid_confirm:
                    self._apply_last_tuned_pid_param()

                entered_jacobian_confirm = (
                    self.shared_data.main_state == MainState.TUNING
                    and self.shared_data.sub_state == SubState.JACOBIAN
                    and self.shared_data.nav_confirm
                    and not (
                        prev_main_state == MainState.TUNING
                        and prev_sub_state == SubState.JACOBIAN
                        and prev_confirm
                    )
                )
                if entered_jacobian_confirm:
                    self._apply_last_tuned_jacobian()
            elif key == 'esc':
                self.state_manager.handle_escape()
            
            # 总开关切换（仅在AUTO/TOWER模式下有效）
            elif key == 'space':
                self._toggle_main_switch()
            
            # 'D'键：快速切换到DATA模式（任意模式尝试切入）
            elif key == 'd':
                self._switch_to_data()
            
            # 'L'键：在DATA模式下切换黑箱记录状态
            elif key == 'l' and self.shared_data.main_state == MainState.DATA:
                self._toggle_blackbox_logging()
            
            # 'S'键：在AUTO模式下切换保存开关
            elif key == 's' and self.shared_data.main_state == MainState.AUTO:
                self._toggle_save_switch()
            
            # 数字输入
            elif key in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']:
                number = int(key)
                
                # 根据当前状态和导航确认状态决定数字键功能
                if self.shared_data.main_state in [MainState.AUTO, MainState.TOWER]:
                    # 在AUTO/TOWER模式下，数字键用于预设状态
                    if number in self.preset_states:
                        self._set_preset_state(number)
                elif self.shared_data.main_state == MainState.TUNING:
                    # 在TUNING模式下，数字键用于参数输入
                    if self.shared_data.nav_confirm:
                        # 在确认状态下，数字键添加到缓冲区（用于输入多位数字）
                        self._add_digit(str(number))
                    else:
                        # 在未确认状态下，数字键用于输入数字到缓冲区
                        # 用户应该先选择参数，然后输入数字
                        self._add_digit(str(number))
                else:
                    # 在其他模式下（如STOP），数字键用于参数输入
                    self._add_digit(str(number))
            elif key in ['-', 'minus']:
                # 仅在舵机调参模式下允许输入负号
                self._handle_minus_sign()
            elif key == '.':
                self._add_decimal_point()
            elif key == 'backspace':
                self._delete_input_char()
            
            
            
        except Exception as e:
            print(f"按键处理错误: {e}")

    def _start_auto_tune(self):
        """启动一键自动调参（舵机 + 前馈）。"""
        if self.auto_tuning:
            print("自动调参已在进行中，忽略重复触发")
            return

        self.auto_tuning = True

        def worker():
            try:
                self.auto_tuner.apply_servo_and_feedforward_from_files()
            except Exception as e:
                print(f"自动调参执行失败: {e}")
            finally:
                self.auto_tuning = False

        self.auto_tune_thread = threading.Thread(target=worker)
        self.auto_tune_thread.daemon = True
        self.auto_tune_thread.start()

    def _start_pid_auto_tune(self):
        """启动一键自动调参（PID）。"""
        if self.auto_tuning:
            print("自动调参已在进行中，忽略重复触发")
            return

        self.auto_tuning = True

        def worker():
            try:
                self.auto_tuner.apply_pid_from_file()
            except Exception as e:
                print(f"PID自动调参执行失败: {e}")
            finally:
                self.auto_tuning = False

        self.auto_tune_thread = threading.Thread(target=worker)
        self.auto_tune_thread.daemon = True
        self.auto_tune_thread.start()
    
    # ==================== 状态切换方法 ====================
    def _switch_to_stop_and_reset(self):
        """切换到STOP状态并重置所有参数"""
        if self.shared_data.set_main_state(MainState.STOP):
            # 重置所有控制参数为STOP状态默认值
            self.shared_data.main_switch = 0
            self.shared_data.fan_speed = 0
            self.shared_data.servo_angles = [0.0, 0.0, 0.0, 0.0]
            self._clear_input_buffer()

    
    def _toggle_main_switch(self):
        """切换总开关状态"""
        if self.shared_data.main_state == MainState.STOP:
            # 在STOP状态下，切换到AUTO
            self.shared_data.set_main_state(MainState.AUTO)
            self.shared_data.main_switch = 1
            self.shared_data.save_switch = 0  # 进入AUTO时重置保存开关
        elif self.shared_data.main_state in [MainState.AUTO, MainState.TOWER]:
            # 在AUTO或TOWER状态下，切换到STOP
            self.shared_data.set_main_state(MainState.STOP)
            self.shared_data.main_switch = 0
            self.shared_data.fan_speed = 0
            self.shared_data.servo_angles = [0.0, 0.0, 0.0, 0.0]
        elif self.shared_data.main_state == MainState.TUNING:
            # 在TUNING状态下，不能切换开关
            pass
    
    def _switch_to_stop(self):
        """切换到STOP状态"""
        if self.shared_data.set_main_state(MainState.STOP):
            self.shared_data.main_switch = 0
            self._clear_input_buffer()
    
    def _switch_to_auto(self):
        """切换到AUTO状态"""
        if self.shared_data.set_main_state(MainState.AUTO):
            self.shared_data.main_switch = 1
            self.shared_data.save_switch = 0  # 进入AUTO时重置保存开关
            self._clear_input_buffer()
    
    def _switch_to_tower(self):
        """切换到TOWER状态"""
        if self.shared_data.set_main_state(MainState.TOWER):
            self.shared_data.main_switch = 2
            self._clear_input_buffer()
    
    def _switch_to_tuning(self):
        """切换到TUNING状态"""
        if self.shared_data.set_main_state(MainState.TUNING):
            self._clear_input_buffer()
    
    def _switch_to_data(self):
        """切换到DATA状态"""
        # 已在DATA模式时，确保黑箱记录已启动
        if self.shared_data.main_state == MainState.DATA:
            print("当前已是DATA模式")
            self._start_blackbox_logging()
            return

        # 先尝试直接切换
        switched = self.shared_data.set_main_state(MainState.DATA)

        # 若当前状态规则不允许（如AUTO/TOWER），尝试经STOP中转再进入DATA
        if not switched:
            if self.shared_data.set_main_state(MainState.STOP):
                switched = self.shared_data.set_main_state(MainState.DATA)

        if switched:
            self._clear_input_buffer()
            print("已切换到DATA模式")
            # 自动开始黑箱记录
            self._start_blackbox_logging()
        else:
            print(f"切换DATA失败，当前状态: {self.shared_data.main_state.name}")
    
    def _toggle_blackbox_logging(self):
        """切换黑箱记录状态"""
        # 这个方法需要在外部设置uart_receiver引用
        if hasattr(self, 'uart_receiver') and self.uart_receiver:
            if self.uart_receiver.toggle_blackbox_logging():
                status = self.uart_receiver.get_blackbox_logging_status()
                if status['is_logging']:
                    print(f"开始黑箱记录 ({status['record_count']}/{status['max_records']})")
                else:
                    print(f"停止黑箱记录 (共记录{status['record_count']}条)")
            else:
                print("黑箱记录切换失败")
        else:
            print("未找到UART接收器，无法控制黑箱记录")
    
    def _start_blackbox_logging(self):
        """开始黑箱记录"""
        if hasattr(self, 'uart_receiver') and self.uart_receiver:
            if self.uart_receiver.start_blackbox_logging():
                status = self.uart_receiver.get_blackbox_logging_status()
                print(f"自动开始黑箱记录 ({status['record_count']}/{status['max_records']})")
            else:
                print("黑箱记录已在进行中")
        else:
            print("未找到UART接收器，无法开始黑箱记录")
    
    def set_uart_receiver(self, uart_receiver):
        """设置UART接收器引用，用于控制黑箱记录"""
        self.uart_receiver = uart_receiver
    
    # ==================== 输入处理方法 ====================
    
    def _handle_number_input(self, number: int):
        """处理数字输入"""
        # 总是添加到缓冲区，以便支持多位数字输入
        self._add_digit(str(number))
    
    def _add_digit(self, digit: str):
        """添加数字到缓冲区"""
        self.input_buffer += digit
        self.last_input_buffer = self.input_buffer

    def _handle_minus_sign(self):
        """处理负号输入（在舵机/前馈调参模式下生效）"""
        if not (
            self.shared_data.main_state == MainState.TUNING
            and self.shared_data.sub_state in (SubState.SERVO, SubState.FEEDFORWARD)
        ):
            return

        # 切换缓冲区开头的负号
        if self.input_buffer.startswith('-'):
            self.input_buffer = self.input_buffer[1:]
        else:
            self.input_buffer = '-' + self.input_buffer if self.input_buffer else '-'

        self.last_input_buffer = self.input_buffer
    
    def _add_decimal_point(self):
        """添加小数点"""
        if not self.input_decimal:
            if self.input_buffer == "":
                self.input_buffer = "0."
            else:
                self.input_buffer += "."
            self.input_decimal = True
            self.last_input_buffer = self.input_buffer
    
    def _delete_input_char(self):
        """删除输入字符"""
        if self.input_buffer:
            if self.input_buffer[-1] == '.':
                self.input_decimal = False
            self.input_buffer = self.input_buffer[:-1]
            self.last_input_buffer = self.input_buffer
    
    def _clear_input_buffer(self):
        """清空输入缓冲区"""
        self.input_buffer = ""
        self.input_decimal = False
        self.last_input_buffer = ""

    def _load_last_tuned_servo_angles(self):
        """加载上次舵机调参结果（仅作为舵机模式初始值）"""
        try:
            if not self.servo_persist_file.exists():
                return

            data = json.loads(self.servo_persist_file.read_text(encoding='utf-8'))
            servo_angles = data.get("servo_angles")
            if isinstance(servo_angles, list) and len(servo_angles) == 4:
                self.last_tuned_servo_angles = [float(v) for v in servo_angles]
                print(f"已加载舵机记忆参数: {self.last_tuned_servo_angles}")
        except Exception as e:
            print(f"加载舵机记忆参数失败: {e}")

    def _save_last_tuned_servo_angles(self):
        """保存舵机调参结果（仅SERVO模式提交时触发）"""
        try:
            payload = {
                "servo_angles": [float(v) for v in self.last_tuned_servo_angles],
                "saved_at": time.time()
            }
            self.servo_persist_file.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
        except Exception as e:
            print(f"保存舵机记忆参数失败: {e}")

    def _apply_last_tuned_servo_angles(self):
        """将记忆值应用到当前舵机参数（进入SERVO调参时调用）"""
        self.shared_data.servo_angles = self.last_tuned_servo_angles.copy()

    def _load_last_tuned_feedforward(self):
        """加载上次前馈调参结果"""
        try:
            if not self.feedforward_persist_file.exists():
                return

            data = json.loads(self.feedforward_persist_file.read_text(encoding='utf-8'))
            values = data.get("feedforward_values")
            if isinstance(values, list) and len(values) == 4:
                self.last_tuned_feedforward = [float(v) for v in values]
                print(f"已加载前馈记忆参数: {self.last_tuned_feedforward}")
        except Exception as e:
            print(f"加载前馈记忆参数失败: {e}")

    def _save_last_tuned_feedforward(self):
        """保存前馈调参结果"""
        try:
            payload = {
                "feedforward_values": [float(v) for v in self.last_tuned_feedforward],
                "saved_at": time.time()
            }
            self.feedforward_persist_file.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
        except Exception as e:
            print(f"保存前馈记忆参数失败: {e}")

    def _apply_last_tuned_feedforward(self):
        """将记忆值应用到当前前馈参数（进入FEEDFORWARD调参时调用）"""
        self.shared_data.feedforward_values = self.last_tuned_feedforward.copy()

    def _load_last_tuned_pid_param(self):
        """加载上次PID调参结果"""
        try:
            if not self.pid_persist_file.exists():
                return

            data = json.loads(self.pid_persist_file.read_text(encoding='utf-8'))
            pid_param = data.get("pid_param")
            if isinstance(pid_param, list) and len(pid_param) == len(self.shared_data.pid_param):
                parsed = []
                valid = True
                for row in pid_param:
                    if not (isinstance(row, list) and len(row) == len(self.shared_data.pid_param[0])):
                        valid = False
                        break
                    parsed.append([float(v) for v in row])
                if valid:
                    self.last_tuned_pid_param = parsed
                    print("已加载PID记忆参数")
        except Exception as e:
            print(f"加载PID记忆参数失败: {e}")

    def _save_last_tuned_pid_param(self):
        """保存PID调参结果"""
        try:
            payload = {
                "pid_param": [[float(v) for v in row] for row in self.last_tuned_pid_param],
                "saved_at": time.time()
            }
            self.pid_persist_file.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
        except Exception as e:
            print(f"保存PID记忆参数失败: {e}")

    def _apply_last_tuned_pid_param(self):
        """将记忆值应用到当前PID参数（进入PID调参时调用）"""
        for i in range(len(self.shared_data.pid_param)):
            for j in range(len(self.shared_data.pid_param[0])):
                self.shared_data.pid_param[i][j] = float(self.last_tuned_pid_param[i][j])

    def _load_last_tuned_jacobian(self):
        """加载上次Jacobian调参结果"""
        try:
            if not self.jacobian_persist_file.exists():
                return

            data = json.loads(self.jacobian_persist_file.read_text(encoding='utf-8'))
            matrix = data.get("jacobian_matrix")
            if isinstance(matrix, list) and len(matrix) == len(self.shared_data.jacobian_matrix):
                parsed = []
                valid = True
                for row in matrix:
                    if not (isinstance(row, list) and len(row) == len(self.shared_data.jacobian_matrix[0])):
                        valid = False
                        break
                    parsed.append([float(v) for v in row])
                if valid:
                    self.last_tuned_jacobian = parsed
                    print("已加载Jacobian记忆参数")
        except Exception as e:
            print(f"加载Jacobian记忆参数失败: {e}")

    def _save_last_tuned_jacobian(self):
        """保存Jacobian调参结果"""
        try:
            payload = {
                "jacobian_matrix": [[float(v) for v in row] for row in self.last_tuned_jacobian],
                "saved_at": time.time()
            }
            self.jacobian_persist_file.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
        except Exception as e:
            print(f"保存Jacobian记忆参数失败: {e}")

    def _apply_last_tuned_jacobian(self):
        """将记忆值应用到当前Jacobian参数（进入Jacobian调参时调用）"""
        for i in range(len(self.shared_data.jacobian_matrix)):
            for j in range(len(self.shared_data.jacobian_matrix[0])):
                self.shared_data.jacobian_matrix[i][j] = float(self.last_tuned_jacobian[i][j])
    
    def _on_navigation_changed(self, nav_row: int, nav_col: int):
        """
        导航变化回调函数
        当导航位置改变时，清空输入缓冲区
        """
        self._clear_input_buffer()
        print(f"导航位置改变: 行={nav_row}, 列={nav_col}, 已清空输入缓冲区")

    def _commit_input_buffer_if_ready(self) -> bool:
        """若输入缓冲可提交则写入参数并返回True，否则返回False"""
        if not self.input_buffer:
            return False

        # 末尾小数点视为未完成输入，不提交
        if self.input_buffer.endswith('.'):
            return False

        if self._update_param_from_buffer():
            self._clear_input_buffer()
            return True
        return False
    
    def _update_param_from_buffer(self) -> bool:
        """从缓冲区更新参数值。成功返回True，失败返回False"""
        if not self.input_buffer:
            return False
        
        try:
            if self.input_buffer.endswith('.'):
                return False
            
            value = float(self.input_buffer)
            
            # 根据当前状态和导航位置更新参数
            if self.shared_data.main_state == MainState.TUNING:
                if self.shared_data.sub_state == SubState.PID:
                    # 更新PID参数 - 使用nav_col作为参数索引
                    if 0 <= self.shared_data.selected_pid < len(self.shared_data.pid_param):
                        if 0 <= self.shared_data.nav_col < len(self.shared_data.pid_param[0]):
                            self.shared_data.pid_param[self.shared_data.selected_pid][self.shared_data.nav_col] = value
                            # 记忆并保存整张PID表
                            self.last_tuned_pid_param = [row.copy() for row in self.shared_data.pid_param]
                            self._save_last_tuned_pid_param()
                            return True
                elif self.shared_data.sub_state == SubState.JACOBIAN:
                    # 更新Jacobian矩阵
                    row = self.shared_data.nav_row
                    col = self.shared_data.nav_col
                    if 0 <= row < 3 and 0 <= col < 4:
                        self.shared_data.jacobian_matrix[row][col] = value
                        # 记忆并保存整张Jacobian
                        self.last_tuned_jacobian = [r.copy() for r in self.shared_data.jacobian_matrix]
                        self._save_last_tuned_jacobian()
                        return True
                elif self.shared_data.sub_state == SubState.SERVO:
                    # 更新舵机四个舵面值
                    servo_index = self.shared_data.nav_col
                    if 0 <= servo_index < 4:
                        self.shared_data.servo_angles[servo_index] = value
                        self.last_tuned_servo_angles = self.shared_data.servo_angles.copy()
                        self._save_last_tuned_servo_angles()
                        return True
                elif self.shared_data.sub_state == SubState.FEEDFORWARD:
                    # 更新前馈四个舵面值（独立存储）
                    servo_index = self.shared_data.nav_col
                    if 0 <= servo_index < 4:
                        self.shared_data.feedforward_values[servo_index] = value
                        self.last_tuned_feedforward = self.shared_data.feedforward_values.copy()
                        self._save_last_tuned_feedforward()
                        return True
            else:
                # 在AUTO或TOWER模式下更新参数
                if self.shared_data.nav_col == 0:  # 开关
                    self.shared_data.main_switch = int(value)
                    return True
                elif self.shared_data.nav_col == 1:  # 风扇
                    self.shared_data.fan_speed = int(value)
                    return True
                elif 2 <= self.shared_data.nav_col <= 5:  # 舵机
                    servo_index = self.shared_data.nav_col - 2
                    self.shared_data.servo_angles[servo_index] = value
                    return True
        
        except ValueError:
            return False

        return False
    
    # ==================== PID参数选择方法 ====================
    
    def _handle_pid_selection(self, pid_index: int):
        """处理PID组选择"""
        if 0 <= pid_index < len(self.shared_data.pid_param):
            self.shared_data.selected_pid = pid_index
            self._clear_input_buffer()
            print(f"已选择PID组: {self.shared_data.pid_name[pid_index]} (编码值: 0x{PID_TYPE_ENCODING.get(pid_index, 0xA1):02X})")
    
    def _select_prev_pid(self):
        """选择上一个PID"""
        if self.shared_data.selected_pid > 0:
            self.shared_data.selected_pid -= 1
            self._clear_input_buffer()
            print(f"已选择PID组: {self.shared_data.pid_name[self.shared_data.selected_pid]} (编码值: 0x{PID_TYPE_ENCODING.get(self.shared_data.selected_pid, 0xA1):02X})")
    
    def _select_next_pid(self):
        """选择下一个PID"""
        if self.shared_data.selected_pid < len(self.shared_data.pid_param) - 1:
            self.shared_data.selected_pid += 1
            self._clear_input_buffer()
            print(f"已选择PID组: {self.shared_data.pid_name[self.shared_data.selected_pid]} (编码值: 0x{PID_TYPE_ENCODING.get(self.shared_data.selected_pid, 0xA1):02X})")
    
    def _select_prev_param(self):
        """选择上一个参数"""
        if self.shared_data.selected_param > 0:
            self.shared_data.selected_param -= 1
            self._clear_input_buffer()
    
    def _select_next_param(self):
        """选择下一个参数"""
        if self.shared_data.selected_param < len(self.shared_data.param_names) - 1:
            self.shared_data.selected_param += 1
            self._clear_input_buffer()
    
    def _toggle_save_switch(self):
        """切换保存开关状态（仅AUTO模式有效，toggle 0↔1）"""
        self.shared_data.save_switch = 1 if self.shared_data.save_switch == 0 else 0
        status = "ON" if self.shared_data.save_switch == 1 else "OFF"
        print(f"保存开关: {status}")

    # ==================== 预设状态方法 ====================
    
    def _set_preset_state(self, preset_num: int):
        """设置预设状态"""
        if preset_num in self.preset_states:
            preset = self.preset_states[preset_num]
            self.shared_data.main_switch = preset["main_switch"]
            self.shared_data.fan_speed = preset["fan_speed"]
            self.shared_data.servo_angles = preset["servo_angles"].copy()
            
            # 根据开关状态设置主状态
            if preset["main_switch"] == 0:
                self.shared_data.set_main_state(MainState.STOP)
            else:
                current_state = self.shared_data.main_state
                if current_state in [MainState.AUTO,MainState.TOWER]:
                    pass
                else:
                    self.shared_data.set_main_state(MainState.AUTO)
                    self.shared_data.save_switch = 0  # 新进入AUTO时重置保存开关
                
    # ==================== 获取状态方法 ====================
    
    def get_current_input(self):
        """获取当前输入状态"""
        return {
            "main_switch": self.shared_data.main_switch,
            "fan_speed": self.shared_data.fan_speed,
            "servo_angles": self.shared_data.servo_angles.copy(),
            "nav_row": self.shared_data.nav_row,
            "nav_col": self.shared_data.nav_col,
            "nav_confirm": self.shared_data.nav_confirm,
            "input_buffer": self.input_buffer,
            "main_state": self.shared_data.main_state.name,
            "sub_state": self.shared_data.sub_state.name if self.shared_data.main_state == MainState.TUNING else "N/A"
        }
    
    def get_navigation_info(self):
        """获取导航信息"""
        return self.state_manager.get_nav_info()
    
    def get_current_selection(self):
        """获取当前选择的项目描述"""
        return self.state_manager.get_current_selection()
