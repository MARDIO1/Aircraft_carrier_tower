"""
Load and save the ground-station tuning JSON files.

The Web dashboard intentionally reuses the same JSON shapes as the terminal
controller: servo_params.json, feedforward_params.json, pid_params.json, and
jacobian_params.json.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict


ROOT_DIR = Path(__file__).resolve().parents[1]
PARAM_FILES = {
    "servo_angles": ROOT_DIR / "servo_params.json",
    "feedforward_values": ROOT_DIR / "feedforward_params.json",
    "pid_param": ROOT_DIR / "pid_params.json",
    "jacobian_matrix": ROOT_DIR / "jacobian_params.json",
}


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _float_list(values: Any, length: int) -> list[float] | None:
    if not isinstance(values, list) or len(values) != length:
        return None
    try:
        return [float(value) for value in values]
    except (TypeError, ValueError):
        return None


def _float_matrix(values: Any, rows: int, cols: int) -> list[list[float]] | None:
    if not isinstance(values, list) or len(values) != rows:
        return None
    matrix: list[list[float]] = []
    for row in values:
        parsed = _float_list(row, cols)
        if parsed is None:
            return None
        matrix.append(parsed)
    return matrix


def load_params() -> Dict[str, Any]:
    payload: Dict[str, Any] = {}

    servo = _float_list(_read_json(PARAM_FILES["servo_angles"]).get("servo_angles"), 4)
    if servo is not None:
        payload["servo_angles"] = servo

    feedforward = _float_list(_read_json(PARAM_FILES["feedforward_values"]).get("feedforward_values"), 4)
    if feedforward is not None:
        payload["feedforward_values"] = feedforward

    pid = _float_matrix(_read_json(PARAM_FILES["pid_param"]).get("pid_param"), 7, 6)
    if pid is not None:
        payload["pid_param"] = pid

    jacobian = _float_matrix(_read_json(PARAM_FILES["jacobian_matrix"]).get("jacobian_matrix"), 3, 4)
    if jacobian is not None:
        payload["jacobian_matrix"] = jacobian

    return payload


def apply_params(shared_data: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    with shared_data._lock:
        if "servo_angles" in params:
            shared_data.servo_angles = list(params["servo_angles"])
        if "feedforward_values" in params:
            shared_data.feedforward_values = list(params["feedforward_values"])
        if "pid_param" in params:
            shared_data.pid_param = [list(row) for row in params["pid_param"]]
        if "jacobian_matrix" in params:
            shared_data.jacobian_matrix = [list(row) for row in params["jacobian_matrix"]]
    return params


def load_into(shared_data: Any) -> Dict[str, Any]:
    return apply_params(shared_data, load_params())


def snapshot_params(shared_data: Any) -> Dict[str, Any]:
    with shared_data._lock:
        return {
            "servo_angles": list(shared_data.servo_angles),
            "feedforward_values": list(shared_data.feedforward_values),
            "pid_param": [list(row) for row in shared_data.pid_param],
            "jacobian_matrix": [list(row) for row in shared_data.jacobian_matrix],
        }


def save_from(shared_data: Any) -> Dict[str, Any]:
    params = snapshot_params(shared_data)
    saved_at = time.time()

    PARAM_FILES["servo_angles"].write_text(
        json.dumps({"servo_angles": params["servo_angles"], "saved_at": saved_at}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    PARAM_FILES["feedforward_values"].write_text(
        json.dumps({"feedforward_values": params["feedforward_values"], "saved_at": saved_at}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    PARAM_FILES["pid_param"].write_text(
        json.dumps({"pid_param": params["pid_param"], "saved_at": saved_at}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    PARAM_FILES["jacobian_matrix"].write_text(
        json.dumps({"jacobian_matrix": params["jacobian_matrix"], "saved_at": saved_at}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {"saved_at": saved_at, "files": {name: str(path) for name, path in PARAM_FILES.items()}, "params": params}
