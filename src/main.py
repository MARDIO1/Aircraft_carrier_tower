"""
主程序入口
负责启动和管理所有线程
"""

import signal
import sys
import time
from protocol import ProtocolData
from initial import Initializer
from playerInput import PlayerInput
from UART_send import UARTSender
from UART_receive import UARTReceiver
from consle import Consle
# import sys
# sys.stdout = open('nul', 'w')  # Windows系统 - 已禁用，以便查看输出
# sys.stderr = open('nul', 'w')  # Windows系统 - 已禁用，以便查看输出


class AircraftCarrierTower:
    def __init__(self):
        """初始化地面站控制塔"""
        # 共享数据对象
        self.shared_data = ProtocolData()
        #impotant
        # 初始化各个模块
        self.initializer = Initializer()
        self.player_input = PlayerInput(self.shared_data)
        self.uart_sender = None
        self.uart_receiver = None
        self.terminal_gui = None
        
        # 运行状态
        self.running = False
        
    def initialize(self):
        """初始化系统"""
        print("正在初始化航模地面站...")
        
        try:
            # 初始化串口
            if not self.initializer.initialize_serial():
                print("串口初始化失败，程序退出")
                return False
                
            # 初始化串口发送器
            self.uart_sender = UARTSender(self.initializer.serial_port, self.shared_data)
            
            # 初始化串口接收器
            self.uart_receiver = UARTReceiver(self.initializer.serial_port, self.shared_data)
            
            # 初始化控制台GUI
            self.terminal_gui = Consle(self.uart_sender, self.initializer, self.player_input, self.shared_data)
            
            print("系统初始化完成")
            return True
            
        except Exception as e:
            print(f"系统初始化失败: {e}")
            return False
            
    def start(self):
        """启动系统"""
        if not self.initialize():
            return
            
        self.running = True
        
        try:
            # 启动各个模块
            self.player_input.start_capture()
            self.uart_sender.start_sending()
            self.uart_receiver.start_receiving()
            self.terminal_gui.start_display()
            
            print("系统已启动，按Ctrl+C退出")
            
            # 主循环
            while self.running:
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\n收到中断信号，正在关闭系统...")
        except Exception as e:
            print(f"系统运行错误: {e}")
        finally:
            self.stop()
            
    def stop(self):
        """停止系统"""
        self.running = False
        
        # 停止各个模块
        if self.terminal_gui:
            self.terminal_gui.stop_display()
        if self.uart_sender:
            self.uart_sender.stop_sending()
        if self.uart_receiver:
            self.uart_receiver.stop_receiving()
        if self.player_input:
            self.player_input.stop_capture()
        if self.initializer:
            self.initializer.close_serial()
            
        print("系统已安全关闭")
        
def signal_handler(sig, frame):
    """信号处理函数"""
    print("\n收到中断信号，正在关闭系统...")
    sys.exit(0)

def main():
    """主函数"""
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    
    # 创建并启动地面站
    tower = AircraftCarrierTower()
    tower.start()

if __name__ == "__main__":
    main()
