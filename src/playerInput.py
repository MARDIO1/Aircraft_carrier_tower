"""
键盘输入捕获模块
负责捕获键盘信号并更新共享数据
"""

import keyboard
import threading
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
        
    def start_capture(self):
        """开始捕获键盘输入"""
        if self.running:
            return
            
        self.running = True
        self.input_thread = threading.Thread(target=self._input_loop)
        self.input_thread.daemon = True
        self.input_thread.start()
        print("键盘输入捕获已启动")
        
    def stop_capture(self):
        """停止捕获键盘输入"""
        self.running = False
        if self.input_thread:
            self.input_thread.join(timeout=1.0)
        print("键盘输入捕获已停止")
        
    def _input_loop(self):
        """键盘输入循环"""
        while self.running:
            try:
                # 检测空格键 - 总开关切换
                if keyboard.is_pressed('space'):
                    self._toggle_main_switch()
                    keyboard.read_key()  # 等待按键释放
                    
                # 检测数字1键 - 预设状态1
                if keyboard.is_pressed('1'):
                    self._set_preset_state(1)
                    keyboard.read_key()  # 等待按键释放
                    
                # 检测数字2键 - 预设状态2
                if keyboard.is_pressed('2'):
                    self._set_preset_state(2)
                    keyboard.read_key()  # 等待按键释放
                    
                # 短暂休眠避免CPU占用过高
                keyboard._msleep(50)
                
            except Exception as e:
                print(f"键盘输入捕获错误: {e}")
                break
                
    def _toggle_main_switch(self):
        """切换总开关状态"""
        self.shared_data.main_switch = 1 if self.shared_data.main_switch == 0 else 0
        print(f"总开关切换为: {self.shared_data.main_switch}")
        
    def _set_preset_state(self, preset_num):
        """设置预设状态"""
        if preset_num == 1:
            # 预设状态1
            self.shared_data.main_switch = 1
            self.shared_data.fan_speed = 1000
            self.shared_data.servo_angles = [500, 500, 500, 500]
            print("已设置预设状态1")
        elif preset_num == 2:
            # 预设状态2
            self.shared_data.main_switch = 1
            self.shared_data.fan_speed = 2000
            self.shared_data.servo_angles = [1000, 1000, 1000, 1000]
            print("已设置预设状态2")
        else:
            print(f"未知的预设状态: {preset_num}")
            
    def get_current_input(self):
        """获取当前输入状态"""
        return {
            "main_switch": self.shared_data.main_switch,
            "fan_speed": self.shared_data.fan_speed,
            "servo_angles": self.shared_data.servo_angles.copy()
        }
