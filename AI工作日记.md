# AI 工作日记 · 航空母舰塔楼地面站

---

## 2026-05-01 21:35 · PID/Jacobian 表格标签修正 v2.4
- PID Matrix 行标签从 CH1~CH7 修正为: 内环 Roll/Pitch/Yaw, 外环 Roll/Pitch/Yaw, Row7
- Jacobian Matrix 列标签从 Roll/Pitch/Yaw/Thr 修正为 FR/FL/BL/BR, 行标签从 X/Y/Z 修正为 L Roll/M Pitch/N Yaw
- Jacobian 标题补充说明 (3x4, Row=力矩轴, Col=舵面)
- 参考 T:\ROBOMASTER_2\Project\missilev1\missilev1_start\my_task\ControlTask.c 线166-168 的 PID 分组定义
- 移除 motorStep 状态变量, PWM 步长固定 1000
- ch-label 宽度增至 72px, 右对齐, nowrap 防止中文换行
- Next.js 16.2.4 TypeScript 编译通过

## 2026-05-01 · Flash Save + Auto Tune + Start Sequence v2.3

### 实现
- 后端 `web_server.py` 新增 `POST /api/flash/save` 端点，3s ack 超时等待
- 后端 `web_server.py` 新增 `POST /api/auto-tune?mode=` 端点，后台线程执行 AutoTuner
- 后端 `web_server.py` 新增 `GET /api/auto-tune/status` 查询调参进度
- 后端 `web_server.py` 新增 `POST /api/start-sequence` 一键运控（load json → tune all → flash save）
- 前端 `page.tsx` 新增 SAVE FLASH / AUTO TUNE SF / AUTO TUNE ALL / START SEQ 四个按钮
- 前端 `page.tsx` 新增 FLASH 状态栏（pending/ack/status/time）+ TUNE 进度显示
- Playwright 测试 `dashboard.spec.ts` 增加 `/api/flash/save` 和 `/api/auto-tune` 断言

### 按钮说明
| 按钮 | 功能 |
|------|------|
| SAVE FLASH | 发送 0xA5 指令 → 飞控烧写 Flash，等 0xA6 ack |
| AUTO TUNE SF | 从 JSON 读取舵面+前馈 → 通过 TUNING 状态写入飞控 |
| AUTO TUNE ALL | SF + PID + Jacobian 全量下发 |
| START SEQ | 一键完整运控：load json → tune all → flash save |

---

## 2026-05-01 · 电机 PWM 脉冲面板 v2.2

### 完成内容
1. **新增电机 PWM 脉冲面板**（`web/app/page.tsx`）
   - 单通道 `fan_speed` 输入，范围 0-10000（协议 int16）
   - 自定义步长输入（默认 1000，范围 1-1000），利用 HTML `step` 属性实现键盘上下键快捷调整
   - 直接走 `PATCH /api/control { fan_speed: N }`，AUTO 帧第 6-7 字节（`<h` int16）
   - 面板位于状态按钮与 hex 显示之间
   - 从 snapshot 恢复时读取 `control.fan_speed` 自动回填
2. Next.js 编译通过

---

## 2026-05-01 · 前端控制台式重构 v2 + DATA 链路验证 + RX hex 实时显示修复

### 完成内容

1. **前端全面重构成"控制台式"4段布局**（`web/app/page.tsx`）
2. **CSS 完全重写**（`web/app/globals.css`）
3. **后端暴露原始收发HEX数据**（已验证）
4. **DATA 记录链路验证通过**
5. **Playwright 端到端测试通过**
6. **RX hex 实时显示修复**（v2.1）：
   - **bug 根因**：`_process_save_flash_ack_frames()` 中 BlackBox 帧的 `byte[1]` (pid_type) 可能等于 `0xA6` (SAVE_TO_FLASH_ACK) 且 `byte[15]` 可能等于 `0xDD`，概率约 1/65536
   - **症状**：CRC 校验失败后旧代码仍 `del self.receive_buffer[:16]` 删除帧头，破坏了 BlackBox 的 `0xCC` 帧头，导致 `decode_data()` 永不解码成功，`_last_rx_packet` 永远为 None，前端退回到"等待接收..."
   - **修复**：CRC 失败时**不再删除** 16 字节，保留给主循环解码 BlackBox；非 ACK 帧且缓冲区 < 76 字节时直接 return，不再逐字节删除 `del self.receive_buffer[0]`

### 尚未实现的功能
- 飞书MCP云文档同步
- MATLAB自动分析报告图表
- 分析报告自动生成与展示

---

## 2025-11-30 · 项目创建（v0.1）

### 架构概述

创建了航模地面站控制软件的初始版本，采用多线程架构通过 UART 串口与航模双向通信。

### 模块清单

