"""
Blackbox CSV analysis pipeline.

The first version deliberately uses only the Python standard library so it can
run on the ground-station laptop without installing heavy scientific packages.
MATLAB can consume the generated JSON for richer plotting.
"""

from __future__ import annotations

import csv
import json
import math
import os
import statistics
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_LOG_DIR = ROOT_DIR / "blackbox_logs"
DEFAULT_REPORT_DIR = ROOT_DIR / "analysis_reports"
MATLAB_SCRIPT = ROOT_DIR / "matlab" / "auto_blackbox_report.m"

NUMERIC_COLUMNS = [
    "packet_timestamp",
    "packet_timestamp2",
    "statemachine",
    "angle_roll",
    "angle_pitch",
    "angle_yaw",
    "gyro_x",
    "gyro_y",
    "gyro_z",
    "acc_x",
    "acc_y",
    "acc_z",
    "torque_x",
    "torque_y",
    "torque_z",
    "rudder1",
    "rudder2",
    "rudder3",
    "rudder4",
]


def latest_blackbox_csv(log_dir: Path = DEFAULT_LOG_DIR) -> Optional[Path]:
    files = sorted(log_dir.glob("blackbox_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    fallback = None
    for file in files:
        if file.stat().st_size > 0:
            fallback = fallback or file
        if file.stat().st_size > 512:
            return file
    return fallback


def _to_float(value: str) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_blackbox_csv(csv_path: Path) -> List[Dict[str, float]]:
    rows: List[Dict[str, float]] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            row: Dict[str, float] = {}
            valid = True
            for name in NUMERIC_COLUMNS:
                value = _to_float(raw.get(name, ""))
                if value is None:
                    valid = False
                    break
                row[name] = value
            if valid:
                rows.append(row)
    return rows


def _series(rows: Sequence[Dict[str, float]], key: str) -> List[float]:
    return [row[key] for row in rows if key in row]


def _stats(values: Sequence[float]) -> Dict[str, float]:
    if not values:
        return {"min": 0.0, "max": 0.0, "mean": 0.0, "std": 0.0, "peak_abs": 0.0}
    return {
        "min": min(values),
        "max": max(values),
        "mean": statistics.fmean(values),
        "std": statistics.pstdev(values) if len(values) > 1 else 0.0,
        "peak_abs": max(abs(v) for v in values),
    }


def _corr(a: Sequence[float], b: Sequence[float]) -> float:
    n = min(len(a), len(b))
    if n < 3:
        return 0.0
    aa = list(a[:n])
    bb = list(b[:n])
    mean_a = statistics.fmean(aa)
    mean_b = statistics.fmean(bb)
    da = [x - mean_a for x in aa]
    db = [x - mean_b for x in bb]
    denom = math.sqrt(sum(x * x for x in da) * sum(x * x for x in db))
    if denom <= 1e-12:
        return 0.0
    return sum(x * y for x, y in zip(da, db)) / denom


def _lag_corr(a: Sequence[float], b: Sequence[float], max_lag: int = 30) -> Dict[str, float]:
    best = {"lag_samples": 0, "correlation": _corr(a, b)}
    for lag in range(-max_lag, max_lag + 1):
        if lag < 0:
            ca, cb = a[-lag:], b[: len(b) + lag]
        elif lag > 0:
            ca, cb = a[: len(a) - lag], b[lag:]
        else:
            ca, cb = a, b
        c = _corr(ca, cb)
        if abs(c) > abs(best["correlation"]):
            best = {"lag_samples": lag, "correlation": c}
    return best


def _estimate_sample_rate(rows: Sequence[Dict[str, float]]) -> float:
    timestamps = _series(rows, "packet_timestamp2") or _series(rows, "packet_timestamp")
    diffs = [b - a for a, b in zip(timestamps, timestamps[1:]) if b > a]
    if not diffs:
        return 0.0
    median_diff = statistics.median(diffs)
    if median_diff <= 0:
        return 0.0
    # Firmware timestamps are milliseconds in current logs.
    return 1000.0 / median_diff


def _dft_peaks(values: Sequence[float], sample_rate_hz: float, max_points: int = 256) -> List[Dict[str, float]]:
    n = min(len(values), max_points)
    if n < 8 or sample_rate_hz <= 0:
        return []
    data = list(values[:n])
    mean = statistics.fmean(data)
    data = [x - mean for x in data]
    peaks: List[Tuple[float, float]] = []
    for k in range(1, n // 2):
        real = 0.0
        imag = 0.0
        for idx, value in enumerate(data):
            angle = -2.0 * math.pi * k * idx / n
            real += value * math.cos(angle)
            imag += value * math.sin(angle)
        amp = math.sqrt(real * real + imag * imag) / n
        freq = sample_rate_hz * k / n
        peaks.append((amp, freq))
    peaks.sort(reverse=True)
    return [{"frequency_hz": freq, "amplitude": amp} for amp, freq in peaks[:5]]


def _downsample(rows: Sequence[Dict[str, float]], keys: Iterable[str], max_points: int = 240) -> List[Dict[str, float]]:
    if not rows:
        return []
    step = max(1, math.ceil(len(rows) / max_points))
    sampled = []
    for row in rows[::step]:
        point = {key: row[key] for key in keys if key in row}
        sampled.append(point)
    return sampled


def generate_report(csv_path: Path, report_dir: Path = DEFAULT_REPORT_DIR) -> Dict[str, object]:
    csv_path = Path(csv_path).resolve()
    rows = load_blackbox_csv(csv_path)
    report_dir.mkdir(parents=True, exist_ok=True)
    sample_rate_hz = _estimate_sample_rate(rows)

    derived = {
        "front_diff": [row["rudder1"] - row["rudder2"] for row in rows],
        "back_diff": [row["rudder3"] - row["rudder4"] for row in rows],
        "front_sum": [row["rudder1"] + row["rudder2"] for row in rows],
        "back_sum": [row["rudder3"] + row["rudder4"] for row in rows],
    }

    axis_pairs = {
        "roll_vs_front_diff": (derived["front_diff"], _series(rows, "gyro_x")),
        "roll_vs_back_diff": (derived["back_diff"], _series(rows, "gyro_x")),
        "pitch_vs_front_sum": (derived["front_sum"], _series(rows, "gyro_y")),
        "pitch_vs_back_sum": (derived["back_sum"], _series(rows, "gyro_y")),
        "yaw_vs_front_diff": (derived["front_diff"], _series(rows, "gyro_z")),
        "yaw_vs_back_diff": (derived["back_diff"], _series(rows, "gyro_z")),
    }

    correlations = {
        name: {
            "zero_lag": _corr(input_signal, output_signal),
            "best_lag": _lag_corr(input_signal, output_signal),
        }
        for name, (input_signal, output_signal) in axis_pairs.items()
    }

    stats_keys = [
        "angle_roll",
        "angle_pitch",
        "angle_yaw",
        "gyro_x",
        "gyro_y",
        "gyro_z",
        "acc_x",
        "acc_y",
        "acc_z",
        "rudder1",
        "rudder2",
        "rudder3",
        "rudder4",
    ]
    state_distribution: Dict[str, int] = {}
    for state in _series(rows, "statemachine"):
        key = str(int(state))
        state_distribution[key] = state_distribution.get(key, 0) + 1

    report = {
        "schema_version": 1,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "source_csv": str(csv_path),
        "summary": {
            "row_count": len(rows),
            "sample_rate_hz": sample_rate_hz,
            "duration_s": (len(rows) / sample_rate_hz) if sample_rate_hz > 0 else 0.0,
            "state_distribution": state_distribution,
        },
        "stats": {key: _stats(_series(rows, key)) for key in stats_keys},
        "correlations": correlations,
        "fft_peaks": {
            "gyro_x": _dft_peaks(_series(rows, "gyro_x"), sample_rate_hz),
            "gyro_y": _dft_peaks(_series(rows, "gyro_y"), sample_rate_hz),
            "gyro_z": _dft_peaks(_series(rows, "gyro_z"), sample_rate_hz),
        },
        "preview": _downsample(
            rows,
            [
                "packet_timestamp",
                "angle_roll",
                "angle_pitch",
                "angle_yaw",
                "gyro_x",
                "gyro_y",
                "gyro_z",
                "rudder1",
                "rudder2",
                "rudder3",
                "rudder4",
            ],
        ),
    }

    safe_name = csv_path.stem.replace(" ", "_")
    report_path = report_dir / f"{safe_name}_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_index(report_dir)
    report["report_path"] = str(report_path)
    return report


def _write_index(report_dir: Path) -> None:
    reports = []
    for path in sorted(report_dir.glob("*_report.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            reports.append(
                {
                    "path": str(path),
                    "source_csv": payload.get("source_csv"),
                    "created_at": payload.get("created_at"),
                    "row_count": payload.get("summary", {}).get("row_count"),
                }
            )
        except Exception:
            continue
    (report_dir / "index.json").write_text(json.dumps({"reports": reports}, ensure_ascii=False, indent=2), encoding="utf-8")


def list_reports(report_dir: Path = DEFAULT_REPORT_DIR) -> Dict[str, object]:
    if not report_dir.exists():
        return {"reports": []}
    index = report_dir / "index.json"
    if not index.exists():
        _write_index(report_dir)
    return json.loads(index.read_text(encoding="utf-8"))


def maybe_launch_matlab(csv_path: Path, report_path: Path) -> Dict[str, object]:
    matlab_executable = os.environ.get("MATLAB_EXECUTABLE", "matlab")
    if not MATLAB_SCRIPT.exists():
        return {"enabled": False, "reason": f"MATLAB script not found: {MATLAB_SCRIPT}"}
    if os.environ.get("ENABLE_MATLAB_REPORT", "0") != "1":
        return {"enabled": False, "reason": "set ENABLE_MATLAB_REPORT=1 to launch MATLAB"}

    csv_arg = str(Path(csv_path).resolve()).replace("\\", "/")
    report_arg = str(Path(report_path).resolve()).replace("\\", "/")
    command = [
        matlab_executable,
        "-batch",
        f"auto_blackbox_report('{csv_arg}','{report_arg}')",
    ]
    try:
        completed = subprocess.run(command, cwd=str(ROOT_DIR), capture_output=True, text=True, timeout=120)
        return {
            "enabled": True,
            "returncode": completed.returncode,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
        }
    except Exception as exc:
        return {"enabled": True, "error": str(exc)}


def run_analysis(csv_path: Optional[str] = None) -> Dict[str, object]:
    selected = Path(csv_path).resolve() if csv_path else latest_blackbox_csv()
    if selected is None:
        raise FileNotFoundError("No blackbox CSV found.")
    report = generate_report(selected)
    report_path = Path(str(report["report_path"]))
    report["matlab"] = maybe_launch_matlab(selected, report_path)
    return report


if __name__ == "__main__":
    print(json.dumps(run_analysis(), ensure_ascii=False, indent=2))
