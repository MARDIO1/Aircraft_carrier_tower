"""
FastAPI bridge for the Next.js ground-station dashboard.

Run with:
    uv run python src/web_server.py
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from analysis_pipeline import list_reports, run_analysis
from feishu_sync import feishu_research_checklist, write_local_feishu_draft
from initial import Initializer
from params_store import load_into, load_params, save_from
from protocol import MainState, ProtocolData, SubState
from UART_receive import UARTReceiver
from UART_send import UARTSender
from web_contract import runtime_snapshot


class ControlPatch(BaseModel):
    main_state: Optional[str] = None
    sub_state: Optional[str] = None
    main_switch: Optional[int] = None
    fan_speed: Optional[int] = None
    servo_angles: Optional[list[float]] = None
    feedforward_values: Optional[list[float]] = None
    selected_pid: Optional[int] = None
    selected_param: Optional[int] = None
    pid_tuning_state: Optional[int] = None
    pid_param: Optional[list[list[float]]] = None
    jacobian_matrix: Optional[list[list[float]]] = None
    nav_row: Optional[int] = None
    nav_col: Optional[int] = None
    nav_confirm: Optional[bool] = None
    request_save_to_flash: bool = False


class ConnectRequest(BaseModel):
    com_port: Optional[str] = None
    auto_keyword: str = "CH340"


class AnalysisRequest(BaseModel):
    csv_path: Optional[str] = None
    write_feishu_draft: bool = Field(default=True)


class RuntimeController:
    def __init__(self) -> None:
        self.shared_data = ProtocolData()
        load_into(self.shared_data)
        self.initializer = Initializer()
        self.uart_sender: Optional[UARTSender] = None
        self.uart_receiver: Optional[UARTReceiver] = None
        self.lock = Lock()
        self.last_analysis: Dict[str, Any] = {"last_run_at": None, "last_report_path": None, "last_error": None}

    def connect(self, com_port: Optional[str] = None, auto_keyword: str = "CH340") -> Dict[str, Any]:
        with self.lock:
            if self.initializer.serial_port and self.initializer.serial_port.is_open:
                return self.serial_status()

            ok = self.initializer.initialize_serial(com_port=com_port, auto_keyword=auto_keyword)
            if not ok:
                return self.serial_status(error="serial initialization failed")

            self.uart_sender = UARTSender(self.initializer.serial_port, self.shared_data)
            self.uart_receiver = UARTReceiver(self.initializer.serial_port, self.shared_data)
            self.uart_sender.start_sending()
            self.uart_receiver.start_receiving()
            return self.serial_status()

    def disconnect(self) -> Dict[str, Any]:
        with self.lock:
            if self.uart_sender:
                self.uart_sender.stop_sending()
                self.uart_sender = None
            if self.uart_receiver:
                self.uart_receiver.stop_receiving()
                self.uart_receiver = None
            self.initializer.close_serial()
            return self.serial_status()

    def serial_status(self, error: Optional[str] = None) -> Dict[str, Any]:
        port = self.initializer.serial_port
        return {
            "connected": bool(port and port.is_open),
            "com_port": self.initializer.com_port,
            "baud_rate": self.initializer.baud_rate,
            "error": error,
        }

    def snapshot(self) -> Dict[str, Any]:
        send_status = {
            "running": bool(self.uart_sender and self.uart_sender.running),
            "last_sent": self.uart_sender.last_sent_data if self.uart_sender else None,
            "hex": self.uart_sender.get_hex_data() if self.uart_sender else None,
        }
        receive_status = self.uart_receiver.get_receive_status() if self.uart_receiver else {
            "running": False,
            "receive_count": 0,
            "error_count": 0,
            "last_receive_time": "never",
            "buffer_size": 0,
        }
        if self.uart_receiver:
            receive_status["blackbox_logging"] = self.uart_receiver.get_blackbox_logging_status()

        return runtime_snapshot(
            self.shared_data,
            serial_status=self.serial_status(),
            send_status=send_status,
            receive_status=receive_status,
            analysis_status=self.last_analysis,
        )

    def apply_control_patch(self, patch: ControlPatch) -> Dict[str, Any]:
        with self.shared_data._lock:
            if patch.main_state is not None:
                try:
                    target = MainState[patch.main_state]
                except KeyError as exc:
                    raise ValueError(f"Unknown main_state: {patch.main_state}") from exc
                if not self.shared_data.set_main_state(target):
                    raise ValueError(f"Rejected state transition to {patch.main_state}")

            if patch.sub_state is not None:
                try:
                    self.shared_data.set_sub_state(SubState[patch.sub_state])
                except KeyError as exc:
                    raise ValueError(f"Unknown sub_state: {patch.sub_state}") from exc

            if patch.main_switch is not None:
                self.shared_data.main_switch = int(patch.main_switch)
            if patch.fan_speed is not None:
                self.shared_data.fan_speed = int(patch.fan_speed)
            if patch.servo_angles is not None:
                self.shared_data.servo_angles = _bounded_float_list(patch.servo_angles, 4)
            if patch.feedforward_values is not None:
                self.shared_data.feedforward_values = _bounded_float_list(patch.feedforward_values, 4)
            if patch.selected_pid is not None:
                self.shared_data.selected_pid = _clamp(int(patch.selected_pid), 0, len(self.shared_data.pid_param) - 1)
            if patch.selected_param is not None:
                self.shared_data.selected_param = _clamp(int(patch.selected_param), 0, 5)
            if patch.pid_tuning_state is not None:
                self.shared_data.pid_tuning_state = _clamp(int(patch.pid_tuning_state), -1, len(self.shared_data.pid_param) - 1)
            if patch.pid_param is not None:
                self.shared_data.pid_param = _matrix(patch.pid_param, len(self.shared_data.pid_param), 6)
            if patch.jacobian_matrix is not None:
                self.shared_data.jacobian_matrix = _matrix(patch.jacobian_matrix, 3, 4)
            if patch.nav_row is not None:
                self.shared_data.nav_row = max(0, int(patch.nav_row))
            if patch.nav_col is not None:
                self.shared_data.nav_col = max(0, int(patch.nav_col))
            if patch.nav_confirm is not None:
                self.shared_data.nav_confirm = bool(patch.nav_confirm)
            if patch.request_save_to_flash:
                self.shared_data.request_save_to_flash()
        return self.snapshot()

    def run_analysis(self, request: AnalysisRequest) -> Dict[str, Any]:
        try:
            report = run_analysis(request.csv_path)
            if request.write_feishu_draft:
                draft_path = write_local_feishu_draft(report)
                report["feishu_draft_path"] = str(draft_path)
            self.last_analysis = {
                "last_run_at": time.time(),
                "last_report_path": report.get("report_path"),
                "last_error": None,
            }
            return report
        except Exception as exc:
            self.last_analysis = {
                "last_run_at": time.time(),
                "last_report_path": None,
                "last_error": str(exc),
            }
            raise

    def read_report(self, report_path: str) -> Dict[str, Any]:
        path = Path(report_path).resolve()
        report_dir = Path(__file__).resolve().parents[1] / "analysis_reports"
        if report_dir not in path.parents and path.parent != report_dir:
            raise ValueError("report path is outside analysis_reports")
        if not path.exists():
            raise FileNotFoundError(report_path)
        return json.loads(path.read_text(encoding="utf-8"))

    def load_json_params(self) -> Dict[str, Any]:
        loaded = load_into(self.shared_data)
        return {"loaded": loaded, "snapshot": self.snapshot()}

    def save_json_params(self) -> Dict[str, Any]:
        saved = save_from(self.shared_data)
        return {"saved": saved, "snapshot": self.snapshot()}


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(value, high))


def _bounded_float_list(values: list[float], length: int) -> list[float]:
    if len(values) != length:
        raise ValueError(f"Expected {length} values.")
    return [float(value) for value in values]


def _matrix(values: list[list[float]], rows: int, cols: int) -> list[list[float]]:
    if len(values) != rows or any(len(row) != cols for row in values):
        raise ValueError(f"Expected {rows}x{cols} matrix.")
    return [[float(value) for value in row] for row in values]


runtime = RuntimeController()
app = FastAPI(title="Aircraft Carrier Tower Web Bridge", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup() -> None:
    # Try auto-connect, but keep the dashboard usable if no serial device is present.
    runtime.connect()


@app.get("/api/health")
async def health() -> Dict[str, Any]:
    return {"ok": True, "snapshot_time": time.time()}


@app.get("/api/snapshot")
async def snapshot() -> Dict[str, Any]:
    return runtime.snapshot()


@app.get("/api/params")
async def params() -> Dict[str, Any]:
    return {"params": load_params()}


@app.post("/api/params/load")
async def params_load() -> Dict[str, Any]:
    return runtime.load_json_params()


@app.post("/api/params/save")
async def params_save() -> Dict[str, Any]:
    return runtime.save_json_params()


@app.post("/api/connect")
async def connect(request: ConnectRequest) -> Dict[str, Any]:
    return runtime.connect(request.com_port, request.auto_keyword)


@app.post("/api/disconnect")
async def disconnect() -> Dict[str, Any]:
    return runtime.disconnect()


@app.post("/api/control")
async def control(patch: ControlPatch) -> Dict[str, Any]:
    try:
        return runtime.apply_control_patch(patch)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/analysis/reports")
async def reports() -> Dict[str, Any]:
    return list_reports()


@app.get("/api/analysis/report")
async def report(path: str) -> Dict[str, Any]:
    try:
        return runtime.read_report(path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/analysis/run")
async def analysis_run(request: AnalysisRequest) -> Dict[str, Any]:
    try:
        return runtime.run_analysis(request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/feishu/research")
async def feishu_research() -> Dict[str, Any]:
    return {"available_connector": False, "checklist": feishu_research_checklist()}


@app.websocket("/ws")
async def websocket(ws: WebSocket) -> None:
    await ws.accept()
    try:
        while True:
            await ws.send_text(json.dumps(runtime.snapshot(), ensure_ascii=False))
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        return


if __name__ == "__main__":
    uvicorn.run("web_server:app", host="127.0.0.1", port=8000, reload=False)