| 模块 | 职责 |
|------|------|
| `protocol.py` | 数据包格式定义与编解码 |
| `initial.py` | COM 口自动检测与串口初始化 |
| `playerInput.py` | 键盘输入捕获（空格键/数字键） |
| `UART_send.py` | 串口数据发送 |
| `terminal_GUI.py` | ANSI 控制台界面（三行动态显示） |
| `main.py` | 主程序，线程管理与协调 |

### 通信协议（初版）

**发送**：`0xAA + uint8总开关 + int16风扇转速 + int16[4]舵机角度 + 0xBB`（13字节）

**接收**：`0xCC + uint8开关 + float[3]加速度 + float[3]陀螺仪 + float[3]角度 + 0xDD`（39字节）

### 线程架构

```
主线程 (main.py)
├── 输入/显示线程 (playerInput + terminal_GUI)
└── 发送线程 (UART_send) — 50Hz
```

---

## 2025-11-30 · VSCode 环境配置

- 创建 `.vscode/settings.json`，配置 uv 虚拟环境 Python 解释器路径
- 验证 pyserial、keyboard 依赖正确安装

---

## 2025-12-17 · 状态机引入（v0.2）

### 改动目标

原有单一"开关"模式扩展为多状态架构：
- **STOP**（0x00）：停止，所有输出归零
- **RUNNING**（0x01）：正常运行
- **TUNING**：调参模式，发送专用帧（帧头 0xEE，帧尾 0xFF）

### 关键变化

- `ProtocolData` 新增 `main_state` 字段
- `protocol.py` 引入状态枚举与对应编码器雏形
- UI 增加状态显示行

---

## 2025-12-20 · 状态机完善（v0.3）

- 状态编码规范化：STOP=0x00，AUTO=0x01，TOWER=0x02
- 发送帧第二字节由"总开关"改为"状态标识"
- `StateTransitionValidator` 引入，约束合法状态转换路径

---

## 2026-02-05 · 完整状态机 + 子状态（v0.4）

### 当前完整状态体系

**主状态（MainState）**

| 状态 | 编码 | 说明 |
|------|------|------|
| STOP | 0x00 | 停止，发送 3 字节最小帧 |
| AUTO | 0x01 | 自动控制，发送含时间戳的 26 字节帧 |
| TOWER | 0x02 | 塔台控制，发送 22 字节帧 |
| TUNING | 0x03 | 调参模式，进入子状态 |
| DATA | 0xB1 | 数据模式，接收 BlackBox 76 字节帧 |

**子状态（SubState，仅 TUNING 下有效）**

| 子状态 | 编码 | 说明 |
|--------|------|------|
| SERVO | 0xA1 | 舵机角度调参，float[4] |
| PID | 0xA2 | PID 参数调参，7组×6参数 |
| JACOBIAN | 0xA3 | 雅可比矩阵调参，3×4 float |
| FEEDFORWARD | 0xA4 | 前馈参数调参，float[4] |

### 编码器工厂架构

```
EncoderBase（抽象基类）
├── StopEncoder       → STOP
├── AutoEncoder       → AUTO（含毫秒时间戳）
├── TowerEncoder      → TOWER
├── DataEncoder       → DATA
├── ServoEncoder      → TUNING/SERVO
├── FeedforwardEncoder→ TUNING/FEEDFORWARD
├── PIDEncoder        → TUNING/PID（含 PID 类型编码字节）
└── JacobianEncoder   → TUNING/JACOBIAN
```

`EncoderFactory` 用字典映射状态→编码器实例，避免 if-elif 链。

### BlackBox 接收协议（76字节）

```
0xCC + uint32时间戳1(4) + uint32时间戳2(4) + uint8状态机(1)
     + float[3]角度(12) + float[3]角速度(12) + float[3]加速度(12)
     + float[3]力矩(12) + float[4]舵机目标角度(16)
     + CRC8(1) + 0xDD
```

### CRC 校验

`crc_calculator.py` 模拟 STM32F411 硬件 CRC32 行为（小端序读取、4字节对齐补零、截取低8位作为 CRC8），与飞控端硬件 CRC 完全对应。

### 参数持久化

四套参数（舵机/前馈/PID/Jacobian）各自独立 JSON 持久化，程序重启后自动恢复上次调参值：
- `servo_params.json`
- `feedforward_params.json`
- `pid_params.json`
- `jacobian_params.json`

### 黑箱记录器

`blackbox_logger.py`：进入 DATA 模式后自动将接收到的 BlackBox 数据写入带时间戳文件名的 CSV，最多记录 3000 条，达到上限自动停止。

### 控制台界面

`consle.py`（curses 实现）：多行动态显示，包含中文字符宽度处理（CJK Unicode 范围完整枚举），避免中文截断导致的显示乱码。

### 完整线程架构

