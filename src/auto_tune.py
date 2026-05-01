"""
自动调参控制器

通过修改共享 ProtocolData 并复用现有 UART_send 线程，在地面站内部完成
"一键" 调整舵机和前馈参数。

当前版本：
- 常用目标：舵机 + 前馈
- 参数来源：项目根目录下的 servo_params.json / feedforward_params.json
- 安全策略：
  - 操作前后切换到 STOP 状态，关闭总开关和风扇
  - 仅通过 ProtocolData / 状态机，不直接操作串口

后续可以按同样模式扩展 PID / Jacobian。
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import List, Optional

from protocol import ProtocolData, MainState, SubState


class AutoTuner:
    """自动调参控制器

    通过修改 shared_data 并依赖现有 UART_send 周期发送，完成一键调参。
    """

    def __init__(self, shared_data: ProtocolData, hold_time: float = 1.0) -> None:
        self.data = shared_data
        # 在 TUNING 子模式下保持的时间，单位秒
        self.hold_time = max(0.2, float(hold_time))

        base_dir = Path(__file__).resolve().parent.parent
        self.servo_file = base_dir / "servo_params.json"
        self.feedforward_file = base_dir / "feedforward_params.json"
        self.pid_file = base_dir / "pid_params.json"
        self.jacobian_file = base_dir / "jacobian_params.json"
        self.surface_limit_file = base_dir / "surface_limit_params.json"

    # ==================== 公共入口 ====================

    def apply_servo_and_feedforward_from_files(self) -> None:
        """从 JSON 文件读取舵机 / 前馈目标值，并依次写入飞控。

        顺序：
        1. STOP → TUNING+SERVO，写入 servo_angles
        2. STOP → TUNING+FEEDFORWARD，写入 feedforward_values
        """
        servo_target = self._load_servo_target()
        ff_target = self._load_feedforward_target()

        if servo_target is None and ff_target is None:
            print("自动调参: 未找到有效的舵机或前馈配置，已取消")
            return

        if servo_target is not None:
            self._apply_servo_target(servo_target)

        if ff_target is not None:
            self._apply_feedforward_target(ff_target)

    def apply_pid_from_file(self) -> None:
        """从 JSON 文件读取 PID 参数矩阵，并依次写入 PID 各组。"""
        pid_target = self._load_pid_target()

        if pid_target is None:
            print("自动调参: 未找到有效的PID配置，已取消")
            return

        self._apply_pid_target(pid_target)

    def apply_jacobian_from_file(self) -> None:
        """从 JSON 文件读取 Jacobian 矩阵，并写入飞控。"""
        jacobian_target = self._load_jacobian_target()

        if jacobian_target is None:
            print("自动调参: 未找到有效的Jacobian配置，已取消")
            return

        self._apply_jacobian_target(jacobian_target)

    def apply_surface_limit_from_file(self) -> None:
        """从 JSON 文件读取翼面限幅+pitch前馈目标值，并写入飞控。"""
        surface_limit_target = self._load_surface_limit_target()

        if surface_limit_target is None:
            print("自动调参: 未找到有效的翼面限幅配置，已取消")
            return

        self._apply_surface_limit_target(surface_limit_target)

    # ==================== 内部步骤 ====================

    def _ensure_safe_stop(self) -> None:
        """将主状态切到 STOP，并关闭总开关与风扇。

        仅通过 ProtocolData.set_main_state 操作，不直接写 main_state，
        以保证符合状态转换规则。
        """
        if self.data.set_main_state(MainState.STOP):
            self.data.main_switch = 0
            self.data.fan_speed = 0
            # 不强制改舵机角度，避免覆盖现场手动姿态
            time.sleep(0.2)
        else:
            # 理论上不会失败，若失败仅提示
            print("自动调参: 无法切换到 STOP 状态")

    def _switch_to_tuning_substate(self, sub_state: SubState) -> bool:
        """从 STOP 切换到 TUNING + 指定子状态。

        返回是否切换成功。
        """
        self._ensure_safe_stop()

        if not self.data.set_main_state(MainState.TUNING):
            print("自动调参: 无法切换到 TUNING 模式")
            return False

        # 只在 TUNING 下允许切子状态
        self.data.set_sub_state(sub_state)
        time.sleep(0.1)
        return True

    def _back_to_stop(self) -> None:
        """从任意状态安全返回 STOP。"""
        if self.data.set_main_state(MainState.STOP):
            self.data.main_switch = 0
            self.data.fan_speed = 0
            time.sleep(0.2)

    def _apply_servo_target(self, target: List[float]) -> None:
        """写入舵机目标值。"""
        if len(target) != 4:
            print("自动调参: 舵机目标长度必须为 4，已忽略")
            return

        if not self._switch_to_tuning_substate(SubState.SERVO):
            return

        self.data.servo_angles = [float(v) for v in target]
        print(f"自动调参: 已应用舵机目标 {self.data.servo_angles}")

        # 在 SERVO 调参模式下保持一段时间，让 UART_send 持续发送
        time.sleep(self.hold_time)
        self._back_to_stop()

    def _apply_feedforward_target(self, target: List[float]) -> None:
        """写入前馈目标值。"""
        if len(target) != 4:
            print("自动调参: 前馈目标长度必须为 4，已忽略")
            return

        if not self._switch_to_tuning_substate(SubState.FEEDFORWARD):
            return

        self.data.feedforward_values = [float(v) for v in target]
        print(f"自动调参: 已应用前馈目标 {self.data.feedforward_values}")

        time.sleep(self.hold_time)
        self._back_to_stop()

    def _apply_pid_target(self, target: List[List[float]]) -> None:
        """写入 PID 参数矩阵，并按组发送。"""
        pid_rows = len(self.data.pid_param)
        pid_cols = len(self.data.pid_param[0]) if pid_rows > 0 else 0

        if pid_rows == 0 or pid_cols == 0:
            print("自动调参: 当前PID参数维度非法，已忽略")
            return

        if len(target) != pid_rows or any(len(row) != pid_cols for row in target):
            print(f"自动调参: PID目标维度应为{pid_rows}x{pid_cols}，已忽略")
            return

        if not self._switch_to_tuning_substate(SubState.PID):
            return

        self.data.pid_param = [[float(v) for v in row] for row in target]
        print("自动调参: 已加载PID目标矩阵，开始逐组下发")

        # 仿照手动 Enter PID 组的行为，逐组切换发送目标。
        for pid_index in range(pid_rows):
            self.data.selected_pid = pid_index
            self.data.pid_tuning_state = pid_index
            print(f"自动调参: 正在下发PID组 {pid_index}")
            time.sleep(self.hold_time)

        # 结束时回到"不改"状态，避免持续占用PID组切换编码。
        self.data.pid_tuning_state = -1
        self._back_to_stop()

    def _apply_jacobian_target(self, target: List[List[float]]) -> None:
        """写入 Jacobian 矩阵 (3x4)。"""
        if len(target) != 3 or any(len(row) != 4 for row in target):
            print("自动调参: Jacobian目标维度必须为3x4，已忽略")
            return

        if not self._switch_to_tuning_substate(SubState.JACOBIAN):
            return

        self.data.jacobian_matrix = [list(row) for row in target]
        print("自动调参: 已应用Jacobian目标矩阵")

        time.sleep(self.hold_time)
        self._back_to_stop()

    def _apply_surface_limit_target(self, target: dict) -> None:
        """写入翼面限幅+pitch前馈目标值。"""
        surface_angle_min_d = target.get("surface_angle_min_d")
        surface_angle_max_d = target.get("surface_angle_max_d")
        pitch_need = target.get("pitch_need")

        if not (
            isinstance(surface_angle_min_d, list)
            and len(surface_angle_min_d) == 4
            and isinstance(surface_angle_max_d, list)
            and len(surface_angle_max_d) == 4
        ):
            print("自动调参: 翼面限幅目标维度必须各为4，已忽略")
            return

        if not self._switch_to_tuning_substate(SubState.SURFACE_LIMIT):
            return

        self.data.surface_angle_min_d = [float(v) for v in surface_angle_min_d]
        self.data.surface_angle_max_d = [float(v) for v in surface_angle_max_d]
        if pitch_need is not None:
            self.data.pitch_need = float(pitch_need)

        print(
            f"自动调参: 已应用翼面限幅 min={self.data.surface_angle_min_d} "
            f"max={self.data.surface_angle_max_d} pitch_need={self.data.pitch_need}"
        )

        time.sleep(self.hold_time)
        self._back_to_stop()

    # ==================== 配置加载 ====================

    def _load_servo_target(self) -> Optional[List[float]]:
        if not self.servo_file.exists():
            return None
        try:
            data = json.loads(self.servo_file.read_text(encoding="utf-8"))
            vals = data.get("servo_angles")
            if isinstance(vals, list) and len(vals) == 4:
                return [float(v) for v in vals]
        except Exception as e:
            print(f"自动调参: 读取舵机配置失败: {e}")
        return None

    def _load_surface_limit_target(self) -> Optional[dict]:
        if not self.surface_limit_file.exists():
            return None
        try:
            data = json.loads(self.surface_limit_file.read_text(encoding="utf-8"))
            min_d = data.get("surface_angle_min_d")
            max_d = data.get("surface_angle_max_d")
            pitch = data.get("pitch_need")
            if (
                isinstance(min_d, list)
                and len(min_d) == 4
                and isinstance(max_d, list)
                and len(max_d) == 4
            ):
                return {
                    "surface_angle_min_d": [float(v) for v in min_d],
                    "surface_angle_max_d": [float(v) for v in max_d],
                    "pitch_need": float(pitch) if pitch is not None else 0.0,
                }
        except Exception as e:
            print(f"自动调参: 读取翼面限幅配置失败: {e}")
        return None

    def _load_feedforward_target(self) -> Optional[List[float]]:
        if not self.feedforward_file.exists():
            return None
        try:
            data = json.loads(self.feedforward_file.read_text(encoding="utf-8"))
            vals = data.get("feedforward_values")
            if isinstance(vals, list) and len(vals) == 4:
                return [float(v) for v in vals]
        except Exception as e:
            print(f"自动调参: 读取前馈配置失败: {e}")
        return None

    def _load_pid_target(self) -> Optional[List[List[float]]]:
        if not self.pid_file.exists():
            return None
        try:
            data = json.loads(self.pid_file.read_text(encoding="utf-8"))
            vals = data.get("pid_param")
            if isinstance(vals, list) and vals:
                parsed: List[List[float]] = []
                for row in vals:
                    if not isinstance(row, list):
                        return None
                    parsed.append([float(v) for v in row])
                return parsed
        except Exception as e:
            print(f"自动调参: 读取PID配置失败: {e}")
        return None

    def _load_jacobian_target(self) -> Optional[List[List[float]]]:
        if not self.jacobian_file.exists():
            return None
        try:
            data = json.loads(self.jacobian_file.read_text(encoding="utf-8"))
            vals = data.get("jacobian_matrix")
            if isinstance(vals, list) and len(vals) == 3:
                parsed: List[List[float]] = []
                for row in vals:
                    if not isinstance(row, list) or len(row) != 4:
                        return None
                    parsed.append([float(v) for v in row])
                return parsed
        except Exception as e:
            print(f"自动调参: 读取Jacobian配置失败: {e}")
        return None
