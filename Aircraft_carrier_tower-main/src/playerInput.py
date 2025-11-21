import threading
import time

class PlayerInput:
    def __init__(self):
        self.throttle = 0.0
        self.control_surfaces = [0.0, 0.0, 0.0, 0.0]  # 4个舵面角度
        self.fan_rpm = 0  # 风扇转速 (0-1000)
        self.servo_angles = [90, 90, 90, 90]  # 4个舵机角度 (0-180)
        self.is_running = False
        self.input_thread = None
        
        # 键盘映射
        self.key_mapping = {
            'w': ('throttle', 0.1),    # 增加油门
            's': ('throttle', -0.1),   # 减少油门
            'a': ('roll', -0.1),       # 左滚转
            'd': ('roll', 0.1),        # 右滚转
            'up': ('pitch', 0.1),      # 上俯仰
            'down': ('pitch', -0.1),   # 下俯仰
            'left': ('yaw', -0.1),     # 左偏航
            'right': ('yaw', 0.1),     # 右偏航
            'q': ('fan', 50),          # 增加风扇转速
            'e': ('fan', -50),         # 减少风扇转速
            '1': ('servo1', 5),        # 增加舵机1角度
            '2': ('servo1', -5),       # 减少舵机1角度
            '3': ('servo2', 5),        # 增加舵机2角度
            '4': ('servo2', -5),       # 减少舵机2角度
            '5': ('servo3', 5),        # 增加舵机3角度
            '6': ('servo3', -5),       # 减少舵机3角度
            '7': ('servo4', 5),        # 增加舵机4角度
            '8': ('servo4', -5),       # 减少舵机4角度
        }
    
    def start_input_capture(self):
        """开始捕获输入"""
        if self.is_running:
            return
        
        self.is_running = True
        self.input_thread = threading.Thread(target=self._input_loop)
        self.input_thread.daemon = True
        self.input_thread.start()
    
    def stop_input_capture(self):
        """停止捕获输入"""
        self.is_running = False
        if self.input_thread:
            self.input_thread.join(timeout=1.0)
    
    def _input_loop(self):
        """输入循环 - 需要根据实际输入设备实现"""
        print("输入捕获已启动 - 使用键盘控制:")
        print("W/S: 油门控制")
        print("A/D: 滚转控制") 
        print("↑/↓: 俯仰控制")
        print("←/→: 偏航控制")
        print("Q/E: 风扇转速控制")
        print("1/2: 舵机1角度控制")
        print("3/4: 舵机2角度控制")
        print("5/6: 舵机3角度控制")
        print("7/8: 舵机4角度控制")
        
        try:
            while self.is_running:
                # 这里需要根据实际输入设备实现
                # 目前使用简单的控制逻辑
                time.sleep(0.1)
        except Exception as e:
            print(f"输入捕获错误: {e}")
    
    def set_keyboard_input(self, key, pressed):
        """设置键盘输入状态
        Args:
            key: str 按键名称
            pressed: bool 是否按下
        """
        if key in self.key_mapping:
            control_type, value = self.key_mapping[key]
            
            if control_type == 'throttle':
                if pressed:
                    self.throttle = max(0.0, min(1.0, self.throttle + value))
            elif control_type == 'roll':
                if pressed:
                    self.control_surfaces[0] = max(-1.0, min(1.0, self.control_surfaces[0] + value))
            elif control_type == 'pitch':
                if pressed:
                    self.control_surfaces[1] = max(-1.0, min(1.0, self.control_surfaces[1] + value))
            elif control_type == 'yaw':
                if pressed:
                    self.control_surfaces[2] = max(-1.0, min(1.0, self.control_surfaces[2] + value))
            elif control_type == 'fan':
                if pressed:
                    self.fan_rpm = max(0, min(1000, self.fan_rpm + value))
            elif control_type == 'servo1':
                if pressed:
                    self.servo_angles[0] = max(0, min(180, self.servo_angles[0] + value))
            elif control_type == 'servo2':
                if pressed:
                    self.servo_angles[1] = max(0, min(180, self.servo_angles[1] + value))
            elif control_type == 'servo3':
                if pressed:
                    self.servo_angles[2] = max(0, min(180, self.servo_angles[2] + value))
            elif control_type == 'servo4':
                if pressed:
                    self.servo_angles[3] = max(0, min(180, self.servo_angles[3] + value))
    
    def get_control_data(self):
        """获取当前控制数据
        Returns:
            tuple: (throttle, control_surfaces, fan_rpm, servo_angles)
        """
        return self.throttle, self.control_surfaces.copy(), self.fan_rpm, self.servo_angles.copy()
    
    def reset_controls(self):
        """重置控制数据"""
        self.throttle = 0.0
        self.control_surfaces = [0.0, 0.0, 0.0, 0.0]
        self.fan_rpm = 0
        self.servo_angles = [90, 90, 90, 90]
    
    def set_manual_controls(self, throttle, surfaces):
        """手动设置控制数据
        Args:
            throttle: float 油门值 (0.0-1.0)
            surfaces: list[float] 4个舵面角度值 (-1.0到1.0)
        """
        self.throttle = max(0.0, min(1.0, throttle))
        if len(surfaces) == 4:
            for i in range(4):
                self.control_surfaces[i] = max(-1.0, min(1.0, surfaces[i]))
    
    def set_fan_servo_controls(self, fan_rpm, servo_angles):
        """手动设置风扇和舵机控制数据
        Args:
            fan_rpm: int 风扇转速 (0-1000)
            servo_angles: list[int] 4个舵机角度值 (0-180)
        """
        self.fan_rpm = max(0, min(1000, fan_rpm))
        if len(servo_angles) == 4:
            for i in range(4):
                self.servo_angles[i] = max(0, min(180, servo_angles[i]))
