"""
键盘输入捕获模块
负责捕获键盘信号并更新共享数据
"""

import keyboard
import threading
import time
from protocol import ProtocolData

class PlayerInput:
    def __init__(self, shared_data):
        """
        初始化键盘输入捕获
        Args:
            shared_data: 线程间共享的数据对象
        """
        self.shared_data = shared_data
        self.running = False
        self.input_thread = None
        self.input_buffer = "" #缓冲区
        self.input_decimal = False  #检测是否输入小数点
        self.last_input_buffer = ""        
    def start_capture(self):
        """开始捕获键盘输入"""
        if self.running:
            return
            
        self.running = True
        self.input_thread = threading.Thread(target=self._input_loop)
        self.input_thread.daemon = True
        self.input_thread.start()
        #print("键盘输入捕获已启动")
        
    def stop_capture(self):
        """停止捕获键盘输入"""
        self.running = False
        if self.input_thread:
            self.input_thread.join(timeout=1.0)
        #print("键盘输入捕获已停止")
        
    def _input_loop(self):
        """键盘输入循环"""
        # 设置按键事件监听器
        keyboard.on_press(self._on_key_press)
        
        # 保持线程运行
        while self.running:
            time.sleep(0.1)  # 避免CPU占用过高



    #几种模式
    def _toggle_tuning_mode(self):
        """切换调参，进入退出"""
        if self.shared_data.current_mode == 'tuning':
            self._enter_stop_mode()
            #print("退出调参模式，停止")
        else:
            if self.shared_data.main_switch == 0:
                self.shared_data.current_mode = 'tuning'
                self.shared_data.tuning_active = True
                self._clear_input_buffer()
                #print("进入调参模式")
            #else:
                #print("警告：开关不为0，无法调参")


    def _enter_stop_mode(self):
        self.shared_data.main_switch = 0
        self.shared_data.fan_speed = 1000
        self.shared_data.current_mode ='STOP'
        self.shared_data.tuning_active = False
        self._clear_input_buffer()
        #print("进入停止模式：开关=0，风扇=1000")


    def _enter_run_mode(self):
        self.shared_data.main_switch = 1
        self.shared_data.current_mode = 'RUN'
        self.shared_data.tuning_active = False
        self._clear_input_buffer()
        #print("进入运行模式，开关=1")


    #选择类型和参数
    def _select_prev_pid(self):
        """选择上一个pid"""
        if self.shared_data.selected_pid > 0:
            self.shared_data.selected_pid -= 1
            self._clear_input_buffer()
            #print(f"选择PID：{self.shared_data.pid_name[self.shared_data.selected_pid]}")
        #else:
            #print("已经是第一个pid类型了")

    def _select_next_pid(self):
        """选择下一个pid"""
        if self.shared_data.selected_pid < len(self.shared_data.pid_param)-1:
            self.shared_data.selected_pid += 1
            self._clear_input_buffer()
            #print(f"选择PID：{self.shared_data.pid_name[self.shared_data.selected_pid]}")
        #else:
            #print("已经是最后一个pid类型了")

    def _select_prev_param(self):
        """选择上一个参数"""
        if self.shared_data.selected_param > 0:
            self.shared_data.selected_param -= 1
            self._clear_input_buffer()
            #print(f"选择参数：{self.shared_data.param_names[self.shared_data.selected_param]}")
        #else:
            #print("已经是第一个参数了")

    def _select_next_param(self):
        """选择下一个参数"""
        if self.shared_data.selected_param < len(self.shared_data.param_names)-1:
            self.shared_data.selected_param += 1
            self._clear_input_buffer()
            #print(f"选择参数：{self.shared_data.param_names[self.shared_data.selected_param]}")
        #else:
            #print("已经是最后一个参数了")


    #数值输入
    def _add_digit(self,digit):
        """添加数字到缓冲区"""
        self.input_buffer += digit
        #print(f"输入数值：{self.input_buffer}")
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
            #print(f"输入数值：{self.input_buffer}")
            self._update_param_from_buffer()
            self.last_input_buffer = self.input_buffer

    
    def _delete_input_char(self):
        """删除输入字符"""
        if self.input_buffer:
            deleted_char = self.input_buffer[-1]
            #检查是否删了小数点
            if self.input_buffer[-1] == '.':
                self.input_decimal = False

            self.input_buffer = self.input_buffer[:-1]
            
            #if self.input_buffer:
                #print(f"删除 '{deleted_char}',当前:{self.input_buffer}")
            #else:
                #print("删除字符，缓冲区已清空")
            self._update_param_from_buffer()
            self.last_input_buffer = self.input_buffer

    def _clear_input_buffer(self):
        """清空缓冲区"""
        self.input_buffer = ""
        self.input_decimal = False
        self.last_input_buffer = self.input_buffer
    
    def _update_param_from_buffer(self):
        """从缓冲区更新参数值"""
        if not self.input_buffer:
            return 
        
        try:
            #尝试解析缓冲区内容
            if self.input_buffer.endswith('.'):
                return
            value = float(self.input_buffer)
            
            #应用边界检查
            param_name = self.shared_data.param_names[self.shared_data.selected_param]
            if param_name in ["kp","ki","kd","积分限幅","正输出限幅"]:
                value = max(0.0,value)
            elif param_name == "负输出限幅":
                value = min(0.0,value)
            #更新参数值
            old_value = self.shared_data.pid_param[self.shared_data.selected_pid][self.shared_data.selected_param]
            self.shared_data.pid_param[self.shared_data.selected_pid][self.shared_data.selected_param] = value
            #print(f"参数更新：{self.shared_data.pid_name[self.shared_data.selected_pid]} - "
                  #f"{param_name}: {old_value:.3f}->{value:.3f}")
        except ValueError:
            pass

    
    def _on_key_press(self, event):
        """按键事件处理"""
        if not self.running:
            return
            
        try:
            key = event.name
            
            if key == 'space':
                self._toggle_main_switch()
            elif key == 't':
                self._toggle_tuning_mode()
            elif key == 's':
                self._enter_stop_mode()
            elif key == 'r':
                self._enter_run_mode()
            elif self.shared_data.current_mode == 'tuning' and self.shared_data.tuning_active:
                #选择pid和参数
                if key == 'a':
                    self._select_prev_pid()
                elif key == 'd':
                    self._select_next_pid()
                elif key == 'q':
                    self._select_prev_param()
                elif key == 'e':
                    self._select_next_param()
                #输入数值和发送
                elif key == 'enter':
                    self._send_current_pid()
                elif key == 'backspace':
                    self._delete_input_char()
                elif key == '.':
                    self._add_decimal_point()
                elif key in ['0', '1','2','3','4','5','6','7','8','9']:
                    self._add_digit(key)
                    
            elif key == '1':
                self._set_preset_state(1)
            elif key == '2':
                self._set_preset_state(2)
            elif key == '3':
                self._set_preset_state(3)
            elif key == '4':
                self._set_preset_state(4)
            elif key == '5':
                self._set_preset_state(5)
            elif key == '6':
                self._set_preset_state(6)
            elif key == '7':
                self._set_preset_state(7)
            elif key == '8':
                self._set_preset_state(8)
            elif key == '9':
                self._set_preset_state(9)
            
            
        except Exception as e:
            print(f"按键处理错误: {e}")
                
    def _toggle_main_switch(self):
        """切换总开关状态"""
        self.shared_data.main_switch = 1 if self.shared_data.main_switch == 0 else 0
        #print(f"总开关切换为: {self.shared_data.main_switch}")
        
    def _set_preset_state(self, preset_num):
        """设置预设状态"""
        if preset_num == 1:
            # 预设状态1: 总开关开 风扇1000 舵机0.0 0.0 0.0 0.0
            self.shared_data.main_switch = 1
            self.shared_data.fan_speed = 1000 
            self.shared_data.servo_angles = [0.0, 0.0, 0.0, 0.0]
            #print("已设置预设状态1: 开关=1 风扇=1000 舵机=[0.0, 0.0, 0.0, 0.0]")
        elif preset_num == 2:
            # 预设状态2: 总开关开 风扇1500 舵机0.0 0.0 0.0 0.0
            self.shared_data.main_switch = 1
            self.shared_data.fan_speed = 1500
            self.shared_data.servo_angles = [0.0, 0.0, 0.0, 0.0]
            #print("已设置预设状态2: 开关=1 风扇=1500 舵机=[0.0, 0.0, 0.0, 0.0]")
        elif preset_num == 3:
            # 预设状态3: 总开关开 风扇1300 舵机0.0 0.0 0.0 0.0
            self.shared_data.main_switch = 1
            self.shared_data.fan_speed = 1300
            self.shared_data.servo_angles = [0.0, 0.0, 0.0, 0.0]
            #print("已设置预设状态3: 开关=1 风扇=1300 舵机=[0.0, 0.0, 0.0, 0.0]")
        elif preset_num == 4:
            # 预设状态4: 总开关开 风扇1400 舵机0.0 0.0 0.0 0.0
            self.shared_data.main_switch = 1
            self.shared_data.fan_speed = 1400 
            self.shared_data.servo_angles = [0.0, 0.0, 0.0, 0.0]
            #print("已设置预设状态4: 开关=1 风扇=1400 舵机=[0.0, 0.0, 0.0, 0.0]")
        elif preset_num == 5:
            # 预设状态5: 总开关开 风扇1600 舵机0.0 0.0 0.0 0.0
            self.shared_data.main_switch = 1
            self.shared_data.fan_speed = 1600
            self.shared_data.servo_angles = [0.0, 0.0, 0.0, 0.0]
            #print("已设置预设状态5: 开关=1 风扇=1600 舵机=[0.0, 0.0, 0.0, 0.0]")
        elif preset_num == 6:
            # 预设状态6: 总开关开 风扇1700 舵机0.0 0.0 0.0 0.0
            self.shared_data.main_switch = 1
            self.shared_data.fan_speed = 1700
            self.shared_data.servo_angles = [0.0, 0.0, 0.0, 0.0]
            #print("已设置预设状态6: 开关=1 风扇=1700 舵机=[0.0, 0.0, 0.0, 0.0]")
        elif preset_num == 7:
            # 预设状态7: 总开关开 风扇1800 舵机0.0 0.0 0.0 0.0
            self.shared_data.main_switch = 1
            self.shared_data.fan_speed = 1800
            self.shared_data.servo_angles = [0.0, 0.0, 0.0, 0.0]
            #print("已设置预设状态7: 开关=1 风扇=1800 舵机=[0.0, 0.0, 0.0, 0.0]")
        elif preset_num == 8:
            # 预设状态8: 总开关开 风扇1900 舵机0.0 0.0 0.0 0.0
            self.shared_data.main_switch = 1
            self.shared_data.fan_speed = 1900
            self.shared_data.servo_angles = [0.0, 0.0, 0.0, 0.0]
            #print("已设置预设状态8: 开关=1 风扇=1900 舵机=[0.0, 0.0, 0.0, 0.0]")
        elif preset_num == 9:
            # 预设状态9: 总开关开 风扇1990 舵机0.0 0.0 0.0 0.0
            self.shared_data.main_switch = 1
            self.shared_data.fan_speed = 1990
            self.shared_data.servo_angles = [0.0, 0.0, 0.0, 0.0]
            #print("已设置预设状态9: 开关=1 风扇=1990 舵机=[0.0, 0.0, 0.0, 0.0]")
        else:
            print(f"未知的预设状态: {preset_num}")

    def _send_current_pid(self):
        """发送当前PID参数"""
        pid_name = self.shared_data.pid_name[self.shared_data.selected_pid]
        param_name = self.shared_data.param_names[self.shared_data.selected_param]
        param_value = self.shared_data.pid_param[self.shared_data.selected_pid][self.shared_data.selected_param]
        
        #print(f"发送PID参数: {pid_name} - {param_name} = {param_value:.3f}")
        # 注意：实际发送由UART_send.py处理，这里只打印日志       
    def get_current_input(self):
        """获取当前输入状态"""
        return {
            "main_switch": self.shared_data.main_switch,
            "fan_speed": self.shared_data.fan_speed,
            "servo_angles": self.shared_data.servo_angles.copy()
        }
