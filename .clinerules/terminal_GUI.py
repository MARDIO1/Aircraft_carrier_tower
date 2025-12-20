"""
控制台GUI模块
使用\b进行缩进刷新，显示三行信息
"""

import threading
import time
import sys
import os

class TerminalGUI:
    def __init__(self, uart_sender, initializer, player_input, shared_data=None):
        """
        初始化控制台GUI
        Args:
            uart_sender: 串口发送器对象
            initializer: 初始化器对象
            player_input: 键盘输入对象
            shared_data: 共享数据对象（ProtocolData实例）
        """
        self.uart_sender = uart_sender
        self.initializer = initializer
        self.player_input = player_input
        self.shared_data = shared_data
        self.running = False
        self.gui_thread = None
        
    def start_display(self):
        """开始显示GUI"""
        if self.running:
            return
            
        self.running = True
        self.gui_thread = threading.Thread(target=self._display_loop)
        self.gui_thread.daemon = True
        self.gui_thread.start()
        print("控制台GUI已启动")
        
    def stop_display(self):
        """停止显示GUI"""
        self.running = False
        if self.gui_thread:
            self.gui_thread.join(timeout=1.0)
        print("控制台GUI已停止")
        
    def _display_loop(self):
        """GUI显示循环"""
        # 显示静态信息（只显示一次）
        self._display_static_info()
        
        # 记录当前显示行数
        self.display_lines = 4  # 四行动态信息（发送、COM口、按键、接收）
        
        while self.running:
            try:
                # 更新动态信息
                self._update_dynamic_info()
                time.sleep(0.1)  # 50Hz刷新间隔 (20ms)  降频
                
            except Exception as e:
                print(f"GUI显示错误: {e}")
                break
                
    def _display_static_info(self):
        """显示静态信息（只显示一次）"""
        print("航模地面站控制台")
        print("=" * 40)
        print("操作提示:")
        print("空格键: 切换总开关")
        print("数字1: 预设状态1 (开关=1 风扇=1000 舵机=0.0)")
        print("数字2: 预设状态2 (开关=1 风扇=1500 舵机=0.0)")
        print("Ctrl+C: 退出程序")
        print("=" * 40)
        print("状态显示:")
        
    def _update_dynamic_info(self):
        """更新动态信息（使用四行显示，包含接收数据）"""
        # 获取所有状态信息
        last_sent = self.uart_sender.get_last_sent_info()
        config = self.initializer.get_current_config()
        com_port = config["com_port"] if config["com_port"] else "未连接"
        input_state = self.player_input.get_current_input()
        
        # 构建接收数据显示字符串
        if self.shared_data:
            # 格式化接收数据
            switch = self.shared_data.received_switch
            #acc_x = self.shared_data.received_acc_x
            #acc_y = self.shared_data.received_acc_y
           # acc_z = self.shared_data.received_acc_z
            #gyro_x = self.shared_data.received_gyro_x
           # gyro_y = self.shared_data.received_gyro_y
           # gyro_z = self.shared_data.received_gyro_z
            angle_roll = self.shared_data.received_angle_roll
            angle_pitch = self.shared_data.received_angle_pitch
            angle_yaw = self.shared_data.received_angle_yaw
            
            # 检查是否有有效数据（不是默认值）
            has_data = (switch != 0 or 
                       #abs(acc_x) > 0.001 or abs(acc_y) > 0.001 or abs(acc_z) > 0.001 or
                       #abs(gyro_x) > 0.001 or abs(gyro_y) > 0.001 or abs(gyro_z) > 0.001 or
                       abs(angle_roll) > 0.001 or abs(angle_pitch) > 0.001 or abs(angle_yaw) > 0.001)
            
            if has_data:
                # 格式化显示，限制小数位数
                line4 = f"接收数据: 开关={switch}  角度=({angle_roll:.1f},{angle_pitch:.1f},{angle_yaw:.1f})"
            else:
                line4 = "接收数据: 无数据"
        else:
            line4 = "接收数据: 未连接"
        
        # 构建四行显示内容
        line1 = f"上一次发送的信息: {last_sent}"
        line2 = f"当前COM口和模式: {com_port}"
        line3 = f"当前按键状态: 开关={input_state['main_switch']} 风扇={input_state['fan_speed']} 舵机={input_state['servo_angles']}"
        
        # 使用光标移动技术更新四行
        # 移动到第一行动态信息位置
        sys.stdout.write(f"\r\033[11A")  # 向上移动11行到动态信息开始位置
        sys.stdout.write(f"\r\033[K{line1}\n")  # 清除行并显示第一行
        sys.stdout.write(f"\033[K{line2}\n")    # 清除行并显示第二行
        sys.stdout.write(f"\033[K{line3}\n")    # 清除行并显示第三行
        sys.stdout.write(f"\033[K{line4}")      # 清除行并显示第四行（不换行）
        sys.stdout.flush()
        
    def get_display_info(self):
        """获取显示信息"""
        last_sent = self.uart_sender.get_last_sent_info()
        config = self.initializer.get_current_config()
        input_state = self.player_input.get_current_input()
        
        # 获取接收数据信息
        if self.shared_data:
            switch = self.shared_data.received_switch
            angle_roll = self.shared_data.received_angle_roll
            angle_pitch = self.shared_data.received_angle_pitch
            angle_yaw = self.shared_data.received_angle_yaw
            received_info = f"开关={switch} 角度=({angle_roll:.2f},{angle_pitch:.2f},{angle_yaw:.2f})"
        else:
            received_info = "未连接"
        
        return {
            "last_sent": last_sent,
            "com_port": config["com_port"] if config["com_port"] else "未连接",
            "current_state": f"开关={input_state['main_switch']} 风扇={input_state['fan_speed']} 舵机={input_state['servo_angles']}",
            "received_data": received_info
        }
