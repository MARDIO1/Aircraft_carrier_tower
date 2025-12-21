'''
curses 控制台第一版
五行
'''
import threading
import time
import curses
from datetime import datetime
from protocol import MainState, SubState

class Consle:
    def __init__(self, uart_sender, initializer, player_input, shared_data=None):
        """
       初始化控制台
        
       
        :param uart_sender: 串口发送对象
        :param initializer: 初始化器对象
        :param player_input: 键盘输入对象
        :param shared_data: 共享数据对象（protocoldota)
        """
        self.uart_sender = uart_sender
        self.initializer = initializer
        self.player_input = player_input
        self.shared_data = shared_data
        self.running = False
        self.console_thread = None
        self.last_input_buffer = ""

        #消息队列(存储最近两条)
        self.message_queue = []
        self.max_messages = 2

        #检测变化
        self.last_mode = None
        self.last_switch = None
        self.last_fan = None
        self.last_servo = None 

    def start_display(self):
        """开始显示控制台"""
        if self.running:
            return 
        self.running = True
        self.console_thread = threading.Thread(target=self._console_loop)
        self.console_thread.daemon = True
        self.console_thread.start()
        #print("简洁控制台已启动")
    
    def stop_display(self):
        """停止显示控制台"""
        self.running = False
        if self.console_thread:
            self.console_thread.join(timeout=1.0)
        #print("控制台已停止")
    
    def add_message(self,message):
        """添加消息到队列"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_message = f"{timestamp} {message}"

        self.message_queue.append(full_message)
        if len(self.message_queue) > self.max_messages:
            self.message_queue.pop(0)

    def _console_loop(self):

        """控制台主循环 - 使用curses.wrapper"""
        print("控制台线程启动")
        try:
            curses.wrapper(self._curses_main)
        except Exception as e:
            print(f"控制台错误：{e}")
        #print("控制台线程结束")

    def _curses_main(self, stdscr):
        """curses主函数"""
        curses.noecho()
        curses.cbreak()
        stdscr.keypad(True)
        curses.curs_set(0)
    
        self.add_message("控制台启动")
    
        while self.running:
            self._draw_console(stdscr)
            time.sleep(0.02)
    
        # 清理
        curses.nocbreak()
        stdscr.keypad(False)
        curses.echo()
        curses.curs_set(1)


    def _draw_console(self,stdscr):
        """绘制控制台界面"""
        curses.curs_set(0)
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        self._draw_status_line(stdscr,0)

        self._draw_send_line(stdscr,1)

        self._draw_receive_line(stdscr,2)

        self._draw_tuning_line(stdscr,3)

        self._draw_message_line(stdscr,4)

        stdscr.refresh()

    def _draw_status_line(self,stdscr,row):
        """第一行：显示主状态和导航信息"""
        if not self.shared_data:
            stdscr.addstr(row,0,"模式：--- 开关：--- 风扇：--- 舵机：---")
            return
        
        # 获取主状态
        main_state = self.shared_data.main_state
        # 使用MainState枚举值
        if main_state == MainState.STOP:
            mode_text = "模式:STOP"
        elif main_state == MainState.AUTO:
            mode_text = "模式:AUTO"
        elif main_state == MainState.TOWER:
            mode_text = "模式:TOWER"
        elif main_state == MainState.TUNING:
            mode_text = "模式:TUNING"
        else:
            mode_text = f"模式:{main_state.name}"
        
        # 获取子状态（如果处于TUNING模式）
        if main_state == MainState.TUNING:
            sub_state = self.shared_data.sub_state
            if sub_state == SubState.SERVO:
                mode_text += "(SERVO)"
            elif sub_state == SubState.PID:
                mode_text += "(PID)"
            elif sub_state == SubState.JACOBIAN:
                mode_text += "(JACOBIAN)"
        
        switch = self.shared_data.main_switch
        switch_text = "开关:ON" if switch == 1 else "开关:OFF"

        fan_text = f"风扇:{self.shared_data.fan_speed}"

        servo_str = ','.join([f"{angle:.1f}" for angle in self.shared_data.servo_angles])
        servo_text = f"舵机:[{servo_str}]"

        # 添加导航信息
        nav_row = self.shared_data.nav_row
        nav_col = self.shared_data.nav_col
        nav_text = f"导航:[{nav_row},{nav_col}]"
        
        line = f"{mode_text} {switch_text} {fan_text} {servo_text} {nav_text}"
         
        self._check_status_changes(main_state.value, switch, self.shared_data.fan_speed, self.shared_data.servo_angles)

        stdscr.addstr(row, 0, line)
    def _check_status_changes(self, main_state, switch, fan, servo):
        """检测状态并记录"""
        current_servo_str = ','.join([f"{angle:.1f}" for angle in servo])

        if(main_state != self.last_mode or
           switch != self.last_switch or
           fan != self.last_fan or
           current_servo_str != self.last_servo):
            if main_state != self.last_mode and self.last_mode is not None:
                if main_state == MainState.STOP.value:
                    self.add_message("停止模式")
                elif main_state == MainState.AUTO.value:
                    self.add_message("自动模式")
                elif main_state == MainState.TOWER.value:
                    self.add_message("塔楼模式")
                elif main_state == MainState.TUNING.value:
                    self.add_message("调参模式")
                    
            if switch != self.last_switch and self.last_switch is not None:
                self.add_message(f"开关:{'ON' if switch == 1 else 'OFF'}")

            #更新上次状态
            self.last_mode = main_state
            self.last_switch = switch
            self.last_fan = fan
            self.last_servo = current_servo_str
    
    def _draw_send_line(self,stdscr,row):
        """绘制第二行"""
        if not self.uart_sender:
            stdscr.addstr(row, 0, "发送:---")
            return
        try:
            hex_data = self.uart_sender.get_hex_data()
            stdscr.addstr(row, 0, f"发送:{hex_data}")
        except Exception as e:
            stdscr.addstr(row, 0, f"发送:错误{str(e)[:20]}")

    def _draw_receive_line(self, stdscr, row):
        """第三行"""
        if not self.shared_data:
            stdscr.addstr(row, 0, "接收:未连接")
            return
        switch = self.shared_data.received_switch
        roll = self.shared_data.received_angle_roll
        pitch = self.shared_data.received_angle_pitch
        yaw = self.shared_data.received_angle_yaw

        has_data = (switch != 0 or 
                   abs(roll) > 0.001 or 
                   abs(pitch) > 0.001 or 
                   abs(yaw) > 0.001)    

        if has_data:
            line = f"接收:开关={switch} 角度=({roll:.1f},{pitch:.1f},{yaw:.1f})"
            stdscr.addstr(row, 0, line)
        else:
            stdscr.addstr(row, 0, "接收:无数据")
    
    def _draw_tuning_line(self,stdscr,row):
        """第四行：调参模式显示和导航信息"""
        if not self.shared_data:
            return
        
        # 只在TUNING模式下显示
        if self.shared_data.main_state == MainState.TUNING:
            sub_state = self.shared_data.sub_state
            nav_row = self.shared_data.nav_row
            nav_col = self.shared_data.nav_col
            
            if sub_state == SubState.SERVO:  # SERVO
                # 显示舵机调参信息
                if nav_row < len(self.shared_data.servo_angles):
                    servo_idx = nav_row
                    servo_value = self.shared_data.servo_angles[servo_idx]
                    input_buffer = self.player_input.input_buffer if hasattr(self.player_input, 'input_buffer') else ""
                    
                    line = f"舵机[{servo_idx}]:{servo_value:.1f}"
                    if input_buffer:
                        line += f" [输入:{input_buffer}]"
                    
                    _, width = stdscr.getmaxyx()
                    if len(line) > width - 1:
                        line = line[:width-1]
                    
                    stdscr.addstr(row,0,line)
                    
                    if input_buffer != self.last_input_buffer:
                        self.add_message(f"舵机{servo_idx}输入:{input_buffer}")
                        self.last_input_buffer = input_buffer
                        
            elif sub_state == SubState.PID:  # PID
                # 显示PID调参信息
                pid_idx = nav_row
                param_idx = nav_col
                
                if (pid_idx < len(self.shared_data.pid_name) and 
                    param_idx < len(self.shared_data.param_names)):
                    
                    pid_name = self.shared_data.pid_name[pid_idx]
                    param_name = self.shared_data.param_names[param_idx]
                    param_value = self.shared_data.pid_param[pid_idx][param_idx]
                    
                    input_buffer = self.player_input.input_buffer if hasattr(self.player_input, 'input_buffer') else ""
                    
                    line = f"PID:{pid_name}.{param_name}={param_value:.3f}"
                    if input_buffer:
                        line += f" [输入:{input_buffer}]"
                    
                    _, width = stdscr.getmaxyx()
                    if len(line) > width - 1:
                        line = line[:width-1]
                    
                    stdscr.addstr(row,0,line)
                    
                    if input_buffer != self.last_input_buffer:
                        self.add_message(f"PID{pid_name}.{param_name}输入:{input_buffer}")
                        self.last_input_buffer = input_buffer
                        
            elif sub_state == SubState.JACOBIAN:  # JACOBIAN
                # 显示Jacobian调参信息
                row_idx = nav_row
                col_idx = nav_col
                
                if (row_idx < 3 and col_idx < 4):
                    jacobian_value = self.shared_data.jacobian_matrix[row_idx][col_idx]
                    input_buffer = self.player_input.input_buffer if hasattr(self.player_input, 'input_buffer') else ""
                    
                    line = f"J[{row_idx},{col_idx}]:{jacobian_value:.3f}"
                    if input_buffer:
                        line += f" [输入:{input_buffer}]"
                    
                    _, width = stdscr.getmaxyx()
                    if len(line) > width - 1:
                        line = line[:width-1]
                    
                    stdscr.addstr(row,0,line)
                    
                    if input_buffer != self.last_input_buffer:
                        self.add_message(f"J[{row_idx},{col_idx}]输入:{input_buffer}")
                        self.last_input_buffer = input_buffer
            else:
                # 显示导航信息
                line = f"导航:行={nav_row},列={nav_col}"
                stdscr.addstr(row,0,line)
        else:
            # 非TUNING模式显示导航提示
            nav_row = self.shared_data.nav_row
            nav_col = self.shared_data.nav_col
            line = f"导航:行={nav_row},列={nav_col} (上下左右导航,Enter确认)"
            stdscr.addstr(row,0,line)

    def _draw_message_line(self, stdscr, row):
        """第五行"""
        if not self.message_queue:
            stdscr.addstr(row, 0, "")
            return
        
        messages = self.message_queue[-2:]
        line = " ".join(messages)

        max_len = stdscr.getmaxyx()[1] - 1
        if len(line) > max_len:
            line = line[:max_len]

        stdscr.addstr(row, 0, line)
    def get_display_info(self):
        """获取显示信息（兼容原有接口）"""
        if not self.uart_sender or not self.initializer or not self.player_input:
            return {
                "last_sent": "---",
                "com_port": "---",
                "current_state": "---",
                "received_data": "---"
            }
            
        # 获取发送信息
        try:
            last_sent = self.uart_sender.get_last_sent_info()
        except:
            last_sent = "---"
            
        # 获取配置信息
        try:
            config = self.initializer.get_current_config()
            com_port = config["com_port"] if config["com_port"] else "未连接"
        except:
            com_port = "---"
            
        # 获取输入状态
        try:
            input_state = self.player_input.get_current_input()
            current_state = f"开关={input_state['main_switch']} 风扇={input_state['fan_speed']} 舵机={input_state['servo_angles']}"
        except:
            current_state = "---"
            
        # 获取接收数据
        if self.shared_data:
            switch = self.shared_data.received_switch
            roll = self.shared_data.received_angle_roll
            pitch = self.shared_data.received_angle_pitch
            yaw = self.shared_data.received_angle_yaw
            received_info = f"开关={switch} 角度=({roll:.2f},{pitch:.2f},{yaw:.2f})"
        else:
            received_info = "未连接"
            
        return {
            "last_sent": last_sent,
            "com_port": com_port,
            "current_state": current_state,
            "received_data": received_info
        }
