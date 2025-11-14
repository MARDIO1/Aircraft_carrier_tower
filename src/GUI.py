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
        control_frame = ttk.LabelFrame(main_frame, text="控制数据", padding="5")
        control_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # 油门控制
        ttk.Label(control_frame, text="油门:").grid(row=0, column=0, sticky=tk.W)
        self.throttle_var = tk.DoubleVar(value=0.0)
        self.throttle_scale = ttk.Scale(control_frame, from_=0.0, to=1.0, variable=self.throttle_var, orient=tk.HORIZONTAL)
        self.throttle_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        self.throttle_label = ttk.Label(control_frame, text="0.0")
        self.throttle_label.grid(row=0, column=2, padx=5)
        
        # 舵面控制
        surface_names = ["滚转", "俯仰", "偏航", "襟翼"]
        self.surface_vars = []
        self.surface_scales = []
        self.surface_labels = []
        
        for i, name in enumerate(surface_names):
            ttk.Label(control_frame, text=f"{name}:").grid(row=i+1, column=0, sticky=tk.W)
            var = tk.DoubleVar(value=0.0)
            scale = ttk.Scale(control_frame, from_=-1.0, to=1.0, variable=var, orient=tk.HORIZONTAL)
            scale.grid(row=i+1, column=1, sticky=(tk.W, tk.E), padx=5)
            label = ttk.Label(control_frame, text="0.0")
            label.grid(row=i+1, column=2, padx=5)
            
            self.surface_vars.append(var)
            self.surface_scales.append(scale)
            self.surface_labels.append(label)
        
        # 接收数据显示区域
        receive_frame = ttk.LabelFrame(main_frame, text="接收数据", padding="5")
        receive_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        self.receive_text = tk.Text(receive_frame, height=8, width=60)
        self.receive_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        scrollbar = ttk.Scrollbar(receive_frame, orient=tk.VERTICAL, command=self.receive_text.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.receive_text.configure(yscrollcommand=scrollbar.set)
        
        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, pady=10)
        
        ttk.Button(button_frame, text="发送数据", command=self.send_control_data).grid(row=0, column=0, padx=5)
        ttk.Button(button_frame, text="清空接收", command=self.clear_receive).grid(row=0, column=1, padx=5)
        ttk.Button(button_frame, text="重置控制", command=self.reset_controls).grid(row=0, column=2, padx=5)
        
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
        
        throttle = self.throttle_var.get()
        surfaces = [var.get() for var in self.surface_vars]
        
        try:
            data = self.protocol.encode_ground_data(throttle, surfaces)
            if self.serial_initializer.send_data(data):
                self.append_receive_text(f"发送: 油门={throttle:.2f}, 舵面={surfaces}")
            else:
                messagebox.showerror("错误", "发送数据失败")
        except Exception as e:
            messagebox.showerror("错误", f"编码数据失败: {e}")
    
    def reset_controls(self):
        """重置控制数据"""
        self.throttle_var.set(0.0)
        for var in self.surface_vars:
            var.set(0.0)
        self.update_display()
    
    def clear_receive(self):
        """清空接收显示"""
        self.receive_text.delete(1.0, tk.END)
    
    def append_receive_text(self, text):
        """添加接收文本"""
        self.receive_text.insert(tk.END, f"{text}\n")
        self.receive_text.see(tk.END)
    
    def update_display(self):
        """更新显示"""
        self.throttle_label.config(text=f"{self.throttle_var.get():.2f}")
        for i, var in enumerate(self.surface_vars):
            self.surface_labels[i].config(text=f"{var.get():.2f}")
    
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
            # 尝试解码航模数据
            custom_data = self.protocol.decode_aircraft_data(data)
            if custom_data is not None:
                self.append_receive_text(f"接收: 自定义数据={custom_data}")
    
    def run(self):
        """运行GUI"""
        self.root.mainloop()
