"""
Web API data contract for the ground-station dashboard.

This module keeps the JSON shape in one place so the FastAPI backend,
Next.js frontend, MATLAB reports, and future Feishu sync all agree on names.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Dict, Optional


def _enum_name(value: Any) -> str:
    if isinstance(value, Enum):
        return value.name
    return str(value)


def _enum_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    return value


def protocol_snapshot(shared_data: Any) -> Dict[str, Any]:
    """Return a thread-safe JSON snapshot of ProtocolData."""
    with shared_data._lock:
        last_rx_age_s: Optional[float] = None
        if shared_data.last_received_time is not None:
            last_rx_age_s = max(0.0, time.time() - shared_data.last_received_time)

        return {
            "timestamp": time.time(),
            "state": {
                "main": _enum_name(shared_data.main_state),
                "main_value": _enum_value(shared_data.main_state),
                "sub": _enum_name(shared_data.sub_state),
                "sub_value": _enum_value(shared_data.sub_state),
                "nav_row": shared_data.nav_row,
                "nav_col": shared_data.nav_col,
                "nav_confirm": shared_data.nav_confirm,
            },
            "control": {
                "main_switch": shared_data.main_switch,
                "fan_speed": shared_data.fan_speed,
                "servo_angles": list(shared_data.servo_angles),
                "feedforward_values": list(shared_data.feedforward_values),
                "selected_pid": shared_data.selected_pid,
                "selected_param": shared_data.selected_param,
                "pid_tuning_state": shared_data.pid_tuning_state,
                "pid_param": [list(row) for row in shared_data.pid_param],
                "pid_name": list(shared_data.pid_name),
                "param_names": list(shared_data.param_names),
                "jacobian_matrix": [list(row) for row in shared_data.jacobian_matrix],
                "surface_angle_min_d": list(shared_data.surface_angle_min_d),
                "surface_angle_max_d": list(shared_data.surface_angle_max_d),
                "pitch_need": float(shared_data.pitch_need),
            },
            "blackbox": {
                "received": shared_data.blackbox_received,
                "timestamp": shared_data.blackbox_timestamp,
                "timestamp2": shared_data.blackbox_timestamp2,
                "statemachine": shared_data.blackbox_statemachine,
                "angle": list(shared_data.blackbox_angle),
                "gyro": list(shared_data.blackbox_gyro),
                "acc": list(shared_data.blackbox_acc),
                "torque": list(shared_data.blackbox_torque),
                "rudder": list(shared_data.blackbox_rudder),
                "last_rx_age_s": last_rx_age_s,
            },
            "flash": {
                "pending": shared_data.pending_save_to_flash,
                "ack_received": shared_data.save_flash_ack_received,
                "status": shared_data.save_flash_status,
                "last_time": shared_data.save_flash_last_time,
            },
        }


def runtime_snapshot(
    shared_data: Any,
    *,
    serial_status: Dict[str, Any],
    send_status: Dict[str, Any],
    receive_status: Dict[str, Any],
    analysis_status: Dict[str, Any],
    auto_tune_status: Dict[str, Any],
) -> Dict[str, Any]:
    snapshot = protocol_snapshot(shared_data)
    snapshot["runtime"] = {
        "serial": serial_status,
        "send": send_status,
        "receive": receive_status,
        "analysis": analysis_status,
        "auto_tune": auto_tune_status,
    }
    return snapshot
