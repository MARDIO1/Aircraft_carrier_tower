import tkinter as tk
from tkinter import ttk, messagebox

class GroundStationGUI:
    def __init__(self, protocol, serial_initializer, player_input):
        self.protocol = protocol
        self.serial_initializer = serial_initializer
        self.player_input = player_input
        
        self.root = tk.Tk()
        self.root.title("航模地面站")
        self.root.geometry("600x400")
        
        self.is_connected = False
        self.update_interval = 100  # 毫秒
        
        self.setup_gui()
    
    def setup_gui(self):
        """设置GUI界面"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 串口连接区域
        connection_frame = ttk.LabelFrame(main_frame, text="串口连接", padding="5")
        connection_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(connection_frame, text="COM端口:").grid(row=0, column=0, sticky=tk.W)
        self.port_var = tk.StringVar(value="COM3")
        self.port_entry = ttk.Entry(connection_frame, textvariable=self.port_var, width=10)
        self.port_entry.grid(row=0, column=1, padx=5)
        
        ttk.Button(connection_frame, text="连接", command=self.connect_serial).grid(row=0, column=2, padx=5)
        ttk.Button(connection_frame, text="断开", command=self.disconnect_serial).grid(row=0, column=3, padx=5)
        ttk.Button(connection_frame, text="扫描端口", command=self.scan_ports).grid(row=0, column=4, padx=5)
        
        # 控制数据区域
        control_frame = ttk.LabelFrame(main_frame, text="系统控制", padding="5")
        control_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # 系统状态控制
        ttk.Label(control_frame, text="系统状态:").grid(row=0, column=0, sticky=tk.W)
        self.throttle_var = tk.DoubleVar(value=0.0)
        self.throttle_scale = ttk.Scale(control_frame, from_=0.0, to=1.0, variable=self.throttle_var, orient=tk.HORIZONTAL, command=self.on_throttle_change)
        self.throttle_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        self.throttle_label = ttk.Label(control_frame, text="关闭")
        self.throttle_label.grid(row=0, column=2, padx=5)
        
        # 状态指示器
        status_frame = ttk.Frame(control_frame)
        status_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(status_frame, text="当前状态:").grid(row=0, column=0, sticky=tk.W)
        self.status_indicator = ttk.Label(status_frame, text="未连接", foreground="red")
        self.status_indicator.grid(row=0, column=1, padx=5)
        
        # ========== 新增：风扇控制区域 ==========
        fan_frame = ttk.LabelFrame(main_frame, text="风扇控制", padding="5")
        fan_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(fan_frame, text="风扇转速:").grid(row=0, column=0, sticky=tk.W)
        self.fan_speed_var = tk.IntVar(value=0)
        self.fan_scale = ttk.Scale(fan_frame, from_=0, to=1000, variable=self.fan_speed_var, orient=tk.HORIZONTAL, command=self.on_fan_change)
        self.fan_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        self.fan_label = ttk.Label(fan_frame, text="0 RPM")
        self.fan_label.grid(row=0, column=2, padx=5)
        
        # ========== 新增：舵机控制区域 ==========
        servo_frame = ttk.LabelFrame(main_frame, text="舵机控制", padding="5")
        servo_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # 舵机1
        ttk.Label(servo_frame, text="舵机1:").grid(row=0, column=0, sticky=tk.W)
        self.servo1_var = tk.IntVar(value=90)
        self.servo1_scale = ttk.Scale(servo_frame, from_=0, to=180, variable=self.servo1_var, orient=tk.HORIZONTAL, command=self.on_servo1_change)
        self.servo1_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        self.servo1_label = ttk.Label(servo_frame, text="90°")
        self.servo1_label.grid(row=0, column=2, padx=5)
        
        # 舵机2
        ttk.Label(servo_frame, text="舵机2:").grid(row=1, column=0, sticky=tk.W)
        self.servo2_var = tk.IntVar(value=90)
        self.servo2_scale = ttk.Scale(servo_frame, from_=0, to=180, variable=self.servo2_var, orient=tk.HORIZONTAL, command=self.on_servo2_change)
        self.servo2_scale.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5)
        self.servo2_label = ttk.Label(servo_frame, text="90°")
        self.servo2_label.grid(row=1, column=2, padx=5)
        
        # 舵机3
        ttk.Label(servo_frame, text="舵机3:").grid(row=2, column=0, sticky=tk.W)
        self.servo3_var = tk.IntVar(value=90)
        self.servo3_scale = ttk.Scale(servo_frame, from_=0, to=180, variable=self.servo3_var, orient=tk.HORIZONTAL, command=self.on_servo3_change)
        self.servo3_scale.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=5)
        self.servo3_label = ttk.Label(servo_frame, text="90°")
        self.servo3_label.grid(row=2, column=2, padx=5)
        
        # 舵机4
        ttk.Label(servo_frame, text="舵机4:").grid(row=3, column=0, sticky=tk.W)
        self.servo4_var = tk.IntVar(value=90)
        self.servo4_scale = ttk.Scale(servo_frame, from_=0, to=180, variable=self.servo4_var, orient=tk.HORIZONTAL, command=self.on_servo4_change)
        self.servo4_scale.grid(row=3, column=1, sticky=(tk.W, tk.E), padx=5)
        self.servo4_label = ttk.Label(servo_frame, text="90°")
        self.servo4_label.grid(row=3, column=2, padx=5)
        
        # 接收数据显示区域 - 调整行号
        receive_frame = ttk.LabelFrame(main_frame, text="接收数据", padding="5")
        receive_frame.grid(row=4, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        self.receive_text = tk.Text(receive_frame, height=8, width=60)
        self.receive_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        scrollbar = ttk.Scrollbar(receive_frame, orient=tk.VERTICAL, command=self.receive_text.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.receive_text.configure(yscrollcommand=scrollbar.set)
        
        # 按钮区域 - 调整行号并添加新按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, pady=10)
        
        ttk.Button(button_frame, text="发送完整数据", command=self.send_full_data).grid(row=0, column=0, padx=5)
        ttk.Button(button_frame, text="发送数据", command=self.send_control_data).grid(row=0, column=1, padx=5)
        ttk.Button(button_frame, text="开启系统", command=lambda: self.send_simple_command(True)).grid(row=0, column=2, padx=5)
        ttk.Button(button_frame, text="关闭系统", command=lambda: self.send_simple_command(False)).grid(row=0, column=3, padx=5)
        ttk.Button(button_frame, text="清空接收", command=self.clear_receive).grid(row=0, column=4, padx=5)
        ttk.Button(button_frame, text="重置控制", command=self.reset_controls).grid(row=0, column=5, padx=5)
        
        # 配置网格权重
        main_frame.columnconfigure(0, weight=1)
        control_frame.columnconfigure(1, weight=1)
        receive_frame.columnconfigure(0, weight=1)
        receive_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)
    
    def connect_serial(self):
        """连接串口"""
        port = self.port_var.get()
        if not port:
            messagebox.showerror("错误", "请输入COM端口")
            return
        
        if self.serial_initializer.initialize_serial(port):
            self.is_connected = True
            messagebox.showinfo("成功", f"已连接到 {port}")
            self.start_update_loop()
        else:
            messagebox.showerror("错误", f"无法连接到 {port}")
    
    def disconnect_serial(self):
        """断开串口"""
        self.serial_initializer.close_serial()
        self.is_connected = False
        messagebox.showinfo("信息", "已断开串口连接")
    
    def scan_ports(self):
        """扫描可用端口"""
        ports = self.serial_initializer.list_available_ports()
        if ports:
            port_list = "\n".join([f"{p['device']} - {p['description']}" for p in ports])
            messagebox.showinfo("可用端口", port_list)
        else:
            messagebox.showinfo("可用端口", "未找到可用串口")
    
    def send_control_data(self):
        """发送控制数据"""
        if not self.is_connected:
            messagebox.showerror("错误", "串口未连接")
            return
        
        # 使用现有的协议功能 - 发送开启/关闭命令
        try:
            # 根据油门值决定发送开启还是关闭命令
            is_on = self.throttle_var.get() > 0.1  # 油门大于0.1认为是开启
            data = self.protocol.encode_ground_command(is_on)
            if self.serial_initializer.send_data(data):
                status = "开启" if is_on else "关闭"
                self.append_receive_text(f"发送: 系统{status}命令")
            else:
                messagebox.showerror("错误", "发送数据失败")
        except Exception as e:
            messagebox.showerror("错误", f"编码数据失败: {e}")
    
    def send_full_data(self):
        """发送完整数据（开关、风扇转速、舵机角度）"""
        if not self.is_connected:
            messagebox.showerror("错误", "串口未连接")
            return
        
        try:
            # 获取当前控制值
            switch_cmd = 1 if self.throttle_var.get() > 0.1 else 0
            fan_rpm = self.fan_speed_var.get()
            servo_angles = [
                self.servo1_var.get(),
                self.servo2_var.get(),
                self.servo3_var.get(),
                self.servo4_var.get()
            ]
            
            # 使用新的协议函数发送完整数据
            data = self.protocol.encode_up_frame(switch_cmd, fan_rpm, servo_angles)
            if data and self.serial_initializer.send_data(data):
                self.append_receive_text(f"发送完整数据: 开关={switch_cmd}, 风扇={fan_rpm}RPM, 舵机={servo_angles}")
            else:
                messagebox.showerror("错误", "发送完整数据失败")
        except Exception as e:
            messagebox.showerror("错误", f"编码完整数据失败: {e}")
    
    def send_simple_command(self, is_on):
        """发送简单命令（开启/关闭）"""
        if not self.is_connected:
            messagebox.showerror("错误", "串口未连接")
            return
        
        try:
            data = self.protocol.encode_ground_command(is_on)
            if self.serial_initializer.send_data(data):
                status = "开启" if is_on else "关闭"
                self.append_receive_text(f"发送: 系统{status}命令")
            else:
                messagebox.showerror("错误", "发送命令失败")
        except Exception as e:
            messagebox.showerror("错误", f"编码命令失败: {e}")
    
    def reset_controls(self):
        """重置控制数据"""
        self.throttle_var.set(0.0)
        self.fan_speed_var.set(0)
        self.servo1_var.set(90)
        self.servo2_var.set(90)
        self.servo3_var.set(90)
        self.servo4_var.set(90)
        self.update_display()
    
    def clear_receive(self):
        """清空接收显示"""
        self.receive_text.delete(1.0, tk.END)
    
    def append_receive_text(self, text):
        """添加接收文本"""
        self.receive_text.insert(tk.END, f"{text}\n")
        self.receive_text.see(tk.END)
    
    def on_throttle_change(self, value):
        """油门滑块变化回调"""
        throttle_value = float(value)
        status_text = "开启" if throttle_value > 0.1 else "关闭"
        self.throttle_label.config(text=status_text)
        
        # 更新player_input中的油门值
        self.player_input.throttle = throttle_value
    
    def on_fan_change(self, value):
        """风扇转速滑块变化回调"""
        fan_rpm = int(float(value))
        self.fan_label.config(text=f"{fan_rpm} RPM")
        
        # 更新player_input中的风扇转速
        self.player_input.fan_rpm = fan_rpm
    
    def on_servo1_change(self, value):
        """舵机1滑块变化回调"""
        servo_angle = int(float(value))
        self.servo1_label.config(text=f"{servo_angle}°")
        
        # 更新player_input中的舵机角度
        self.player_input.servo_angles[0] = servo_angle
    
    def on_servo2_change(self, value):
        """舵机2滑块变化回调"""
        servo_angle = int(float(value))
        self.servo2_label.config(text=f"{servo_angle}°")
        
        # 更新player_input中的舵机角度
        self.player_input.servo_angles[1] = servo_angle
    
    def on_servo3_change(self, value):
        """舵机3滑块变化回调"""
        servo_angle = int(float(value))
        self.servo3_label.config(text=f"{servo_angle}°")
        
        # 更新player_input中的舵机角度
        self.player_input.servo_angles[2] = servo_angle
    
    def on_servo4_change(self, value):
        """舵机4滑块变化回调"""
        servo_angle = int(float(value))
        self.servo4_label.config(text=f"{servo_angle}°")
        
        # 更新player_input中的舵机角度
        self.player_input.servo_angles[3] = servo_angle
    
    def update_display(self):
        """更新显示"""
        # 更新系统状态显示
        throttle_value = self.throttle_var.get()
        status_text = "开启" if throttle_value > 0.1 else "关闭"
        self.throttle_label.config(text=status_text)
        
        # 更新风扇转速显示
        fan_rpm = self.fan_speed_var.get()
        self.fan_label.config(text=f"{fan_rpm} RPM")
        
        # 更新舵机角度显示
        self.servo1_label.config(text=f"{self.servo1_var.get()}°")
        self.servo2_label.config(text=f"{self.servo2_var.get()}°")
        self.servo3_label.config(text=f"{self.servo3_var.get()}°")
        self.servo4_label.config(text=f"{self.servo4_var.get()}°")
        
        # 更新连接状态指示器
        if self.is_connected:
            self.status_indicator.config(text="已连接", foreground="green")
        else:
            self.status_indicator.config(text="未连接", foreground="red")
    
    def start_update_loop(self):
        """开始更新循环"""
        if self.is_connected:
            self.update_display()
            self.check_receive_data()
            self.root.after(self.update_interval, self.start_update_loop)
    
    def check_receive_data(self):
        """检查接收数据"""
        if not self.is_connected:
            return
        
        data = self.serial_initializer.receive_data()
        if data:
            # 使用新的协议处理函数解析完整下行数据
            packets = self.protocol.process_receive_data(data)
            for packet in packets:
                self.display_down_data(packet)
            
            # 兼容性：也尝试解码简单状态
            status = self.protocol.decode_aircraft_status(data)
            if status is not None and not packets:  # 如果没有解析到完整数据包，显示简单状态
                status_text = "已开启" if status else "已关闭"
                self.append_receive_text(f"接收: 航模状态={status_text}")
    
    def display_down_data(self, packet_data):
        """显示下行数据包信息"""
        try:
            last_switch = packet_data['last_switch']
            gyro_data = packet_data['gyro_data']
            
            # 格式化显示
            switch_text = "开启" if last_switch == 1 else "关闭"
            gyro_text = f"陀螺仪: gx={gyro_data['gx']:.2f}, gy={gyro_data['gy']:.2f}, gz={gyro_data['gz']:.2f}"
            accel_text = f"加速度: ax={gyro_data['ax']:.2f}, ay={gyro_data['ay']:.2f}, az={gyro_data['az']:.2f}"
            mag_text = f"磁力计: mx={gyro_data['mx']:.2f}, my={gyro_data['my']:.2f}, mz={gyro_data['mz']:.2f}"
            
            self.append_receive_text(f"接收完整数据:")
            self.append_receive_text(f"  上次开关状态: {switch_text}")
            self.append_receive_text(f"  {gyro_text}")
            self.append_receive_text(f"  {accel_text}")
            self.append_receive_text(f"  {mag_text}")
            self.append_receive_text("")
            
        except Exception as e:
            self.append_receive_text(f"解析下行数据包错误: {e}")
    
    def run(self):
        """运行GUI"""
        self.root.mainloop()
