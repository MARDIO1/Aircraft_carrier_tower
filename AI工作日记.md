# AI工作日记

## 2025-11-30 02:30 - 航空母舰塔楼项目创建

### 实现内容

创建了一个完整的航模地面站控制软件，包含以下模块：

1. **protocol.py** - 串口通讯协议配置
   - 定义了数据包格式：0xAA + 总开关(1字节) + 风扇转速(2字节) + 4个舵机角度(各2字节) + 0xBB
   - 实现了数据编码和解码函数
   - 使用小端序处理16位整数

2. **initial.py** - 初始化模块
   - 自动检测可用COM口
   - 初始化串口连接（115200波特率，8N1）
   - 预设状态配置功能

3. **playerInput.py** - 键盘输入捕获
   - 捕获空格键（切换总开关）
   - 捕获数字1/2键（预设状态切换）
   - 使用keyboard库实现非阻塞输入检测

4. **UART_send.py** - 串口发送模块
   - 将键盘信号编码为协议格式
   - 通过串口发送数据
   - 只在数据变化时发送，减少通信负载

5. **terminal_GUI.py** - 控制台界面
   - 显示三行信息：上次发送数据、COM口状态、当前按键状态
   - 使用ANSI转义序列实现清屏刷新
   - 提供操作提示

6. **main.py** - 主程序
   - 集成所有模块
   - 管理多线程启动和停止
   - 处理程序退出信号

7. **项目配置**
   - pyproject.toml - 依赖管理（pyserial, keyboard）
   - README.md - 项目文档和使用说明

### 技术特点

- 多线程架构：terminal_GUI和playerInput在同一线程，UART_send在独立线程
- 线程间通过共享ProtocolData对象传递数据
- 使用uv进行Python包管理
- 支持PowerShell终端运行
- 完整的错误处理和资源清理

### 项目结构

├── src/
│   ├── main.py
│   ├── protocol.py
│   ├── initial.py
│   ├── playerInput.py
│   ├── UART_send.py
│   └── terminal_GUI.py
├── pyproject.toml
├── README.md
└── AI工作日记.md

项目已按照要求完成，可以运行测试。

## 2025-11-30 02:41 - VSCode环境配置

### 配置内容

1. **创建VSCode工作区设置**
   - 创建 `.vscode/settings.json` 文件
   - 配置Python解释器路径为 `.venv\Scripts\python.exe`
   - 启用终端环境自动激活

2. **验证依赖包安装**
   - 使用 `uv sync` 重新同步依赖包
   - 验证 pyserial 和 keyboard 包正确安装
   - 确认Python 3.13.5环境正常工作

### 配置结果 

- VSCode现在可以正确识别uv虚拟环境中的Python包
- 代码补全和语法检查功能正常工作
- 程序可以在VSCode中正常运行和调试

### 2025.12.17晚上22.45

  1. **本次修改目标**

  - 将目前可以发送数据，接收数据的功能保留，增设状态：开启running；关闭：stop;并在stop状态基础上可以进入调参模式tuning
  调参模式下系统发送0xee帧头0xff帧尾
  我现在基本上可以确定，要先完成数据的集成定义三种模式，把调参数据编码，并且修改ui