# AGENTS.md

## Project Role

This repository is the STM32F411 flight-control firmware for the RoboMaster guided dart body.
注意，这些硬编码的路径仅在mardio电脑上有用，这是一个多人协作的项目，在开始前务必询问用户目录在哪里
Related workspaces:
- Flight controller: `T:\ROBOMASTER_2\Project\missilev1\missilev1_start`
- Ground station: `T:\ROBOMASTER_2\Project\Aircraft_carrier_tower`
- OpenMV vision: `T:\ROBOMASTER_2\Project\openmv2\openmv_learn`
- MATLAB/data tools: `T:\ROBOMASTER_2\matlab`

## Build And Debug

- Primary build system: CMake + Ninja.
- Configure/build from this workspace:
  - `cmake --preset Debug`
  - `cmake --build --preset Debug --parallel 4`
- Output ELF: `build/Debug/missilev1.elf`
- Target: STM32F411xE, Cortex-M4F, hard-float.
- Linker script: `STM32F411XX_FLASH.ld`
- Startup: `startup_stm32f411xe.s`
- VS Code ST-LINK config: `.vscode/launch.json`
- CLI flash example:
  - `STM32_Programmer_CLI -c port=SWD mode=UR freq=1000 -w build\Debug\missilev1.elf -v -rst`
- CLI attach pattern used successfully:
  - Start OpenOCD with `openocd -f interface/stlink.cfg -f target/stm32f4x.cfg`
  - Attach GDB to `:3333`

## Main Firmware Structure

- `Core/`: STM32CubeMX HAL init, FreeRTOS entry, peripherals.
- `my_general/initial.c`: creates application FreeRTOS tasks and shared semaphore.
- `my_task/MasterTask.c`: high-level mode/state machine, telemetry, OpenMV send, Flash-save command handling.
- `my_task/ReceiveTask.c`: UART1 ground-station receive, CRC validation, parameter packet parsing; UART2 OpenMV receive.
- `my_task/ControlTask.c`: servo/fan output, PID control loops, Jacobian-based control allocation, navigation guidance.
- `my_task/IMUTask.c`: IMU readout and pose update.
- `my_BSP/Flash/param_flash.c`: persistent parameter snapshot in internal Flash Sector 6/7.
- `my_BSP/RAM/blackboxRAM.c`: RAM BlackBox logging path.
- `my_BSP/Flash/blackbox.c`: intentionally stubbed; Flash BlackBox no longer owns Sector 6/7.

## FreeRTOS Tasks

Created in `my_general/initial.c`:
- `ReceiveTask`, priority 7, stack 128
- `MasterTask`, priority 6, stack 256
- `ControlTask`, priority 5, stack 512
- `IMUTask`, priority 4, stack 256

Important shared objects:
- `State_machine` and `AUTO_state_machine` in `MasterTask.c`
- `Receive_tower_normal_data` in `MasterTask.c`
- `Contrl_data` and `Navigation_data` in `ControlTask.c`
- `IMU_data` in `IMUTask.c`
- `receive_enevt_semaphore` for deferred parameter application in `ReceiveTask`

## Ground Station Protocol

Frame directions:
- Ground station to flight controller: header `0xAA`, tail `0xBB`
- Flight controller to ground station: header `0xCC`, tail `0xDD`

Mode/command bytes in `my_task/MasterTask.h`:
- `STOP = 0x00`
- `AUTO_CONTRL = 0x01`
- `TOWER_CONTRL = 0x02`
- `RUDDER_DATA_CHANGE = 0xA1`
- `PID_DATA_CHANGE = 0xA2`
- `JACOBIAN_DATA_CHANGE = 0xA3`
- `SURFACE_DATA_CHANGE = 0xA4`
- `SAVE_DATA = 0xA5`
- `SAVE_DATA_END = 0xA6`
- `DATA = 0xB1`

CRC:
- Firmware uses STM32 hardware CRC and keeps the low byte as CRC8-like checksum.
- Python ground station mirrors this in `src/crc_calculator.py`.

Save command:
- Ground station sends `AA A5 CRC BB`.
- Flight controller saves current effective parameters, then sends 16-byte ACK:
  - `[0]=0xCC`, `[1]=0xA6`, `[2]=status`, `[14]=crc`, `[15]=0xDD`
- Ground station automatic test script:
  - `T:\ROBOMASTER_2\Project\Aircraft_carrier_tower\src\send_save_command.py --port COM16 --timeout 10`
- Flight-controller-local test helper:
  - `tools/send_save_command.py --port COM16 --timeout 10`

## Flash Parameter Persistence

Internal Flash ownership:
- Sector 6: `0x08040000`
- Sector 7: `0x08060000`
- These sectors are reserved for parameter snapshots.
- Do not re-enable Flash BlackBox on Sector 6/7.

Saved payload:
- Servo neutral angles
- Surface feedforward values
- 3 pose PID groups
- 3 torque PID groups
- 3x4 Jacobian matrix
- Metadata: magic, version, size, crc, sequence

Boot behavior:
- `ControlInit()` initializes defaults first.
- `ParamFlash_LoadToControl()` then overlays valid Flash data.
- Jacobian transpose and pseudo-inverse are recalculated after load.

Safety:
- Flash erase/program stalls execution from internal Flash on F411.
- Save is allowed only outside `AUTO_CONTRL` and `TOWER_CONTRL`; busy status is returned otherwise.
- Do not call Flash erase/program from ISR.

Debug variable to inspect:
- `g_flash_verify_result.sample_id`
- `g_flash_verify_result.write_ret`
- `g_flash_verify_result.verify_ok`
- `g_flash_verify_result.load_ok`
- `g_flash_verify_result.status`

## Coding Notes

- Prefer DMA UART APIs in firmware. Do not add business-code calls to blocking `HAL_UART_Transmit`.
- Flash operations are the only accepted temporary blocking path, and only in safe states.
- Keep code changes scoped; generated HAL/CubeMX files should be touched only when necessary.
- Some comments/files are mojibake in the current checkout; avoid mass re-encoding unless explicitly requested.
- There are existing dirty/generated files such as `gdbClient_log.txt`, JSON tuning files, and `__pycache__` in the ground station. Do not clean them unless asked.

## Known Hardware Links From Last Validation

- ST-LINK was detected as STM32F411xC/E, 512 KB Flash, target voltage about 3.26 V.
- Ground-station USB-TTL was on `COM16`.
- Last validated save round trip:
  - TX `aa a5 68 bb`
  - RX `cc a6 00 00 00 00 00 00 00 00 00 00 00 00 85 dd`
