import sys
import os

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from protocol import Protocol
from initial import SerialInitializer
from playerInput import PlayerInput
from GUI_enhanced import EnhancedGroundStationGUI

def main():
    """主程序入口"""
    print("航模地面站启动中...")
    
    # 初始化各模块
    protocol = Protocol()
    serial_initializer = SerialInitializer()
    player_input = PlayerInput()
    
    # 启动输入捕获
    player_input.start_input_capture()
    
    # 创建并运行增强版GUI
    gui = EnhancedGroundStationGUI(protocol, serial_initializer, player_input)
    
    try:
        gui.run()
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"程序运行错误: {e}")
    finally:
        # 清理资源
        serial_initializer.close_serial()
        player_input.stop_input_capture()
        print("程序已退出")

if __name__ == "__main__":
    main()
