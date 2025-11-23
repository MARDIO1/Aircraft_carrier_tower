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
        self.update_interval = 20  # 毫秒 (50Hz)
        
        # 传感器数据历史记录
        self.sensor_history = {
            'gx': [], 'gy': [], 'gz': [],
            'ax': [], 'ay': [], 'az': [],
            'mx': [], 'my': [], 'mz': []
        }
        self.max_history = 50  # 最大历史数据点数
        
        # 自动发送控制
        self.auto_send_enabled = False
        self.last_send_time = 0
        self.send_interval = 20  # 毫秒 (50Hz)
        self.send_statistics = {
            'total_sent': 0,
            'last_second_count': 0,
            'current_frequency': 0.0
        }
        
        # 数据包大小控制
        self.data_packet_mode = tk.StringVar(value="full")  # "full" 或 "compact"
        self.send_frequency = tk.IntVar(value=50)  # Hz
        
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
        
        # 系统开关控制 - 改进为按钮形式
        ttk.Label(control_frame, text="系统状态:").grid(row=0, column=0, sticky=tk.W)
        
        # 创建开关按钮框架
        switch_frame = ttk.Frame(control_frame)
        switch_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        
        self.throttle_var = tk.DoubleVar(value=0.0)
        
        # 开关按钮
        self.switch_button = tk.Button(switch_frame, text="🔴 关闭", font=("Arial", 12, "bold"), 
                                      bg="#f44336", fg="white", width=10, height=2,
                                      command=self.toggle_system)
        self.switch_button.grid(row=0, column=0, padx=5)
        
        # 状态标签（用于兼容性）
        self.throttle_label = ttk.Label(control_frame, text="关闭", font=("Arial", 10, "bold"))
        self.throttle_label.grid(row=0, column=1, padx=5)
        
        # 状态指示器
        self.status_indicator = tk.Canvas(control_frame, width=100, height=20)
        self.status_indicator.grid(row=0, column=2, padx=10)
        self.draw_status_indicator("disconnected")
        
        # ========== 数据包和频率控制区域 ==========
        packet_control_frame = ttk.LabelFrame(main_frame, text="数据包和发送控制", padding="5")
        packet_control_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # 数据包模式选择
        ttk.Label(packet_control_frame, text="数据包模式:").grid(row=0, column=0, sticky=tk.W)
        packet_mode_combo = ttk.Combobox(packet_control_frame, textvariable=self.data_packet_mode, 
                                        values=["full", "compact"], state="readonly", width=10)
        packet_mode_combo.grid(row=0, column=1, padx=5)
        packet_mode_combo.bind('<<ComboboxSelected>>', self.on_packet_mode_change)
        
        # 发送频率控制
        ttk.Label(packet_control_frame, text="发送频率:").grid(row=0, column=2, sticky=tk.W, padx=(20, 5))
        frequency_frame = ttk.Frame(packet_control_frame)
        frequency_frame.grid(row=0, column=3, sticky=(tk.W, tk.E), padx=5)
        
        self.frequency_scale = ttk.Scale(frequency_frame, from_=1, to=100, variable=self.send_frequency, 
                                        orient=tk.HORIZONTAL, command=self.on_frequency_change)
        self.frequency_scale.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        self.frequency_label = ttk.Label(frequency_frame, text="50 Hz", font=("Arial", 9, "bold"))
        self.frequency_label.grid(row=0, column=1, padx=5)
        
        # 自动发送控制
        self.auto_send_var = tk.BooleanVar(value=False)
        auto_send_check = ttk.Checkbutton(packet_control_frame, text="自动发送", 
                                         variable=self.auto_send_var, command=self.toggle_auto_send)
        auto_send_check.grid(row=0, column=4, padx=20)
        
        # 数据包大小显示
        self.packet_size_label = ttk.Label(packet_control_frame, text="数据包大小: 14 字节", font=("Arial", 9))
        self.packet_size_label.grid(row=0, column=5, padx=10)
        
        # 配置网格权重
        packet_control_frame.columnconfigure(3, weight=1)
        frequency_frame.columnconfigure(0, weight=1)
        
        # ========== 风扇控制区域 ==========
        fan_frame = ttk.LabelFrame(main_frame, text="风扇控制", padding="5")
        fan_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=5)
        
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
        
        # ========== 发送数据监控区域 ==========
        send_data_frame = ttk.LabelFrame(main_frame, text="发送数据监控", padding="5")
        send_data_frame.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # 发送数据包显示
        ttk.Label(send_data_frame, text="发送数据包格式:", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky=tk.W, pady=2)
        
        # 创建发送数据显示区域
        self.send_data_text = tk.Text(send_data_frame, height=4, width=80, font=("Consolas", 9), wrap=tk.WORD)
        self.send_data_text.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # 添加滚动条
        send_scrollbar = ttk.Scrollbar(send_data_frame, orient=tk.VERTICAL, command=self.send_data_text.yview)
        self.send_data_text.configure(yscrollcommand=send_scrollbar.set)
        send_scrollbar.grid(row=1, column=1, sticky=(tk.N, tk.S))
        
        # 发送数据统计
        send_stats_frame = ttk.Frame(send_data_frame)
        send_stats_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=2)
        
        self.send_count_label = ttk.Label(send_stats_frame, text="发送次数: 0", font=("Arial", 9))
        self.send_count_label.grid(row=0, column=0, sticky=tk.W, padx=5)
        
        self.last_send_time_label = ttk.Label(send_stats_frame, text="最后发送: --", font=("Arial", 9))
        self.last_send_time_label.grid(row=0, column=1, sticky=tk.W, padx=20)
        
        ttk.Button(send_stats_frame, text="清空显示", command=self.clear_send_data, width=10).grid(row=0, column=2, padx=5)
        ttk.Button(send_stats_frame, text="复制数据", command=self.copy_send_data, width=10).grid(row=0, column=3, padx=5)
        
        # 初始化发送数据统计
        self.send_count = 0
        self.last_send_time = None
        self.send_data_history = []  # 存储发送数据历史
        self.max_send_history = 50   # 最大历史记录数
        
        # 配置网格权重
        send_data_frame.columnconfigure(0, weight=1)
        
        # ========== 回传数据验证区域 ==========
        feedback_frame = ttk.LabelFrame(main_frame, text="回传数据验证", padding="5")
        feedback_frame.grid(row=6, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # 创建回传数据显示网格
        feedback_data_frame = ttk.Frame(feedback_frame)
        feedback_data_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # 数据包信息
        packet_frame = ttk.LabelFrame(feedback_data_frame, text="数据包信息", padding="3")
        packet_frame.grid(row=0, column=0, padx=5, sticky=(tk.W, tk.E))
        
        self.packet_count_label = ttk.Label(packet_frame, text="数据包: 0", font=("Arial", 9))
        self.packet_count_label.grid(row=0, column=0, sticky=tk.W)
        self.last_packet_time_label = ttk.Label(packet_frame, text="最后接收: --", font=("Arial", 9))
        self.last_packet_time_label.grid(row=1, column=0, sticky=tk.W)
        
        # 原始数据
        raw_frame = ttk.LabelFrame(feedback_data_frame, text="原始数据", padding="3")
        raw_frame.grid(row=0, column=1, padx=5, sticky=(tk.W, tk.E))
        
        self.raw_data_label = ttk.Label(raw_frame, text="原始: --", font=("Consolas", 8), wraplength=200)
        self.raw_data_label.grid(row=0, column=0, sticky=tk.W)
        
        # 数据状态
        status_frame = ttk.LabelFrame(feedback_data_frame, text="数据状态", padding="3")
        status_frame.grid(row=0, column=2, padx=5, sticky=(tk.W, tk.E))
        
        self.data_valid_label = ttk.Label(status_frame, text="状态: 等待数据", font=("Arial", 9))
        self.data_valid_label.grid(row=0, column=0, sticky=tk.W)
        self.zero_data_warning_label = ttk.Label(status_frame, text="警告: 检测到零数据", font=("Arial", 9), foreground="orange")
        self.zero_data_warning_label.grid(row=1, column=0, sticky=tk.W)
        self.zero_data_warning_label.grid_remove()  # 初始隐藏
        
        # 初始化计数器
        self.packet_count = 0
        self.last_packet_time = None
        
        # 兼容性：创建receive_text变量（用于旧代码兼容）
        self.receive_text = tk.Text(main_frame, height=8, width=80)
        self.receive_text.grid(row=7, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        self.receive_text.grid_remove()  # 初始隐藏，因为现在使用高级日志
        
        # ========== 控制按钮区域 ==========
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, pady=10)
        
        # 主要控制按钮
        ttk.Button(button_frame, text="发送完整数据", command=self.send_full_data, 
                  style="Accent.TButton").grid(row=0, column=0, padx=5)
        ttk.Button(button_frame, text="发送控制数据", command=self.send_control_data).grid(row=0, column=1, padx=5)
        ttk.Button(button_frame, text="开启系统", command=lambda: self.send_simple_command(True)).grid(row=0, column=2, padx=5)
        ttk.Button(button_frame, text="关闭系统", command=lambda: self.send_simple_command(False)).grid(row=0, column=3, padx=5)
        
        # 工具按钮
        ttk.Button(button_frame, text="重置控制", command=self.reset_controls).grid(row=0, column=4, padx=5)
        ttk.Button(button_frame, text="清空历史", command=self.clear_sensor_history).grid(row=0, column=5, padx=5)
        
        # ========== 高级数据日志区域 ==========
        log_frame = ttk.LabelFrame(main_frame, text="高级数据日志", padding="5")
        log_frame.grid(row=6, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # 创建日志工具栏
        log_toolbar = ttk.Frame(log_frame)
        log_toolbar.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        # 日志控制按钮
        ttk.Button(log_toolbar, text="清空日志", command=self.clear_receive, width=10).grid(row=0, column=0, padx=2)
        ttk.Button(log_toolbar, text="导出日志", command=self.export_log, width=10).grid(row=0, column=1, padx=2)
        ttk.Button(log_toolbar, text="暂停更新", command=self.toggle_log_pause, width=10).grid(row=0, column=2, padx=2)
        
        # 日志统计信息
        self.log_stats_label = ttk.Label(log_toolbar, text="条目: 0", font=("Arial", 9))
        self.log_stats_label.grid(row=0, column=3, padx=10)
        
        # 日志类型过滤器
        ttk.Label(log_toolbar, text="过滤:", font=("Arial", 9)).grid(row=0, column=4, padx=(20, 5))
        self.log_filter_var = tk.StringVar(value="全部")
        log_filter_combo = ttk.Combobox(log_toolbar, textvariable=self.log_filter_var, 
                                       values=["全部", "发送", "接收", "错误", "状态"], 
                                       state="readonly", width=8)
        log_filter_combo.grid(row=0, column=5, padx=2)
        log_filter_combo.bind('<<ComboboxSelected>>', self.apply_log_filter)
        
        # 搜索框
        ttk.Label(log_toolbar, text="搜索:", font=("Arial", 9)).grid(row=0, column=6, padx=(20, 5))
        self.log_search_var = tk.StringVar()
        log_search_entry = ttk.Entry(log_toolbar, textvariable=self.log_search_var, width=15)
        log_search_entry.grid(row=0, column=7, padx=2)
        log_search_entry.bind('<KeyRelease>', self.search_log)
        
        # 创建高级日志显示区域
        log_display_frame = ttk.Frame(log_frame)
        log_display_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 使用Treeview创建表格样式的日志显示
        columns = ("时间", "类型", "内容")
        self.log_tree = ttk.Treeview(log_display_frame, columns=columns, show="tree headings", height=8)
        
        # 配置列
        self.log_tree.column("#0", width=0, stretch=False)  # 隐藏第一列
        self.log_tree.column("时间", width=80, anchor="center")
        self.log_tree.column("类型", width=60, anchor="center")
        self.log_tree.column("内容", width=400, anchor="w")
        
        # 配置表头
        self.log_tree.heading("时间", text="时间")
        self.log_tree.heading("类型", text="类型")
        self.log_tree.heading("内容", text="内容")
        
        # 添加滚动条
        log_scrollbar = ttk.Scrollbar(log_display_frame, orient=tk.VERTICAL, command=self.log_tree.yview)
        self.log_tree.configure(yscrollcommand=log_scrollbar.set)
        
        # 布局
        self.log_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # 右键菜单
        self.log_context_menu = tk.Menu(self.root, tearoff=0)
        self.log_context_menu.add_command(label="复制内容", command=self.copy_log_content)
        self.log_context_menu.add_command(label="删除选中", command=self.delete_selected_log)
        self.log_context_menu.add_separator()
        self.log_context_menu.add_command(label="清空所有", command=self.clear_receive)
        
        self.log_tree.bind("<Button-3>", self.show_log_context_menu)  # 右键绑定
        
        # 日志状态变量
        self.log_paused = False
        self.log_entries = []
        self.log_entry_count = 0
        
        # 配置网格权重
        log_display_frame.columnconfigure(0, weight=1)
        log_display_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(1, weight=1)
        
        # 配置网格权重
        main_frame.columnconfigure(0, weight=1)
        control_frame.columnconfigure(1, weight=1)
        fan_frame.columnconfigure(1, weight=1)
        servo_frame.columnconfigure(1, weight=1)
        sensor_data_frame.columnconfigure(0, weight=1)
        sensor_data_frame.columnconfigure(1, weight=1)
        sensor_data_frame.columnconfigure(2, weight=1)
        main_frame.rowconfigure(6, weight=1)
        
        # 初始化自动发送定时器
        self.auto_send_timer = None
        self.last_auto_send_time = 0
        self.update_packet_size_display()
    
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
                # 显示发送数据包格式
                self.display_send_data(data, switch_cmd, fan_rpm, servo_angles)
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
    
    def toggle_system(self):
        """切换系统开关状态"""
        current_value = self.throttle_var.get()
        new_value = 1.0 if current_value == 0.0 else 0.0
        self.throttle_var.set(new_value)
        
        # 更新按钮显示
        if new_value > 0.1:
            self.switch_button.config(text="🟢 开启", bg="#4CAF50")
        else:
            self.switch_button.config(text="🔴 关闭", bg="#f44336")
        
        # 更新player_input中的油门值
        self.player_input.throttle = new_value
        
        # 如果已连接，发送控制命令
        if self.is_connected:
            self.send_control_data()
    
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
            
            # 更新回传数据验证区域
            self.update_feedback_display(packet_data)
            
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
    
    def update_feedback_display(self, packet_data):
        """更新回传数据验证区域显示"""
        import time
        
        # 更新数据包计数
        self.packet_count += 1
        self.last_packet_time = time.time()
        
        # 更新数据包信息
        self.packet_count_label.config(text=f"数据包: {self.packet_count}")
        time_str = time.strftime("%H:%M:%S", time.localtime(self.last_packet_time))
        self.last_packet_time_label.config(text=f"最后接收: {time_str}")
        
        # 更新原始数据显示
        raw_data_str = str(packet_data)
        if len(raw_data_str) > 50:
            raw_data_str = raw_data_str[:47] + "..."
        self.raw_data_label.config(text=f"原始: {raw_data_str}")
        
        # 检查数据有效性
        gyro_data = packet_data.get('gyro_data', {})
        all_zero = all(abs(v) < 0.001 for v in gyro_data.values())
        
        if all_zero:
            self.data_valid_label.config(text="状态: 零数据", foreground="orange")
            self.zero_data_warning_label.grid()  # 显示警告
        else:
            self.data_valid_label.config(text="状态: 数据正常", foreground="green")
            self.zero_data_warning_label.grid_remove()  # 隐藏警告
    
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
    
    def append_receive_text(self, text):
        """添加接收文本到高级日志"""
        import time
        
        # 确定日志类型
        if "发送" in text:
            log_type = "发送"
            tag = "send"
        elif "接收" in text:
            log_type = "接收"
            tag = "receive"
        elif "错误" in text:
            log_type = "错误"
            tag = "error"
        else:
            log_type = "状态"
            tag = "status"
        
        # 获取当前时间
        current_time = time.strftime("%H:%M:%S", time.localtime())
        
        # 创建日志条目
        log_entry = {
            "time": current_time,
            "type": log_type,
            "content": text,
            "tag": tag
        }
        
        # 添加到日志列表
        self.log_entries.append(log_entry)
        self.log_entry_count += 1
        
        # 更新统计信息
        self.log_stats_label.config(text=f"条目: {self.log_entry_count}")
        
        # 如果日志未暂停，更新显示
        if not self.log_paused:
            self.update_log_display()
    
    def update_log_display(self):
        """更新日志显示"""
        # 清空当前显示
        for item in self.log_tree.get_children():
            self.log_tree.delete(item)
        
        # 应用过滤和搜索
        filtered_entries = self.filter_log_entries()
        
        # 添加条目到Treeview
        for entry in filtered_entries:
            item_id = self.log_tree.insert("", "end", values=(entry["time"], entry["type"], entry["content"]))
            
            # 根据类型设置标签
            if entry["tag"] == "error":
                self.log_tree.item(item_id, tags=("error",))
            elif entry["tag"] == "send":
                self.log_tree.item(item_id, tags=("send",))
            elif entry["tag"] == "receive":
                self.log_tree.item(item_id, tags=("receive",))
        
        # 滚动到底部
        if filtered_entries:
            self.log_tree.see(self.log_tree.get_children()[-1])
    
    def filter_log_entries(self):
        """过滤日志条目"""
        filtered = self.log_entries.copy()
        
        # 应用类型过滤
        filter_type = self.log_filter_var.get()
        if filter_type != "全部":
            filtered = [entry for entry in filtered if entry["type"] == filter_type]
        
        # 应用搜索过滤
        search_text = self.log_search_var.get().lower()
        if search_text:
            filtered = [entry for entry in filtered if search_text in entry["content"].lower()]
        
        return filtered
    
    def apply_log_filter(self, event=None):
        """应用日志过滤器"""
        self.update_log_display()
    
    def search_log(self, event=None):
        """搜索日志"""
        self.update_log_display()
    
    def toggle_log_pause(self):
        """切换日志暂停状态"""
        self.log_paused = not self.log_paused
        button_text = "继续更新" if self.log_paused else "暂停更新"
        for widget in self.root.winfo_children():
            if isinstance(widget, ttk.Button) and widget.cget("text") in ["暂停更新", "继续更新"]:
                widget.config(text=button_text)
                break
    
    def export_log(self):
        """导出日志到文件"""
        import tkinter.filedialog as filedialog
        import os
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="导出日志"
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write("航模地面站数据日志\n")
                    f.write("=" * 50 + "\n\n")
                    
                    for entry in self.log_entries:
                        f.write(f"[{entry['time']}] [{entry['type']}] {entry['content']}\n")
                
                messagebox.showinfo("成功", f"日志已导出到: {os.path.basename(filename)}")
            except Exception as e:
                messagebox.showerror("错误", f"导出失败: {e}")
    
    def show_log_context_menu(self, event):
        """显示日志右键菜单"""
        item = self.log_tree.identify_row(event.y)
        if item:
            self.log_tree.selection_set(item)
            self.log_context_menu.post(event.x_root, event.y_root)
    
    def copy_log_content(self):
        """复制选中的日志内容"""
        selected = self.log_tree.selection()
        if selected:
            item = selected[0]
            content = self.log_tree.item(item, "values")[2]  # 内容在第三列
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            messagebox.showinfo("成功", "内容已复制到剪贴板")
    
    def delete_selected_log(self):
        """删除选中的日志条目"""
        selected = self.log_tree.selection()
        if selected:
            for item in selected:
                # 从日志列表中删除对应的条目
                item_values = self.log_tree.item(item, "values")
                for i, entry in enumerate(self.log_entries):
                    if entry["time"] == item_values[0] and entry["content"] == item_values[2]:
                        del self.log_entries[i]
                        self.log_entry_count -= 1
                        break
                self.log_tree.delete(item)
            
            # 更新统计信息
            self.log_stats_label.config(text=f"条目: {self.log_entry_count}")
    
    def clear_receive(self):
        """清空日志"""
        self.log_entries = []
        self.log_entry_count = 0
        for item in self.log_tree.get_children():
            self.log_tree.delete(item)
        self.log_stats_label.config(text="条目: 0")
    
    def display_send_data(self, data_bytes, switch_cmd, fan_rpm, servo_angles):
        """显示发送数据包格式，按照'aa.....bb.j校验位'格式"""
        import time
        import struct
        
        # 更新发送统计
        self.send_count += 1
        self.last_send_time = time.time()
        
        # 更新统计显示
        self.send_count_label.config(text=f"发送次数: {self.send_count}")
        time_str = time.strftime("%H:%M:%S", time.localtime(self.last_send_time))
        self.last_send_time_label.config(text=f"最后发送: {time_str}")
        
        # 将字节数据转换为十六进制字符串
        hex_data = data_bytes.hex()
        
        # 按照协议格式解析数据包
        # 上行数据包格式: 0xAA + switch_cmd + fan_rpm + servo[4] + 0xBB + CRC
        if len(data_bytes) >= 14:  # 完整上行数据包
            try:
                # 使用struct正确解析小端序数据
                unpacked = struct.unpack('<B B h 4h B B', data_bytes)
                header = unpacked[0]
                switch_value = unpacked[1]
                fan_value = unpacked[2]
                servo1_value = unpacked[3]
                servo2_value = unpacked[4]
                servo3_value = unpacked[5]
                servo4_value = unpacked[6]
                footer = unpacked[7]
                crc_value = unpacked[8]
                
                # 转换为十六进制显示
                header_hex = f"{header:02x}"
                switch_hex = f"{switch_value:02x}"
                fan_hex = f"{fan_value:04x}"  # 2字节风扇转速
                servo1_hex = f"{servo1_value:02x}"
                servo2_hex = f"{servo2_value:02x}"
                servo3_hex = f"{servo3_value:02x}"
                servo4_hex = f"{servo4_value:02x}"
                footer_hex = f"{footer:02x}"
                crc_hex = f"{crc_value:02x}"
                
                # 构建显示格式: aa.....bb.j校验位
                data_display = f"aa{switch_hex}{fan_hex}{servo1_hex}{servo2_hex}{servo3_hex}{servo4_hex}bb.{crc_hex}"
                
                detailed_info = (
                    f"数据包格式: {data_display}\n"
                    f"详细解析:\n"
                    f"  包头: 0x{header_hex} (AA)\n"
                    f"  开关命令: 0x{switch_hex} = {switch_value} ({'开启' if switch_value == 1 else '关闭'})\n"
                    f"  风扇转速: 0x{fan_hex} = {fan_value} RPM\n"
                    f"  舵机1角度: 0x{servo1_hex} = {servo1_value}°\n"
                    f"  舵机2角度: 0x{servo2_hex} = {servo2_value}°\n"
                    f"  舵机3角度: 0x{servo3_hex} = {servo3_value}°\n"
                    f"  舵机4角度: 0x{servo4_hex} = {servo4_value}°\n"
                    f"  包尾: 0x{footer_hex} (BB)\n"
                    f"  CRC校验: 0x{crc_hex} = {crc_value}\n"
                    f"完整十六进制: {hex_data}\n"
                    f"{'-'*60}"
                )
            except Exception as e:
                # 如果解析失败，使用原始十六进制显示
                data_display = hex_data
                detailed_info = f"解析错误: {e}\n完整十六进制: {hex_data}\n{'-'*60}"
        else:
            # 简单命令数据包
            data_display = hex_data
            detailed_info = f"简单命令数据包: {hex_data}\n{'-'*60}"
        
        # 添加到发送数据历史
        send_entry = {
            "time": time_str,
            "data_display": data_display,
            "detailed_info": detailed_info,
            "raw_data": hex_data
        }
        self.send_data_history.append(send_entry)
        
        # 限制历史记录数量
        if len(self.send_data_history) > self.max_send_history:
            self.send_data_history.pop(0)
        
        # 更新显示区域
        self.update_send_data_display()
    
    def update_send_data_display(self):
        """更新发送数据显示区域"""
        # 清空当前显示
        self.send_data_text.delete(1.0, tk.END)
        
        # 添加最新的发送数据
        for entry in self.send_data_history[-10:]:  # 显示最近10条
            self.send_data_text.insert(tk.END, f"[{entry['time']}] {entry['data_display']}\n")
            self.send_data_text.insert(tk.END, f"{entry['detailed_info']}\n\n")
        
        # 滚动到底部
        self.send_data_text.see(tk.END)
    
    def clear_send_data(self):
        """清空发送数据显示"""
        self.send_data_text.delete(1.0, tk.END)
        self.send_data_history = []
        self.send_count = 0
        self.send_count_label.config(text="发送次数: 0")
        self.last_send_time_label.config(text="最后发送: --")
        self.send_data_text.insert(tk.END, "发送数据已清空\n")
    
    def copy_send_data(self):
        """复制发送数据到剪贴板"""
        if self.send_data_history:
            # 获取最新的发送数据
            latest_entry = self.send_data_history[-1]
            copy_text = f"发送数据包: {latest_entry['data_display']}\n{latest_entry['detailed_info']}"
            
            self.root.clipboard_clear()
            self.root.clipboard_append(copy_text)
            messagebox.showinfo("成功", "发送数据已复制到剪贴板")
        else:
            messagebox.showinfo("信息", "没有可复制的发送数据")
    
    # ========== 新增的数据包大小和频率控制回调函数 ==========
    
    def on_packet_mode_change(self, event=None):
        """数据包模式变化回调"""
        mode = self.data_packet_mode.get()
        if self.protocol.set_data_packet_mode(mode):
            self.update_packet_size_display()
            self.append_receive_text(f"数据包模式已切换为: {mode}")
        else:
            messagebox.showerror("错误", "无效的数据包模式")
    
    def on_frequency_change(self, value):
        """发送频率变化回调"""
        frequency = int(float(value))
        if self.protocol.set_send_frequency(frequency):
            self.frequency_label.config(text=f"{frequency} Hz")
            self.send_interval = int(1000 / frequency)  # 转换为毫秒
            self.append_receive_text(f"发送频率已设置为: {frequency} Hz")
            
            # 如果自动发送已启用，重新启动定时器
            if self.auto_send_var.get():
                self.stop_auto_send()
                self.start_auto_send()
        else:
            messagebox.showerror("错误", "无效的发送频率")
    
    def update_packet_size_display(self):
        """更新数据包大小显示"""
        packet_size = self.protocol.get_current_packet_size()
        mode = self.data_packet_mode.get()
        self.packet_size_label.config(text=f"数据包大小: {packet_size} 字节 ({mode}模式)")
    
    def toggle_auto_send(self):
        """切换自动发送状态"""
        if self.auto_send_var.get():
            if not self.is_connected:
                messagebox.showerror("错误", "串口未连接，无法启用自动发送")
                self.auto_send_var.set(False)
                return
            self.start_auto_send()
            self.append_receive_text("自动发送已启用")
        else:
            self.stop_auto_send()
            self.append_receive_text("自动发送已禁用")
    
    def start_auto_send(self):
        """开始自动发送"""
        if self.auto_send_timer is not None:
            self.root.after_cancel(self.auto_send_timer)
        
        def auto_send_loop():
            if self.auto_send_var.get() and self.is_connected:
                # 获取当前控制值
                switch_cmd = 1 if self.throttle_var.get() > 0.1 else 0
                fan_rpm = self.fan_speed_var.get()
                servo_angles = [var.get() for var in self.servo_vars]
                
                # 根据当前模式编码数据
                data = self.protocol.encode_control_data(switch_cmd, fan_rpm, servo_angles)
                if data and self.serial_initializer.send_data(data):
                    # 更新发送统计
                    self.send_statistics['total_sent'] += 1
                    
                    # 显示发送信息
                    mode_text = "精简" if self.data_packet_mode.get() == "compact" else "完整"
                    self.append_receive_text(f"自动发送[{mode_text}]: 开关={switch_cmd}, 风扇={fan_rpm}RPM")
                    
                    # 显示发送数据包格式
                    self.display_send_data(data, switch_cmd, fan_rpm, servo_angles)
                
                # 安排下一次发送
                self.auto_send_timer = self.root.after(self.send_interval, auto_send_loop)
        
        # 立即开始第一次发送
        auto_send_loop()
    
    def stop_auto_send(self):
        """停止自动发送"""
        if self.auto_send_timer is not None:
            self.root.after_cancel(self.auto_send_timer)
            self.auto_send_timer = None
    
    def run(self):
        """运行GUI"""
        self.root.mainloop()