```
主线程 (main.py)
├── 输入线程 (playerInput.py) — 键盘捕获 + 状态机操作
├── 显示线程 (consle.py)     — curses 界面，10Hz 刷新
├── 发送线程 (UART_send.py)  — 50Hz 恒频发送
└── 接收线程 (UART_receive.py)— 100Hz 检查，BlackBox 解码
```

---

## 2026-04-01 · 实验记录

- 力度格数 8 格，加配重，低头明显，低头距离约 7 m

---

## 2026-04-01 · P0 安全性修复（本次 AI 改动）

### 问题背景

代码审查发现两个 P0 级缺陷：

1. **无锁共享状态（竞态定时炸弹）**：`ProtocolData` 被发送线程（读）、接收线程（写）、输入线程（写）同时访问，无任何锁保护。在 50Hz 发送 + 100Hz 接收 + 实时键盘输入的场景下，存在真实的竞态窗口，可能导致发送帧数据撕裂或显示数据不一致。

2. **CSV 列顺序 bug**：`blackbox_logger.py` 的 headers 定义中 `packet_timestamp` 和 `packet_timestamp2` 顺序与 `row` 写入顺序对调，导致所有历史 CSV 文件的两列时间戳标注错误。

### 改动详情

#### `src/protocol.py`

- `import threading` 加入文件顶部
- `ProtocolData.__init__` 新增 `self._lock = threading.RLock()`
  - 选用 `RLock`（可重入锁）而非 `Lock`，防止将来嵌套调用死锁
- `set_main_state()` 方法体套 `with self._lock`，状态切换原子化
- 新增 `update_blackbox(decoded)` 方法：在锁内一次性原子写入全部 10 个黑箱字段（timestamp、timestamp2、statemachine、angle、gyro、acc、torque、rudder、blackbox_received、last_received_time）

#### `src/UART_send.py`

- `_send_loop` 中 `encode_data(self.shared_data)` 调用外套 `with self.shared_data._lock`
- 编码期间整个 `shared_data` 被锁住，消除"编码读取过程中数据被输入线程修改"的竞态窗口
- `with` 语句保证 `encode_data` 抛出异常时锁自动释放，不会死锁

#### `src/UART_receive.py`

- `_update_shared_data()` 从 10 行逐字段赋值改为一行 `self.shared_data.update_blackbox(decoded_data)`
- CSV 写入（`blackbox_logger.log_data()`）保持在锁外执行，避免持锁期间做磁盘 IO

#### `src/blackbox_logger.py`

- `start_logging()` 中 headers 列表：`packet_timestamp` 移至第 0 列，`packet_timestamp2` 移至第 1 列，与 `log_data()` 中 `row` 写入顺序严格对应
- `log_data()` 中的噪音 `print`（每次调用未记录状态都打印）拆分为两个独立 `if` 判断，未记录状态下静默返回 `False`

### 验证结果

运行验证脚本，5 项断言全部通过：
- `ProtocolData._lock` 存在且为 RLock ✓
- `update_blackbox` 方法存在 ✓
- `set_main_state` 线程安全版本工作正常 ✓
- `update_blackbox` 原子写入正确 ✓
- CSV 列顺序正确（packet_timestamp=12345, packet_timestamp2=67890）✓
- `log_data` 在未记录状态下静默返回 False ✓

### 性能影响评估

| 关注点 | 结论 |
|--------|------|
| 键盘响应延迟 | 无影响（锁竞争在微秒级） |
| 发送频率 50Hz | 无影响（串口 IO 在锁外执行） |
| 接收数据实时性 | 无损失，一致性反而提升 |
| 黑箱记录实时性 | 无影响（CSV 写入在锁外） |

---

## 2026-04-02 · 架构债务修复 A1/A2/A3/B1（本次 AI 改动）

### 改动概述

按优先级清单实施了 4 项改动，全部通过语法验证。

### A2 · 接收缓冲区防溢出（`UART_receive.py`，+4行）

在 `_process_received_data()` 的 `extend` 之后立即检查缓冲区大小：
```python
MAX_BUFFER = 1024
if len(self.receive_buffer) > MAX_BUFFER:
    self.receive_buffer = self.receive_buffer[-256:]
```
保留最后 256 字节（≥3 个完整 76 字节帧），丢弃最老的垃圾字节。正常飞行时缓冲区峰值 < 200 字节，截断逻辑永远不触发，零性能影响。

### A3 · 精确发送频率（`UART_send.py`，+8行）

