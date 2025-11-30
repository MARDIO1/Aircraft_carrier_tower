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
        # 设置按键事件监听器
        keyboard.on_press(self._on_key_press)
        
        # 保持线程运行
        while self.running:
            time.sleep(0.1)  # 避免CPU占用过高
                
    def _on_key_press(self, event):
        """按键事件处理"""
        if not self.running:
            return
            
        try:
            key = event.name
            
            if key == 'space':
                self._toggle_main_switch()
            elif key == '1':
                self._set_preset_state(1)
            elif key == '2':
                self._set_preset_state(2)
                
        except Exception as e:
            print(f"按键处理错误: {e}")
                
    def _toggle_main_switch(self):
        """切换总开关状态"""
        self.shared_data.main_switch = 1 if self.shared_data.main_switch == 0 else 0
        print(f"总开关切换为: {self.shared_data.main_switch}")
        
    def _set_preset_state(self, preset_num):
        """设置预设状态"""
        if preset_num == 1:
            # 预设状态1: 总开关开 风扇1000 舵机45 45 45 45
            self.shared_data.main_switch = 1
            self.shared_data.fan_speed = 1000
            self.shared_data.servo_angles = [45, 45, 45, 45]
            print("已设置预设状态1: 开关=1 风扇=1000 舵机=[45, 45, 45, 45]")
        elif preset_num == 2:
            # 预设状态2: 总开关开 风扇1500 舵机60 60 60 60
            self.shared_data.main_switch = 1
            self.shared_data.fan_speed = 1500
            self.shared_data.servo_angles = [0, 0, 0, 0]
            print("已设置预设状态2: 开关=1 风扇=1500 舵机=[60, 60, 60, 60]")
        else:
            print(f"未知的预设状态: {preset_num}")
            
    def get_current_input(self):
        """获取当前输入状态"""
        return {
            "main_switch": self.shared_data.main_switch,
            "fan_speed": self.shared_data.fan_speed,
            "servo_angles": self.shared_data.servo_angles.copy()
        }
