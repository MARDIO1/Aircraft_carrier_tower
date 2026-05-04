---
name: ground-station-automation
description: "Use when: testing or debugging ground station serial communication, telemetry, pinging the STM32 board, analyzing blackbox logs, or running hardware/COM stress tests. This skill helps the AI autonomously run Python test scripts and validate the UART communication between the STM32F411 and the Python Ground Station."
---

# 地面站自动化测试指南 (Ground Station Automation Guide)

## 🎯 业务上下文
本项目为 Robomaster 飞镖的地面站 (Aircraft_carrier_tower)。地面站使用 Python 编写，通过 USB-TTL 串口与 `STM32F411` 飞控板通信。
未来的架构包括后端（例如 FastAPI）和前端（例如 Vue3 / React），通过 WebSocket 将串口解包数据分发给 Web 面板。

## 🔌 硬件与串口拓扑
- **目标设备**: STM32F411xE, Cortex-M4F。
- **默认波特率**: `115200` (8N1)。
- **串口设备发现**: 严禁在脚本中硬编码 `COMx`。应该使用 `python -m serial.tools.list_ports` 获取列表，或者运行 `tools/find_stlink_port.py` 根据 VID/PID 自动匹配。

## 📡 通信协议标准
1. **帧格式 (Frame Format)**:
   - 下发（Ground Station -> STM32）: 帧头 `0xAA`，帧尾 `0xBB`
   - 上传（STM32 -> Ground Station）: 帧头 `0xCC`，帧尾 `0xDD`
2. **校验与验证 (Validation)**:
   - STM32 硬件 CRC8 校验。参考 `src/crc_calculator.py` 或 `src/protocol_parser.py` 进行数据包完整性验证。
3. **关键指令 (Command IDs)**:
   - `0x00` (STOP)
   - `0x01` (AUTO_CONTRL)
   - `0xA5` (SAVE_DATA)
   - （详见 `AGENTS.md`）

## 🛠️ 自动化测试工作流 (Automation Workflow)

作为 AI AI 助手，在执行地面站串口相关任务时，请严格遵循以下执行路径：

### 1. 基础连通性测试 (Ping Test)
**指令**: 运行目标设备的 Ping/握手脚本。
**操作**: 
```bash
python tools/send_save_command.py --timeout 10
# 或者未来的 ping_board.py
```
**期望结果**: 收到 ACK 包，例如 `CC A6 ... DD`。

### 2. 压力与丢包测试 (Stress Testing)
**指令**: 进行一定时间的高密度读写。
**操作**:
```bash
python tools/stress_test_uart.py --duration 10 --baud 115200
```
**异常处理**:
- **丢包 (Drop)**: 检查 `ReadTimeout` 或被抛弃的非规范帧头。
- **CRC 错误 (CRC Error)**: 检查数据段中间是否发生了截断或干扰。

### 3. 日志分析回溯 (Blackbox Log Analysis)
当串口传输崩溃或者飞控处于异常状态时：
1. 搜索 `blackbox_logs/` 目录下的最新 `.csv`。
2. 利用 Python 预处理脚本或直接读取文件，分析最后 100 行的状态字段或 PID 抛物线是否发散。

## 🤖 虚拟环境测试 (Mocking)
如果当前设备没有连接 STM32 硬件，则必须使用 Mock 工具，以进行完整的 Web/后端全栈测试：
**操作**:
```bash
python tools/mock_stm32_device.py --port loopback
```
接着再启动后端和前端服务。

## ⚠️ 约束限制
- **严禁**使用终端死循环读取串口（如单纯的 `cat /dev/ttyUSB0` 或无限循环的 `serial.read()`），这会导致 AI 上下文爆满（Token 超载），必须通过带 `--timeout` 或者重定向到日志文件的 Python 脚本来进行。
- 分析错误时必须结合终端输出和 `.csv` 飞行日志。
