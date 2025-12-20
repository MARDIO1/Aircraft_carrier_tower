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
### 2025.12.20

  -，现在要靠状态机来实现多种模式，原来的开关数据现在变成状态数据，0x00停止，0x01
  if key == 'a':
                    self._select_prev_pid()
                elif key == 'd':
                    self._select_next_pid()
                elif key == 'q':
                    self._select_prev_param()
                elif key == 'e':
                    self._select_next_param()
                #输入数值和发送
                elif key == 'enter':
                    self._send_current_pid()
                elif key == 'backspace':
                    self._delete_input_char()
                elif key == '.':
                    self._add_decimal_point()
                elif key in ['0', '1','2','3','4','5','6','7','8','9']:
                    self._add_digit(key)
                    2025.12.21 1.42凌晨
                    主函数基本兼容性很高，初始化函数100兼容，最关键的协议和输入处理中核心代码有需要定义状态机，协议最好是能每一种状态机有它自己的结构体，方便扩展，一个总的编码函数内设跳转不同状态机下编码函数，我还希望能有一个框架就是未来也许实现接收数据也和状态机有关应该留有扩展余地，既然你不做状态机保护处理，那我做，必须在stop才能有效切换为tuning
                    输入处理 创立二维数组，通过上下来切换状态，初始是在auto模式，每一次切换需要摁enter来确认，这就很方便扩展，进入调参模式后依旧一维数组，按enter确认，下面舵机同理但需要输入数字处理，pid二维数组，一发发一组既需要上下检索，按enter进入下一个参数选择，输入数字处理按enter确认输入完成，此时再摁enter开始发送数据，jacobian同理
                    ui像现在一样的呈现就可以


                    状态机
                    0 stop 0x00   发三个字节aa 00 bb
                    1 auto  0x01   发21个字节 0xAA + uint8[1]总开关 + int16[1]风扇转速 + float32[4]舵机角度 + 0xBB
                    2 tower  0x02   0xAA + uint8[1]总开关 + int16[1]风扇转速 + float32[4]舵机角度 + 0xBB
                    3 tuning   不用发 
                       0  servo    19字节 0xa1  aa 0xa1 float[4] bb
                       1  pid    0xa2  aa 0xa2 0x00到0xc2 决定哪组参数 float[6] bb
                       2  jacobian  0xa3 aa  float[3][4] bb
                        
                       

