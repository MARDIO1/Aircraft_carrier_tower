import tkinter as tk
from tkinter import ttk, messagebox
import math

class EnhancedGroundStationGUI:
    def __init__(self, protocol, serial_initializer, player_input):
        self.protocol = protocol
        self.serial_initializer = serial_initializer
        self.player_input = player_input
        
        self.root = tk.Tk()
        self.root.title("航模地面站 - 增强版")
        self.root.geometry("800x600")
        
        self.is_connected = False
        self.update_interval = 100  # 毫秒
        
        # 传感器数据历史记录
        self.sensor_history = {
            'gx': [], 'gy': [], 'gz': [],
            'ax': [], 'ay': [], 'az': [],
            'mx': [], 'my': [], 'mz': []
        }
        self.max_history = 50  # 最大历史数据点数
        
        self.setup_gui()
    
    def setup_gui(self):
        """设置增强版GUI界面"""
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # ========== 连接控制区域 ==========
        connection_frame = ttk.LabelFrame(main_frame, text="串口连接", padding="5")
        connection_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(connection_frame, text="COM端口:").grid(row=0, column=0, sticky=tk.W)
        self.port_var = tk.StringVar(value="COM3")
        self.port_entry = ttk.Entry(connection_frame, textvariable=self.port_var, width=10)
        self.port_entry.grid(row=0, column=1, padx=5)
        
        ttk.Button(connection_frame, text="连接", command=self.connect_serial).grid(row=0, column=2, padx=5)
        ttk.Button(connection_frame, text="断开", command=self.disconnect_serial).grid(row=0, column=3, padx=5)
        ttk.Button(connection_frame, text="扫描端口", command=self.scan_ports).grid(row=0, column=4, padx=5)
        
        # 连接状态指示器（带动画效果）
        self.connection_indicator = tk.Canvas(connection_frame, width=20, height=20)
        self.connection_indicator.grid(row=0, column=5, padx=10)
        self.draw_connection_indicator("disconnected")
        
        # ========== 系统状态控制区域 ==========
        control_frame = ttk.LabelFrame(main_frame, text="系统控制", padding="5")
        control_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # 系统开关控制
        ttk.Label(control_frame, text="系统状态:").grid(row=0, column=0, sticky=tk.W)
        self.throttle_var = tk.DoubleVar(value=0.0)
        self.throttle_scale = ttk.Scale(control_frame, from_=0.0, to=1.0, variable=self.throttle_var, 
                                       orient=tk.HORIZONTAL, command=self.on_throttle_change)
        self.throttle_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        self.throttle_label = ttk.Label(control_frame, text="关闭", font=("Arial", 10, "bold"))
        self.throttle_label.grid(row=0, column=2, padx=5)
        
        # 状态指示器
        self.status_indicator = tk.Canvas(control_frame, width=100, height=20)
        self.status_indicator.grid(row=0, column=3, padx=10)
        self.draw_status_indicator("disconnected")
        
        # ========== 风扇控制区域 ==========
        fan_frame = ttk.LabelFrame(main_frame, text="风扇控制", padding="5")
        fan_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(fan_frame, text="风扇转速:").grid(row=0, column=0, sticky=tk.W)
        self.fan_speed_var = tk.IntVar(value=0)
        self.fan_scale = ttk.Scale(fan_frame, from_=0, to=1000, variable=self.fan_speed_var, 
                                  orient=tk.HORIZONTAL, command=self.on_fan_change)
        self.fan_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        self.fan_label = ttk.Label(fan_frame, text="0 RPM", font=("Arial", 10, "bold"))
        self.fan_label.grid(row=0, column=2, padx=5)
        
        # 风扇状态指示器
        self.fan_indicator = tk.Canvas(fan_frame, width=80, height=20)
        self.fan_indicator.grid(row=0, column=3, padx=10)
        self.draw_fan_indicator(0)
        
        # ========== 舵机控制区域 ==========
        servo_frame = ttk.LabelFrame(main_frame, text="舵机控制", padding="5")
        servo_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # 创建舵机控制网格
        servo_labels = ["舵机1", "舵机2", "舵机3", "舵机4"]
        self.servo_vars = []
        self.servo_labels = []
        self.servo_indicators = []
        
        for i, label in enumerate(servo_labels):
            ttk.Label(servo_frame, text=f"{label}:").grid(row=i, column=0, sticky=tk.W)
            
            var = tk.IntVar(value=90)
            self.servo_vars.append(var)
            
            scale = ttk.Scale(servo_frame, from_=0, to=180, variable=var, 
                             orient=tk.HORIZONTAL, command=lambda v, idx=i: self.on_servo_change(v, idx))
            scale.grid(row=i, column=1, sticky=(tk.W, tk.E), padx=5)
            
            servo_label = ttk.Label(servo_frame, text="90°", font=("Arial", 9))
            servo_label.grid(row=i, column=2, padx=5)
            self.servo_labels.append(servo_label)
            
            # 舵机角度指示器
            indicator = tk.Canvas(servo_frame, width=60, height=15)
            indicator.grid(row=i, column=3, padx=5)
            self.servo_indicators.append(indicator)
            self.draw_servo_indicator(i, 90)
        
        # ========== 传感器数据显示区域 ==========
        sensor_frame = ttk.LabelFrame(main_frame, text="传感器数据可视化", padding="5")
        sensor_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # 创建传感器数据显示网格
        sensor_data_frame = ttk.Frame(sensor_frame)
        sensor_data_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # 陀螺仪数据
        gyro_frame = ttk.LabelFrame(sensor_data_frame, text="陀螺仪 (°/s)", padding="3")
        gyro_frame.grid(row=0, column=0, padx=5, sticky=(tk.W, tk.E))
        
        self.gx_label = ttk.Label(gyro_frame, text="gx: 0.00", font=("Arial", 9))
        self.gx_label.grid(row=0, column=0, sticky=tk.W)
        self.gy_label = ttk.Label(gyro_frame, text="gy: 0.00", font=("Arial", 9))
        self.gy_label.grid(row=1, column=0, sticky=tk.W)
        self.gz_label = ttk.Label(gyro_frame, text="gz: 0.00", font=("Arial", 9))
        self.gz_label.grid(row=2, column=0, sticky=tk.W)
        
        # 加速度计数据
        accel_frame = ttk.LabelFrame(sensor_data_frame, text="加速度计 (g)", padding="3")
        accel_frame.grid(row=0, column=1, padx=5, sticky=(tk.W, tk.E))
        
        self.ax_label = ttk.Label(accel_frame, text="ax: 0.00", font=("Arial", 9))
        self.ax_label.grid(row=0, column=0, sticky=tk.W)
        self.ay_label = ttk.Label(accel_frame, text="ay: 0.00", font=("Arial", 9))
        self.ay_label.grid(row=1, column=0, sticky=tk.W)
        self.az_label = ttk.Label(accel_frame, text="az: 0.00", font=("Arial", 9))
        self.az_label.grid(row=2, column=0, sticky=tk.W)
        
        # 磁力计数据
        mag_frame = ttk.LabelFrame(sensor_data_frame, text="磁力计 (μT)", padding="3")
        mag_frame.grid(row=0, column=2, padx=5, sticky=(tk.W, tk.E))
        
        self.mx_label = ttk.Label(mag_frame, text="mx: 0.00", font=("Arial", 9))
        self.mx_label.grid(row=0, column=0, sticky=tk.W)
        self.my_label = ttk.Label(mag_frame, text="my: 0.00", font=("Arial", 9))
        self.my_label.grid(row=1, column=0, sticky=tk.W)
        self.mz_label = ttk.Label(mag_frame, text="mz: 0.00", font=("Arial", 9))
        self.mz_label.grid(row=2, column=0, sticky=tk.W)
        
        # ========== 控制按钮区域 ==========
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, pady=10)
        
        # 主要控制按钮
        ttk.Button(button_frame, text="发送完整数据", command=self.send_full_data, 
                  style="Accent.TButton").grid(row=0, column=0, padx=5)
        ttk.Button(button_frame, text="发送控制数据", command=self.send_control_data).grid(row=0, column=1, padx=5)
        ttk.Button(button_frame, text="开启系统", command=lambda: self.send_simple_command(True)).grid(row=0, column=2, padx=5)
        ttk.Button(button_frame, text="关闭系统", command=lambda: self.send_simple_command(False)).grid(row=0, column=3, padx=5)
        
        # 工具按钮
        ttk.Button(button_frame, text="重置控制", command=self.reset_controls).grid(row=0, column=4, padx=5)
        ttk.Button(button_frame, text="清空历史", command=self.clear_sensor_history).grid(row=0, column=5, padx=5)
        
        # ========== 接收数据显示区域 ==========
        receive_frame = ttk.LabelFrame(main_frame, text="数据日志", padding="5")
        receive_frame.grid(row=6, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        self.receive_text = tk.Text(receive_frame, height=6, width=80, font=("Consolas", 9))
        self.receive_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        scrollbar = ttk.Scrollbar(receive_frame, orient=tk.VERTICAL, command=self.receive_text.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.receive_text.configure(yscrollcommand=scrollbar.set)
        
        # 配置网格权重
        main_frame.columnconfigure(0, weight=1)
        control_frame.columnconfigure(1, weight=1)
        fan_frame.columnconfigure(1, weight=1)
        servo_frame.columnconfigure(1, weight=1)
        sensor_data_frame.columnconfigure(0, weight=1)
        sensor_data_frame.columnconfigure(1, weight=1)
        sensor_data_frame.columnconfigure(2, weight=1)
        receive_frame.columnconfigure(0, weight=1)
        receive_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(6, weight=1)
    
    def draw_connection_indicator(self, status):
        """绘制连接状态指示器"""
        self.connection_indicator.delete("all")
        if status == "connected":
            self.connection_indicator.create_oval(2, 2, 18, 18, fill="green", outline="")
            self.connection_indicator.create_text(10, 10, text="●", fill="white", font=("Arial", 8))
        else:
            self.connection_indicator.create_oval(2, 2, 18, 18, fill="red", outline="")
            self.connection_indicator.create_text(10, 10, text="●", fill="white", font=("Arial", 8))
    
    def draw_status_indicator(self, status):
        """绘制系统状态指示器"""
        self.status_indicator.delete("all")
        if status == "connected":
            self.status_indicator.create_rectangle(0, 0, 100, 20, fill="#4CAF50", outline="")
            self.status_indicator.create_text(50, 10, text="已连接", fill="white", font=("Arial", 9, "bold"))
        elif status == "active":
            self.status_indicator.create_rectangle(0, 0, 100, 20, fill="#2196F3", outline="")
            self.status_indicator.create_text(50, 10, text="运行中", fill="white", font=("Arial", 9, "bold"))
        else:
            self.status_indicator.create_rectangle(0, 0, 100, 20, fill="#f44336", outline="")
            self.status_indicator.create_text(50, 10, text="未连接", fill="white", font=("Arial", 9, "bold"))
    
    def draw_fan_indicator(self, rpm):
        """绘制风扇状态指示器"""
        self.fan_indicator.delete("all")
        # 根据转速计算颜色
        if rpm == 0:
            color = "#cccccc"
        elif rpm < 300:
            color = "#4CAF50"  # 绿色
        elif rpm < 700:
            color = "#FFC107"  # 黄色
        else:
            color = "#f44336"  # 红色
        
        self.fan_indicator.create_rectangle(0, 0, 80, 20, fill=color, outline="")
        self.fan_indicator.create_text(40, 10, text=f"{rpm}RPM", fill="white", font=("Arial", 8, "bold"))
    
    def draw_servo_indicator(self, index, angle):
        """绘制舵机角度指示器"""
        canvas = self.servo_indicators[index]
        canvas.delete("all")
        
        # 根据角度计算颜色（90°为中性位置）
        if angle == 90:
            color = "#4CAF50"  # 绿色
        elif 80 <= angle <= 100:
            color = "#2196F3"  # 蓝色
        elif 60 <= angle < 80 or 100 < angle <= 120:
            color = "#FFC107"  # 黄色
        else:
            color = "#f44336"  # 红色
        
        # 绘制角度条
        bar_width = 60
        bar_height = 15
        fill_width = int((angle / 180.0) * bar_width)
        
        canvas.create_rectangle(0, 0, bar_width, bar_height, fill="#e0e0e0", outline="")
        canvas.create_rectangle(0, 0, fill_width, bar_height, fill=color, outline="")
        canvas.create_text(bar_width//2, bar_height//2, text=f"{angle}°", 
                          fill="black", font=("Arial", 7, "bold"))
    
    def connect_serial(self):
        """连接串口"""
        port = self.port_var.get()
        if not port:
            messagebox.showerror("错误", "请输入COM端口")
            return
        
        if self.serial_initializer.initialize_serial(port):
            self.is_connected = True
            self.draw_connection_indicator("connected")
            self.draw_status_indicator("connected")
            messagebox.showinfo("成功", f"已连接到 {port}")
            self.start_update_loop()
        else:
            messagebox.showerror("错误", f"无法连接到 {port}")
    
    def disconnect_serial(self):
        """断开串口"""
        self.serial_initializer.close_serial()
        self.is_connected = False
        self.draw_connection_indicator("disconnected")
        self.draw_status_indicator("disconnected")
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
        
        try:
            # 根据油门值决定发送开启还是关闭命令
            is_on = self.throttle_var.get() > 0.1  # 油门大于0.1认为是开启
            data = self.protocol.encode_ground_command(is_on)
            if self.serial_initializer.send_data(data):
                status = "开启" if is_on else "关闭"
                self.append_receive_text(f"发送: 系统{status}命令")
                # 更新状态指示器
                if is_on:
                    self.draw_status_indicator("active")
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
            servo_angles = [var.get() for var in self.servo_vars]
            
            # 使用新的协议函数发送完整数据
            data = self.protocol.encode_up_frame(switch_cmd, fan_rpm, servo_angles)
            if data and self.serial_initializer.send_data(data):
                self.append_receive_text(f"发送完整数据: 开关={switch_cmd}, 风扇={fan_rpm}RPM, 舵机={servo_angles}")
                # 更新状态指示器
                if switch_cmd == 1:
                    self.draw_status_indicator("active")
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
                # 更新状态指示器
                if is_on:
                    self.draw_status_indicator("active")
            else:
                messagebox.showerror("错误", "发送命令失败")
        except Exception as e:
            messagebox.showerror("错误", f"编码命令失败: {e}")
    
    def reset_controls(self):
        """重置控制数据"""
        self.throttle_var.set(0.0)
        self.fan_speed_var.set(0)
        for var in self.servo_vars:
            var.set(90)
        self.update_display()
    
    def clear_sensor_history(self):
        """清空传感器历史数据"""
        for key in self.sensor_history:
            self.sensor_history[key] = []
        self.append_receive_text("传感器历史数据已清空")
    
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
        self.draw_fan_indicator(fan_rpm)
        
        # 更新player_input中的风扇转速
        self.player_input.fan_rpm = fan_rpm
    
    def on_servo_change(self, value, index):
        """舵机滑块变化回调"""
        servo_angle = int(float(value))
        self.servo_labels[index].config(text=f"{servo_angle}°")
        self.draw_servo_indicator(index, servo_angle)
        
        # 更新player_input中的舵机角度
        self.player_input.servo_angles[index] = servo_angle
    
    def update_display(self):
        """更新显示"""
        # 更新系统状态显示
        throttle_value = self.throttle_var.get()
        status_text = "开启" if throttle_value > 0.1 else "关闭"
        self.throttle_label.config(text=status_text)
        
        # 更新风扇转速显示
        fan_rpm = self.fan_speed_var.get()
        self.fan_label.config(text=f"{fan_rpm} RPM")
        self.draw_fan_indicator(fan_rpm)
        
        # 更新舵机角度显示
        for i, var in enumerate(self.servo_vars):
            angle = var.get()
            self.servo_labels[i].config(text=f"{angle}°")
            self.draw_servo_indicator(i, angle)
        
        # 更新连接状态指示器
        if self.is_connected:
            self.draw_connection_indicator("connected")
            if throttle_value > 0.1:
                self.draw_status_indicator("active")
            else:
                self.draw_status_indicator("connected")
        else:
            self.draw_connection_indicator("disconnected")
            self.draw_status_indicator("disconnected")
    
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
            
            # 更新传感器数据显示
            self.update_sensor_display(gyro_data)
            
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
    
    def update_sensor_display(self, gyro_data):
        """更新传感器数据显示"""
        # 更新陀螺仪数据
        self.gx_label.config(text=f"gx: {gyro_data['gx']:.2f}")
        self.gy_label.config(text=f"gy: {gyro_data['gy']:.2f}")
        self.gz_label.config(text=f"gz: {gyro_data['gz']:.2f}")
        
        # 更新加速度计数据
        self.ax_label.config(text=f"ax: {gyro_data['ax']:.2f}")
        self.ay_label.config(text=f"ay: {gyro_data['ay']:.2f}")
        self.az_label.config(text=f"az: {gyro_data['az']:.2f}")
        
        # 更新磁力计数据
        self.mx_label.config(text=f"mx: {gyro_data['mx']:.2f}")
        self.my_label.config(text=f"my: {gyro_data['my']:.2f}")
        self.mz_label.config(text=f"mz: {gyro_data['mz']:.2f}")
        
        # 更新历史数据
        for key in ['gx', 'gy', 'gz', 'ax', 'ay', 'az', 'mx', 'my', 'mz']:
            self.sensor_history[key].append(gyro_data[key])
            if len(self.sensor_history[key]) > self.max_history:
                self.sensor_history[key].pop(0)
    
    def run(self):
        """运行GUI"""
        self.root.mainloop()
