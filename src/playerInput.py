"""
键盘输入捕获模块 - 二维数组导航版本
负责捕获键盘信号并更新共享数据，支持二维数组导航
"""

import keyboard
import threading
import time
from protocol import ProtocolData, MainState, SubState, StateMachineManager

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
        
        # 输入缓冲区
        self.input_buffer = ""
        self.input_decimal = False
        self.last_input_buffer = ""
        
        # 预设状态
        self.preset_states = {
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
                self.state_manager.handle_enter()
            elif key == 'esc':
                self.state_manager.handle_escape()
            
            # 总开关切换（仅在AUTO/TOWER模式下有效）
            elif key == 'space':
                self._toggle_main_switch()
            
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
            elif key == '.':
                self._add_decimal_point()
            elif key == 'backspace':
                self._delete_input_char()
            
            
            
        except Exception as e:
            print(f"按键处理错误: {e}")
    
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
    
    # ==================== 输入处理方法 ====================
    
    def _handle_number_input(self, number: int):
        """处理数字输入"""
        # 总是添加到缓冲区，以便支持多位数字输入
        self._add_digit(str(number))
    
    def _add_digit(self, digit: str):
        """添加数字到缓冲区"""
        self.input_buffer += digit
        self._update_param_from_buffer()
        self.last_input_buffer = self.input_buffer
    
    def _add_decimal_point(self):
        """添加小数点"""
        if not self.input_decimal:
            if self.input_buffer == "":
                self.input_buffer = "0."
            else:
                self.input_buffer += "."
            self.input_decimal = True
            self._update_param_from_buffer()
            self.last_input_buffer = self.input_buffer
    
    def _delete_input_char(self):
        """删除输入字符"""
        if self.input_buffer:
            if self.input_buffer[-1] == '.':
                self.input_decimal = False
            self.input_buffer = self.input_buffer[:-1]
            self._update_param_from_buffer()
            self.last_input_buffer = self.input_buffer
    
    def _clear_input_buffer(self):
        """清空输入缓冲区"""
        self.input_buffer = ""
        self.input_decimal = False
        self.last_input_buffer = ""
    
    def _on_navigation_changed(self, nav_row: int, nav_col: int):
        """
        导航变化回调函数
        当导航位置改变时，清空输入缓冲区
        """
        self._clear_input_buffer()
        print(f"导航位置改变: 行={nav_row}, 列={nav_col}, 已清空输入缓冲区")
    
    def _update_param_from_buffer(self):
        """从缓冲区更新参数值"""
        if not self.input_buffer:
            return
        
        try:
            if self.input_buffer.endswith('.'):
                return
            
            value = float(self.input_buffer)
            
            # 根据当前状态和导航位置更新参数
            if self.shared_data.main_state == MainState.TUNING:
                if self.shared_data.sub_state == SubState.PID:
                    # 更新PID参数 - 使用nav_col作为参数索引
                    if 0 <= self.shared_data.selected_pid < len(self.shared_data.pid_param):
                        if 0 <= self.shared_data.nav_col < len(self.shared_data.pid_param[0]):
                            self.shared_data.pid_param[self.shared_data.selected_pid][self.shared_data.nav_col] = value
                elif self.shared_data.sub_state == SubState.JACOBIAN:
                    # 更新Jacobian矩阵
                    row = self.shared_data.nav_row
                    col = self.shared_data.nav_col
                    if 0 <= row < 3 and 0 <= col < 4:
                        self.shared_data.jacobian_matrix[row][col] = value
                elif self.shared_data.sub_state == SubState.SERVO:
                    # 更新舵机角度
                    servo_index = self.shared_data.nav_col
                    if 0 <= servo_index < 4:
                        self.shared_data.servo_angles[servo_index] = value
            else:
                # 在AUTO或TOWER模式下更新参数
                if self.shared_data.nav_col == 0:  # 开关
                    self.shared_data.main_switch = int(value)
                elif self.shared_data.nav_col == 1:  # 风扇
                    self.shared_data.fan_speed = int(value)
                elif 2 <= self.shared_data.nav_col <= 5:  # 舵机
                    servo_index = self.shared_data.nav_col - 2
                    self.shared_data.servo_angles[servo_index] = value
        
        except ValueError:
            pass
    
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
                self.shared_data.set_main_state(MainState.AUTO)
    
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
