#!/usr/bin/env python3
"""
增强功能演示脚本
展示风扇转速和舵机角度控制的完整功能
"""

import sys
import os
import time
import threading

# 添加当前目录到Python路径
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from protocol import Protocol
from playerInput import PlayerInput

class EnhancedFeaturesDemo:
    def __init__(self):
        self.protocol = Protocol()
        self.player_input = PlayerInput()
        self.is_running = False
        self.demo_thread = None
        
    def start_demo(self):
        """开始演示"""
        print("=== 航模地面站增强功能演示 ===")
        print("此演示展示风扇转速和舵机角度控制功能")
        print("=" * 50)
        
        self.is_running = True
        self.demo_thread = threading.Thread(target=self._demo_loop)
        self.demo_thread.daemon = True
        self.demo_thread.start()
        
        print("演示已启动，按Ctrl+C停止")
        
    def stop_demo(self):
        """停止演示"""
        self.is_running = False
        if self.demo_thread:
            self.demo_thread.join(timeout=2.0)
        print("\n演示已停止")
    
    def _demo_loop(self):
        """演示循环"""
        demo_sequence = [
            # (开关状态, 风扇转速, [舵机1, 舵机2, 舵机3, 舵机4], 描述)
            (0, 0, [90, 90, 90, 90], "系统关闭状态"),
            (1, 0, [90, 90, 90, 90], "系统开启，风扇停止"),
            (1, 250, [90, 90, 90, 90], "风扇低速运行"),
            (1, 500, [90, 90, 90, 90], "风扇中速运行"),
            (1, 750, [90, 90, 90, 90], "风扇高速运行"),
            (1, 1000, [90, 90, 90, 90], "风扇全速运行"),
            (1, 500, [45, 135, 90, 90], "舵机1和2角度变化"),
            (1, 500, [90, 90, 30, 150], "舵机3和4角度变化"),
            (1, 750, [0, 180, 90, 90], "舵机极限角度测试"),
            (1, 250, [60, 120, 45, 135], "综合控制测试"),
            (0, 0, [90, 90, 90, 90], "系统关闭")
        ]
        
        step = 0
        while self.is_running and step < len(demo_sequence):
            switch_cmd, fan_rpm, servo_angles, description = demo_sequence[step]
            
            # 更新player_input
            self.player_input.throttle = 1.0 if switch_cmd else 0.0
            self.player_input.fan_rpm = fan_rpm
            self.player_input.servo_angles = servo_angles.copy()
            
            # 编码数据包
            data = self.protocol.encode_up_frame(switch_cmd, fan_rpm, servo_angles)
            
            # 显示当前状态
            print(f"\n步骤 {step + 1}: {description}")
            print(f"  开关状态: {'开启' if switch_cmd else '关闭'}")
            print(f"  风扇转速: {fan_rpm} RPM")
            print(f"  舵机角度: {servo_angles}")
            print(f"  数据包: {data.hex() if data else '编码失败'}")
            print(f"  数据包长度: {len(data) if data else 0} 字节")
            
            # 模拟发送数据
            print("  [模拟发送数据...]")
            
            step += 1
            time.sleep(2)  # 每个步骤间隔2秒
    
    def show_protocol_details(self):
        """显示协议详细信息"""
        print("\n" + "=" * 50)
        print("协议详细信息:")
        print(f"  上行数据包大小: {self.protocol.UP_FRAME_SZ} 字节")
        print(f"  下行数据包大小: {self.protocol.DOWN_FRAME_SZ} 字节")
        print(f"  上行包头: 0x{self.protocol.UP_HEADER:02X}")
        print(f"  上行包尾: 0x{self.protocol.UP_TAIL:02X}")
        print(f"  下行包头: 0x{self.protocol.DOWN_HEADER:02X}")
        print(f"  下行包尾: 0x{self.protocol.DOWN_TAIL:02X}")
        
        print("\n数据包结构:")
        print("  上行数据包 (14字节):")
        print("    - 包头: 1字节 (0xAA)")
        print("    - 开关命令: 1字节 (0=关, 1=开)")
        print("    - 风扇转速: 2字节 (小端序, 0-1000)")
        print("    - 舵机角度[4]: 8字节 (4个2字节小端序, 0-180)")
        print("    - 包尾: 1字节 (0xBB)")
        print("    - CRC校验: 1字节")
        
        print("\n  下行数据包 (40字节):")
        print("    - 包头: 1字节 (0xCC)")
        print("    - 上次开关状态: 1字节")
        print("    - 陀螺仪数据[9]: 36字节 (9个4字节浮点数)")
        print("    - 包尾: 1字节 (0xDD)")
        print("    - CRC校验: 1字节")
    
    def show_gui_features(self):
        """显示GUI功能特性"""
        print("\n" + "=" * 50)
        print("GUI界面功能:")
        print("  ✓ 串口连接管理")
        print("  ✓ 系统开关控制滑块")
        print("  ✓ 风扇转速控制滑块 (0-1000 RPM)")
        print("  ✓ 4个舵机角度控制滑块 (0-180°)")
        print("  ✓ 实时数值显示")
        print("  ✓ 发送完整数据功能")
        print("  ✓ 接收数据显示区域")
        print("  ✓ 键盘快捷键支持")
        
        print("\n键盘控制:")
        print("  W/S: 油门控制")
        print("  Q/E: 风扇转速控制")
        print("  1/2: 舵机1角度控制")
        print("  3/4: 舵机2角度控制")
        print("  5/6: 舵机3角度控制")
        print("  7/8: 舵机4角度控制")

def main():
    """主演示函数"""
    demo = EnhancedFeaturesDemo()
    
    try:
        # 显示协议信息
        demo.show_protocol_details()
        
        # 显示GUI功能
        demo.show_gui_features()
        
        # 开始动态演示
        print("\n" + "=" * 50)
        print("开始动态演示...")
        demo.start_demo()
        
        # 等待演示完成或用户中断
        try:
            while demo.is_running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n用户中断演示")
        finally:
            demo.stop_demo()
            
    except Exception as e:
        print(f"演示过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
