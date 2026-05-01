"""Apply tuning JSON files to ProtocolData through the normal UART sender loop."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

from protocol import MainState, ProtocolData, SubState


class AutoTuner:
    """Small helper used by both the TUI and Web backend.

    The tuner only mutates ProtocolData. UARTSender observes the same shared
    data and sends the selected tuning sub-packet at 50 Hz.
    """

    def __init__(self, shared_data: ProtocolData, hold_time: float = 1.0) -> None:
        self.data = shared_data
        self.hold_time = max(0.2, float(hold_time))

        base_dir = Path(__file__).resolve().parents[1]
        self.servo_file = base_dir / "servo_params.json"
        self.feedforward_file = base_dir / "feedforward_params.json"
        self.pid_file = base_dir / "pid_params.json"
        self.jacobian_file = base_dir / "jacobian_params.json"
        self.surface_limit_file = base_dir / "surface_limit_params.json"

    def apply_servo_and_feedforward_from_files(self) -> None:
        servo_target = self._load_float_list(self.servo_file, "servo_angles", 4)
        ff_target = self._load_float_list(self.feedforward_file, "feedforward_values", 4)

        if servo_target is not None:
            self._apply_servo_target(servo_target)
        if ff_target is not None:
            self._apply_feedforward_target(ff_target)

    def apply_pid_from_file(self) -> None:
        target = self._load_float_matrix(self.pid_file, "pid_param")
        if target is None:
            print("auto tune: no valid PID params found")
            return
        self._apply_pid_target(target)

    def apply_jacobian_from_file(self) -> None:
        target = self._load_float_matrix(self.jacobian_file, "jacobian_matrix")
        if target is None:
            print("auto tune: no valid Jacobian matrix found")
            return
        self._apply_jacobian_target(target)

    def apply_surface_limit_from_file(self) -> None:
        target = self._load_surface_limit_target()
        if target is None:
            print("auto tune: no valid surface limit params found")
            return
        self._apply_surface_limit_target(target)

    def _ensure_safe_stop(self) -> None:
        if self.data.set_main_state(MainState.STOP):
            self.data.main_switch = 0
            self.data.fan_speed = 0
            time.sleep(0.2)

    def _switch_to_tuning_substate(self, sub_state: SubState) -> bool:
        self._ensure_safe_stop()
        if not self.data.set_main_state(MainState.TUNING):
            print("auto tune: failed to enter TUNING")
            return False
        self.data.set_sub_state(sub_state)
        time.sleep(0.1)
        return True

    def _back_to_stop(self) -> None:
        if self.data.set_main_state(MainState.STOP):
            self.data.main_switch = 0
            self.data.fan_speed = 0
            self.data.pid_tuning_state = -1
            time.sleep(0.2)

    def _apply_servo_target(self, target: list[float]) -> None:
        if not self._switch_to_tuning_substate(SubState.SERVO):
            return
        with self.data._lock:
            self.data.servo_angles = [float(v) for v in target]
        time.sleep(self.hold_time)
        self._back_to_stop()

    def _apply_feedforward_target(self, target: list[float]) -> None:
        if not self._switch_to_tuning_substate(SubState.FEEDFORWARD):
            return
        with self.data._lock:
            self.data.feedforward_values = [float(v) for v in target]
        time.sleep(self.hold_time)
        self._back_to_stop()

    def _apply_pid_target(self, target: list[list[float]]) -> None:
        rows = len(self.data.pid_param)
        cols = len(self.data.pid_param[0]) if rows else 0
        if len(target) != rows or any(len(row) != cols for row in target):
            print(f"auto tune: PID shape must be {rows}x{cols}")
            return
        if not self._switch_to_tuning_substate(SubState.PID):
            return

        with self.data._lock:
            self.data.pid_param = [[float(v) for v in row] for row in target]

        for pid_index in range(rows):
            with self.data._lock:
                self.data.selected_pid = pid_index
                self.data.pid_tuning_state = pid_index
            time.sleep(self.hold_time)

        self._back_to_stop()

    def _apply_jacobian_target(self, target: list[list[float]]) -> None:
        if len(target) != 3 or any(len(row) != 4 for row in target):
            print("auto tune: Jacobian shape must be 3x4")
            return
        if not self._switch_to_tuning_substate(SubState.JACOBIAN):
            return
        with self.data._lock:
            self.data.jacobian_matrix = [[float(v) for v in row] for row in target]
        time.sleep(self.hold_time)
        self._back_to_stop()

    def _apply_surface_limit_target(self, target: dict[str, Any]) -> None:
        if not self._switch_to_tuning_substate(SubState.SURFACE_LIMIT):
            return
        with self.data._lock:
            self.data.surface_angle_min_d = [float(v) for v in target["surface_angle_min_d"]]
            self.data.surface_angle_max_d = [float(v) for v in target["surface_angle_max_d"]]
            self.data.pitch_need = float(target["pitch_need"])
        time.sleep(self.hold_time)
        self._back_to_stop()

    def _read_json(self, path: Path) -> dict[str, Any]:
        try:
            if not path.exists():
                return {}
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception as exc:
            print(f"auto tune: failed to read {path.name}: {exc}")
            return {}

    def _load_float_list(self, path: Path, key: str, length: int) -> Optional[list[float]]:
        values = self._read_json(path).get(key)
        if not isinstance(values, list) or len(values) != length:
            return None
        try:
            return [float(v) for v in values]
        except (TypeError, ValueError):
            return None

    def _load_float_matrix(self, path: Path, key: str) -> Optional[list[list[float]]]:
        values = self._read_json(path).get(key)
        if not isinstance(values, list) or not values:
            return None
        try:
            return [[float(v) for v in row] for row in values if isinstance(row, list)]
        except (TypeError, ValueError):
            return None

    def _load_surface_limit_target(self) -> Optional[dict[str, Any]]:
        data = self._read_json(self.surface_limit_file)
        min_d = data.get("surface_angle_min_d")
        max_d = data.get("surface_angle_max_d")
        pitch = data.get("pitch_need", 0.0)
        if not (isinstance(min_d, list) and isinstance(max_d, list)):
            return None
        if len(min_d) != 4 or len(max_d) != 4:
            return None
        try:
            return {
                "surface_angle_min_d": [float(v) for v in min_d],
                "surface_angle_max_d": [float(v) for v in max_d],
                "pitch_need": float(pitch),
            }
        except (TypeError, ValueError):
            return None