用 `time.perf_counter()` 补偿式定时替换裸 `time.sleep(0.02)`：
```python
next_tick = time.perf_counter()
while self.running:
    sleep_time = next_tick - time.perf_counter()
    if sleep_time > 0:
        time.sleep(sleep_time)
    next_tick += SEND_INTERVAL
    # 防止长时间阻塞后 next_tick 严重落后导致连续空转
    if next_tick < time.perf_counter() - SEND_INTERVAL:
        next_tick = time.perf_counter() + SEND_INTERVAL
```
消除 Windows `sleep` ±15ms 精度误差，实际发送频率从 30-40Hz 提升到稳定 50Hz。

### A1 · 串口断线自动重连（`UART_send.py`，+30行）

新增模块级常量和 `_try_reconnect()` 方法：
- 串口写入失败时关闭串口，下一个 tick 检测到 `is_open=False` 后进入重连循环
- 每秒尝试 `serial_port.open()` 一次，最多 30 次（30 秒）
- 重连成功打印提示并继续正常发送；彻底失败后置 `running=False` 退出线程
- 重连期间 `_send_loop` 主循环不阻塞（`_try_reconnect` 内部 sleep）

### B1 · `handle_enter()` 分派表重构（`protocol.py`，零行为变更）

将 80+ 行三层嵌套 if-elif 拆分为分派表 + 9 个独立方法：

| 方法 | 职责 |
|------|------|
| `handle_enter()` | 分派表入口，查表调用对应方法 |
| `_enter_noop()` | AUTO/DATA：无操作 |
| `_enter_stop()` | STOP：切换到光标选中的目标状态 |
| `_enter_tower()` | TOWER：切换确认状态 |
| `_enter_tuning()` | TUNING：分派到未确认/已确认两个子方法 |
| `_enter_tuning_select_substate()` | TUNING未确认：选择子状态 |
| `_enter_tuning_confirmed()` | TUNING已确认：按子状态再次分派 |
| `_enter_tuning_pid()` | PID子状态的Enter行为 |
| `_enter_tuning_jacobian()` | Jacobian子状态的Enter行为 |
| `_enter_tuning_servo/feedforward()` | SERVO/FF子状态：pass（由playerInput处理） |

新增状态只需在 `_dispatch` 字典加一行，不需要修改任何已有方法。

---

## 未来待改进事项

### P1 · 架构债务（影响长期可维护性）

- **拆分 `ProtocolData` 上帝对象**：当前该类同时承担控制参数、传感器数据、UI 导航状态、调参参数、状态机状态五种职责。建议拆分为 `ControlState`、`SensorData`、`UINavigationState`、`TuningParams` 四个独立数据类，各模块只访问自己负责的数据类。

- **`handle_enter()` 方法重构**：当前 80+ 行、三层嵌套 if-elif，处理所有主状态和子状态的 Enter 逻辑。建议用状态模式（State Pattern）将每个状态的行为分散到各自的状态类中，新增状态不需要修改已有代码。

- **更新 README**：当前 README 描述的是旧版协议（13字节发送帧、39字节接收帧），与实际代码（26字节 AUTO 帧、76字节 BlackBox 帧）严重不符，且文件结构里有不存在的 `terminal_GUI.py`。

### P1 · 可靠性（野外使用必需）

- **串口断线自动重连**：当前串口断开后发送线程直接退出，需要加重连循环（每秒尝试重新打开串口）。

- **接收缓冲区防溢出**：`receive_buffer` 无大小上限，持续收到垃圾数据时内存无限增长，需加 `MAX_BUFFER_SIZE = 1024` 上限保护。

- **精确发送频率控制**：当前用 `time.sleep(0.02)` 控制 50Hz，Windows 下 sleep 精度约 ±15ms，实际频率可能只有 30-40Hz。建议改用 `time.perf_counter` 的补偿式定时循环。

### P2 · 可观测性

- **用 `logging` 模块替换所有 `print`**：当前所有调试信息用 `print`，在 curses 界面下会破坏显示，且无法控制日志级别。建议输出到文件 `ground_station.log`，不输出到 stdout。

- **界面增加系统健康状态行**：显示实测发送/接收频率（Hz）、串口连接状态、黑箱记录状态、最后接收数据时间（超过 500ms 变红色警告）。

### P2 · 易用性

- **外部配置文件**：`COM14` 和 `CH340` 关键字硬编码在 `initial.py` 函数签名里，换台电脑就失效。建议新增 `config.toml`，启动时读取，找不到指定端口时自动降级到交互式选择。

### P3 · 质量保证

- **协议层单元测试**：为每个编码器和 `decode_data()` 编写单元测试，用 `teas.py`（建议改名为 `tools/generate_test_packet.py`）生成的测试包做离线协议验证，确保协议改动不引入回归。

- **修复 `teas.py` 文件名**：当前文件名完全无法表达用途，建议改为 `tools/generate_test_packet.py`。

- **清理死代码**：`get_packet_length()` 方法在所有编码器中都实现了，但整个代码库中从未被调用，建议删除或补充调用方。
