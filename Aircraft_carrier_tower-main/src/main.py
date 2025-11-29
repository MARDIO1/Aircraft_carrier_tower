import sys
import argparse
import logging
from command import CommandControl
def show_welcome():
    """显示欢迎信息"""
    print("="*60)
    print("航模地面站 - 命令行控制界面")
    print("="*60)
    print("输入‘help'查看可用命令")
    print("输入'exit'退出程序")
    print()

def show_help():
    """显示帮助信息"""
    print ("\n可用命令：")
    print("  list                    - 列出可用串口")
    print("  connect <端口> [波特率] - 连接串口 (默认115200)")
    print("  disconnect              - 断开串口连接")
    print("  set throttle <值>       - 设置油门值 (0-65535)")
    print("  set switch <值>         - 设置总开关 (0=关, 1=开, 2=特殊模式)")
    print("  set servo <角度列表>    - 设置4个舵机角度")
    print("  auto [间隔]             - 启动自动发送 (默认0.1秒)")
    print("  stop                    - 停止自动发送")
    print("  status                  - 显示当前状态")
    print("  log [行数]              - 显示最近的接收数据 (默认20行)")
    print("  log clear               - 清空日志文件")
    print("  log info                - 显示日志文件信息")
    print("  help                    - 显示此帮助信息")
    print("  exit/quit               - 退出程序")
    print()

def parse_set_command(controller, args):
    """解析set命令和日志命令"""
    if len(args) < 1:
        print("用法: set <参数> <值> 或 log [选项]")
        return
        
    # 处理日志命令
    if args[0].lower() == 'log':
        if len(args) == 1:
            # log - 显示最近20行
            controller.show_log(20)
        elif args[1].lower() == 'clear':
            # log clear - 清空日志
            controller.clear_log()
        elif args[1].lower() == 'info':
            # log info - 显示日志信息
            controller.show_log_info()
        else:
            # log <行数> - 显示指定行数
            try:
                lines = int(args[1])
                controller.show_log(lines)
            except ValueError:
                print("错误：行数必须是数字")
        return
        
    # 原有的set命令处理
    if len(args) < 2:
        print("用法: set <参数> <值>")
        return
        
    param_type = args[0].lower()
    value_str = args[1]
    
    if param_type == 'throttle':
        # 设置油门值（根据协议要求使用float类型）
        try:
            fan_rpm = float(value_str)
            controller.send_control_data(fan_rpm=fan_rpm)
        except ValueError:
            print("错误：油门值必须是数字")
            
    elif param_type == 'switch':
        # 设置总开关
        try:
            switch_cmd = int(value_str)
            if switch_cmd not in [0, 1, 2]:
                print("错误：开关值必须是0、1或2")
                return
            controller.send_control_data(switch_cmd=switch_cmd)
        except ValueError:
            print("错误：开关值必须是整数")
            
    elif param_type == 'servo':
        # 设置舵机角度（根据协议要求使用float类型）
        try:
            # 解析角度列表 (格式: 90.5,45.0,120.3,30.7)
            angles = [float(x.strip()) for x in value_str.split(',')]
            if len(angles) != 4:
                print("错误：必须提供4个舵机角度值")
                return
            controller.send_control_data(servo_angles=angles)
        except ValueError:
            print("错误：舵机角度必须是数字")
    else:
        print(f"未知参数: {param_type}")
def main():
    """主函数 - 命令行交互界面"""
    # 创建命令行控制器实例
    controller = CommandControl()
    # 显示欢迎信息
    show_welcome()

    # 主命令循环
    while True:
        try:
            # 获取用户输入
            user_input = input(">>> ").strip()
            
            # 处理空输入
            if not user_input:
                continue
                
            # 分割命令和参数
            parts = user_input.split()
            command = parts[0].lower()
            args = parts[1:]
            
            # 命令解析和执行
            if command in ['exit', 'quit']:
                # 退出程序
                print("正在退出...")
                controller.cleanup()
                break
                
            elif command == 'help':
                # 显示帮助信息
                show_help()
                
            elif command == 'list':
                # 列出可用串口
                controller.list_ports()
                
            elif command == 'connect':
                # 连接串口
                if len(args) < 1:
                    print("用法: connect <端口> [波特率]")
                    continue
                    
                port_name = args[0]
                baudrate = int(args[1]) if len(args) > 1 else 115200
                controller.connect_serial(port_name, baudrate)
                
            elif command == 'disconnect':
                # 断开串口连接
                controller.disconnect_serial()
                
            elif command == 'set':
                # 设置控制参数
                parse_set_command(controller, args)
                
            elif command == 'auto':
                # 启动自动发送
                interval = float(args[0]) if args else 0.1
                controller.start_auto_send(interval)
                
            elif command == 'stop':
                # 停止自动发送
                controller.stop_auto_send()
                
            elif command == 'status':
                # 显示状态
                controller.print_status()
                
            elif command == 'log':
                # 处理日志命令
                if len(args) == 0:
                    # log - 显示最近20行
                    controller.show_log(20)
                elif args[0].lower() == 'clear':
                    # log clear - 清空日志
                    controller.clear_log()
                elif args[0].lower() == 'info':
                    # log info - 显示日志信息
                    controller.show_log_info()
                else:
                    # log <行数> - 显示指定行数
                    try:
                        lines = int(args[0])
                        controller.show_log(lines)
                    except ValueError:
                        print("错误：行数必须是数字")
                
            else:
                print(f"未知命令: {command}")
                print("输入 'help' 查看可用命令")
                
        except KeyboardInterrupt:
            # 处理Ctrl+C
            print("\n接收到中断信号，正在退出...")
            controller.cleanup()
            break
        except Exception as e:
            print(f"命令执行错误: {e}")


if __name__ == "__main__":
    main()
