"""
控制台GUI模块
使用\b进行缩进刷新，显示三行信息
"""

import threading
import time
import sys

class TerminalGUI:
    def __init__(self, uart_sender, initializer, player_input):
        """
        初始化控制台GUI
        Args:
            uart_sender: 串口发送器对象
            initializer: 初始化器对象
            player_input: 键盘输入对象
        """
        self.uart_sender = uart_sender
        self.initializer = initializer
        self.player_input = player_input
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
        while self.running:
            try:
                # 清屏并显示三行信息
                self._clear_screen()
                self._display_lines()
                time.sleep(0.1)  # 100ms刷新间隔
                
            except Exception as e:
                print(f"GUI显示错误: {e}")
                break
                
    def _clear_screen(self):
        """清屏"""
        sys.stdout.write('\033[2J\033[H')  # ANSI转义序列清屏
        sys.stdout.flush()
        
    def _display_lines(self):
        """显示三行信息"""
        # 第一行: 上一次发送的信息
        last_sent = self.uart_sender.get_last_sent_info()
        print(f"上一次发送: {last_sent}")
        
        # 第二行: 当前的COM口和模式
        config = self.initializer.get_current_config()
        com_port = config["com_port"] if config["com_port"] else "未连接"
        mode = "运行中" if self.running else "已停止"
        print(f"COM口: {com_port} | 模式: {mode}")
        
        # 第三行: 当前按下的键盘按键状态
        input_state = self.player_input.get_current_input()
        print(f"当前状态: 开关={input_state['main_switch']} 风扇={input_state['fan_speed']} 舵机={input_state['servo_angles']}")
        
        # 添加操作提示
        print("\n操作提示:")
        print("空格键: 切换总开关")
        print("数字1: 预设状态1")
        print("数字2: 预设状态2")
        print("Ctrl+C: 退出程序")
        
    def get_display_info(self):
        """获取显示信息"""
        last_sent = self.uart_sender.get_last_sent_info()
        config = self.initializer.get_current_config()
        input_state = self.player_input.get_current_input()
        
        return {
            "last_sent": last_sent,
            "com_port": config["com_port"] if config["com_port"] else "未连接",
            "current_state": f"开关={input_state['main_switch']} 风扇={input_state['fan_speed']} 舵机={input_state['servo_angles']}"
        }
