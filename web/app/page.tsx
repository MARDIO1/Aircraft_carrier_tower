"use client";

import { useEffect, useRef, useState } from "react";

type Snapshot = Record<string, any>;
type PortInfo = { device: string; description: string; hwid?: string };

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const WS_BASE = API_BASE.replace(/^http/, "ws");
const MAIN_STATES = ["STOP", "TOWER", "AUTO", "TUNING", "DATA"] as const;
const PID_LABELS = ["att roll", "att pitch", "att yaw", "rate roll", "rate pitch", "rate yaw", "aux"];
const PID_COLS = ["kp", "ki", "kd", "pmax", "out max", "out min"];
const JACOBIAN_ROWS = ["L roll", "M pitch", "N yaw"];
const SURFACE_ROWS = ["min 1", "min 2", "min 3", "min 4", "max 1", "max 2", "max 3", "max 4", "pitch need"];
const SURFACE_COLS = ["value"];

function apiUrl(path: string) {
  return `${API_BASE}${path}`;
}

async function readJson(path: string, init?: RequestInit) {
  let res: Response;
  try {
    res = await fetch(apiUrl(path), {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new Error(`backend offline: ${API_BASE}`);
  }
  const text = await res.text();
  const body = text ? JSON.parse(text) : {};
  if (!res.ok) throw new Error(body.detail ?? body.message ?? res.statusText);
  return body;
}

function makeMatrix(rows: number, cols: number, value = 0) {
  return Array.from({ length: rows }, () => Array.from({ length: cols }, () => value));
}

function nums(values: unknown, length: number) {
  const arr = Array.isArray(values) ? values : [];
  return Array.from({ length }, (_, index) => Number(arr[index] ?? 0));
}

function matrix(values: unknown, rows: number, cols: number) {
  const arr = Array.isArray(values) ? values : [];
  return Array.from({ length: rows }, (_, row) => nums(arr[row], cols));
}

function formFromSnapshot(snapshot: Snapshot | null) {
  const control = snapshot?.control ?? {};
  return {
    fanSpeed: Number(control.fan_speed ?? 0),
    servoAngles: nums(control.servo_angles, 4),
    feedforwardValues: nums(control.feedforward_values, 4),
    pidParam: matrix(control.pid_param, 7, 6),
    jacobianMatrix: matrix(control.jacobian_matrix, 3, 4),
    surfaceMin: nums(control.surface_angle_min_d, 4),
    surfaceMax: nums(control.surface_angle_max_d, 4),
    pitchNeed: Number(control.pitch_need ?? 0),
  };
}

export default function Page() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [status, setStatus] = useState("connecting...");
  const [busy, setBusy] = useState("");
  const [ports, setPorts] = useState<PortInfo[]>([]);
  const [selectedPort, setSelectedPort] = useState("AUTO_CH340");
  const [flashResult, setFlashResult] = useState("idle");
  const [autoTuneStatus, setAutoTuneStatus] = useState("idle");
  const [fanSpeed, setFanSpeed] = useState(1000);
  const [fanCustom, setFanCustom] = useState(1400);
  const [servoAngles, setServoAngles] = useState<number[]>([0, 0, 0, 0]);
  const [feedforwardValues, setFeedforwardValues] = useState<number[]>([0, 0, 0, 0]);
  const [pidParam, setPidParam] = useState<number[][]>(makeMatrix(7, 6, 0));
  const [jacobianMatrix, setJacobianMatrix] = useState<number[][]>(makeMatrix(3, 4, 0));
  const [surfaceMin, setSurfaceMin] = useState<number[]>([-35, -35, -30, -30]);
  const [surfaceMax, setSurfaceMax] = useState<number[]>([35, 35, 40, 40]);
  const [pitchNeed, setPitchNeed] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);

  function applyForm(next: Snapshot | null) {
    const form = formFromSnapshot(next);
    setFanSpeed(form.fanSpeed);
    setFanCustom(form.fanSpeed || 1400);
    setServoAngles(form.servoAngles);
    setFeedforwardValues(form.feedforwardValues);
    setPidParam(form.pidParam);
    setJacobianMatrix(form.jacobianMatrix);
    setSurfaceMin(form.surfaceMin);
    setSurfaceMax(form.surfaceMax);
    setPitchNeed(form.pitchNeed);
  }

  useEffect(() => {
    readJson("/api/snapshot")
      .then((data) => {
        setSnapshot(data);
        applyForm(data);
        setStatus("ready");
      })
      .catch((error: Error) => setStatus(error.message));

    readJson("/api/ports")
      .then((data) => setPorts(data.ports ?? []))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    const socket = new WebSocket(`${WS_BASE}/ws`);
    wsRef.current = socket;
    socket.onopen = () => setStatus("live");
    socket.onclose = () => setStatus("ws closed");
    socket.onerror = () => setStatus("ws error");
    socket.onmessage = (event) => {
      try {
        setSnapshot(JSON.parse(event.data));
      } catch {
        // ignore one bad frame
      }
    };
    return () => socket.close();
  }, []);

  useEffect(() => {
    const tuning = snapshot?.runtime?.auto_tune;
    if (!tuning) return;
    setAutoTuneStatus(tuning.running ? `${tuning.stage || "running"}` : tuning.stage || "idle");
  }, [snapshot]);

  async function runAction(name: string, action: () => Promise<void>) {
    setBusy(name);
    try {
      await action();
    } catch (error) {
      setStatus((error as Error).message);
    } finally {
      setBusy("");
    }
  }

  async function patchControl(payload: Record<string, unknown>) {
    const data = await readJson("/api/control", { method: "POST", body: JSON.stringify(payload) });
    setSnapshot(data);
    applyForm(data);
  }

  function quickPatch(payload: Record<string, unknown>) {
    void patchControl(payload);
  }

  const serial = snapshot?.runtime?.serial ?? {};
  const receive = snapshot?.runtime?.receive ?? {};
  const send = snapshot?.runtime?.send ?? {};
  const analysis = snapshot?.runtime?.analysis ?? {};
  const mainState = snapshot?.state?.main ?? "STOP";
  const blackbox = receive.blackbox_logging ?? {};
  const rxCount = Number(receive.receive_count ?? 0);
  const csvCount = Number(blackbox.record_count ?? 0);

  return (
    <main className="shell">
      <section className="panel">
        <h1>Ground Station Web</h1>
        <div className="meta">
          <span>status: {status}</span>
          <span>serial: {serial.com_port ?? "none"}</span>
          <span>rx: {rxCount}</span>
          <span>csv: {blackbox.is_logging ? `recording ${csvCount}` : "idle"}</span>
          <span>busy: {busy || "none"}</span>
        </div>
      </section>

      <section className="panel">
        <h2>1. USB TTL / JSON</h2>
        <div className="toolbar">
          <label>
            <span>COM port</span>
            <select value={selectedPort} onChange={(event) => setSelectedPort(event.target.value)}>
              <option value="AUTO_CH340">auto CH340</option>
              {ports.map((port) => (
                <option key={port.device} value={port.device}>
                  {port.device} {port.description}
                </option>
              ))}
            </select>
          </label>
          <button onClick={() => runAction("connect", async () => connectPort(selectedPort, setStatus))}>connect</button>
          <button onClick={() => runAction("disconnect", async () => disconnectPort(setStatus))}>disconnect</button>
          <button onClick={() => runAction("load json", async () => loadJson(setSnapshot, applyForm, setStatus))}>load json</button>
          <button onClick={() => runAction("save json", async () => saveJson(setStatus))}>save json</button>
        </div>
      </section>

      <section className="panel">
        <h2>2. State</h2>
        <div className="state-row">
          {MAIN_STATES.map((state) => (
            <button
              key={state}
              className={state === mainState ? "active" : ""}
              onClick={() =>
                state === "TUNING"
                  ? runAction("tuning", async () => startTuningSequence(setStatus, setAutoTuneStatus))
                  : runAction(`state ${state}`, () => patchControl({ main_state: state }))
              }
            >
              {state}
            </button>
          ))}
        </div>
        <div className="toolbar compact">
          <button onClick={() => runAction("flash", async () => flashSave(setFlashResult, setSnapshot))}>save flash</button>
          <button onClick={() => runAction("auto jacobian", () => startAutoTune("jacobian", setAutoTuneStatus))}>auto jacobian</button>
          <button onClick={() => runAction("auto all", () => startAutoTune("all", setAutoTuneStatus))}>auto all</button>
          <span>flash: {flashResult}</span>
          <span>tune: {autoTuneStatus}</span>
        </div>
      </section>

      <section className="panel">
        <h2>3. Raw HEX</h2>
        <div className="hex-line">
          <strong>TX</strong>
          <code>{send.hex ?? "no tx frame"}</code>
        </div>
        <div className="hex-line">
          <strong>RX</strong>
          <code>{receive.last_rx_hex ?? "no rx frame"}</code>
        </div>
        <div className="meta">
          <span>last rx: {receive.last_receive_time ?? "never"}</span>
          <span>errors: {receive.error_count ?? 0}</span>
          <span>blackbox received: {snapshot?.blackbox?.received ? "yes" : "no"}</span>
        </div>
      </section>

      <section className="panel">
        <h2>4. Parameters</h2>
        <div className="param-row tight">
          <div className="param-block narrow">
            <h3>Fan speed</h3>
            <div className="fan-row">
              <button onClick={() => quickPatch({ fan_speed: 1000 })}>1000</button>
              <button onClick={() => quickPatch({ fan_speed: 1400 })}>1400</button>
              <label className="fan-custom">
                <span>custom</span>
                <input
                  type="number"
                  step="1"
                  value={fanCustom}
                  onChange={(event) => setFanCustom(Number(event.target.value))}
                />
              </label>
              <button onClick={() => quickPatch({ fan_speed: fanCustom })}>apply</button>
            </div>
          </div>

          <div className="param-block narrow">
            <h3>Servo</h3>
            <MatrixTable
              rowLabels={["servo"]}
              colLabels={["1", "2", "3", "4"]}
              values={[servoAngles]}
              onChange={(row, col, value) => setServoAngles(replaceAt(servoAngles, col, value))}
              compact
            />
            <button onClick={() => quickPatch({ servo_angles: servoAngles })}>apply servo</button>
          </div>

          <div className="param-block narrow">
            <h3>Feedforward</h3>
            <MatrixTable
              rowLabels={["ff"]}
              colLabels={["1", "2", "3", "4"]}
              values={[feedforwardValues]}
              onChange={(row, col, value) => setFeedforwardValues(replaceAt(feedforwardValues, col, value))}
              compact
            />
            <button onClick={() => quickPatch({ feedforward_values: feedforwardValues })}>apply ff</button>
          </div>
        </div>

        <div className="param-block">
          <h3>PID</h3>
          <MatrixTable
            rowLabels={PID_LABELS}
            colLabels={PID_COLS}
            values={pidParam}
            onChange={(row, col, value) => setPidParam(replaceMatrix(pidParam, row, col, value))}
          />
          <button onClick={() => runAction("apply pid", () => patchControl({ pid_param: pidParam }))}>apply pid</button>
        </div>

        <div className="param-row tight">
          <div className="param-block narrow">
            <h3>Jacobian 3x4</h3>
            <MatrixTable
              rowLabels={JACOBIAN_ROWS}
              colLabels={["1", "2", "3", "4"]}
              values={jacobianMatrix}
              onChange={(row, col, value) => setJacobianMatrix(replaceMatrix(jacobianMatrix, row, col, value))}
              compact
            />
            <button onClick={() => runAction("apply jacobian", () => patchControl({ jacobian_matrix: jacobianMatrix }))}>
              apply jacobian
            </button>
          </div>

          <div className="param-block narrow">
            <h3>Surface Limit</h3>
            <MatrixTable
              rowLabels={SURFACE_ROWS}
              colLabels={SURFACE_COLS}
              values={surfaceVector(surfaceMin, surfaceMax, pitchNeed)}
              onChange={(row, col, value) => {
                if (row < 4) setSurfaceMin(replaceAt(surfaceMin, row, value));
                else if (row < 8) setSurfaceMax(replaceAt(surfaceMax, row - 4, value));
                else setPitchNeed(value);
              }}
              compact
            />
            <button
              onClick={() =>
                runAction("apply surface", async () => {
                  await saveSurfaceLimit(surfaceMin, surfaceMax, pitchNeed);
                  setStatus("surface limit saved");
                })
              }
            >
              save surface
            </button>
          </div>
        </div>
      </section>

      <section className="panel">
        <h2>5. Analysis / Feishu</h2>
        <div className="toolbar compact">
          <button onClick={() => runAction("analysis", async () => analysisRun(setStatus))}>run analysis</button>
          <button onClick={() => runAction("feishu", async () => feishuStatus(setStatus))}>feishu status</button>
          <span>last report: {analysis.last_report_path ?? "none"}</span>
          <span>last error: {analysis.last_error ?? "none"}</span>
        </div>
      </section>
    </main>
  );
}

async function connectPort(selectedPort: string, setStatus: (value: string) => void) {
  const data = await readJson("/api/connect", {
    method: "POST",
    body: JSON.stringify({
      com_port: selectedPort === "AUTO_CH340" ? null : selectedPort,
      auto_keyword: "CH340",
    }),
  });
  setStatus(data.connected ? `connected ${data.com_port}` : `connect failed: ${data.error ?? "unknown"}`);
}

async function disconnectPort(setStatus: (value: string) => void) {
  await readJson("/api/disconnect", { method: "POST", body: "{}" });
  setStatus("disconnected");
}

async function loadJson(setSnapshot: (value: Snapshot) => void, applyForm: (value: Snapshot | null) => void, setStatus: (value: string) => void) {
  const data = await readJson("/api/params/load", { method: "POST", body: "{}" });
  setSnapshot(data.snapshot);
  applyForm(data.snapshot);
  setStatus("json loaded");
}

async function saveJson(setStatus: (value: string) => void) {
  await readJson("/api/params/save", { method: "POST", body: "{}" });
  setStatus("json saved");
}

async function flashSave(setFlashResult: (value: string) => void, setSnapshot: (value: Snapshot) => void) {
  const data = await readJson("/api/flash/save", { method: "POST", body: "{}" });
  setFlashResult(data.ok ? `ok status=${data.status}` : data.error ?? `fail status=${data.status}`);
  setSnapshot(data.snapshot);
}

async function startAutoTune(mode: string, setAutoTuneStatus: (value: string) => void) {
  const data = await readJson(`/api/auto-tune?mode=${mode}`, { method: "POST", body: "{}" });
  setAutoTuneStatus(data.ok ? `${mode} started` : data.error ?? "failed");
}

async function startTuningSequence(setStatus: (value: string) => void, setAutoTuneStatus: (value: string) => void) {
  const data = await readJson("/api/tuning/run", { method: "POST", body: "{}" });
  setStatus(data.ok ? "tuning sequence started" : data.error ?? "failed");
  setAutoTuneStatus(data.ok ? `${data.status?.stage ?? "running"}` : data.error ?? "failed");
}

async function analysisRun(setStatus: (value: string) => void) {
  const data = await readJson("/api/analysis/run", { method: "POST", body: JSON.stringify({}) });
  setStatus(`analysis report: ${data.report_path ?? "done"}`);
}

async function feishuStatus(setStatus: (value: string) => void) {
  const data = await readJson("/api/feishu/research");
  setStatus(`feishu connector: ${data.available_connector ? "available" : "local draft only"}`);
}

async function saveSurfaceLimit(surfaceMin: number[], surfaceMax: number[], pitchNeed: number) {
  await readJson("/api/control", {
    method: "POST",
    body: JSON.stringify({
      surface_angle_min_d: surfaceMin,
      surface_angle_max_d: surfaceMax,
      pitch_need: pitchNeed,
    }),
  });
  await readJson("/api/params/save", { method: "POST", body: "{}" });
}

function surfaceVector(surfaceMin: number[], surfaceMax: number[], pitchNeed: number) {
  return [...surfaceMin, ...surfaceMax, pitchNeed].map((value) => [value]);
}

function MatrixTable({
  rowLabels,
  colLabels,
  values,
  onChange,
  compact = false,
}: {
  rowLabels: string[];
  colLabels: string[];
  values: number[][];
  onChange: (row: number, col: number, value: number) => void;
  compact?: boolean;
}) {
  return (
    <div className={`table-wrap ${compact ? "compact" : ""}`}>
      <table className={compact ? "compact" : ""}>
        <thead>
          <tr>
            <th />
            {colLabels.map((label) => (
              <th key={label}>{label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {values.map((row, rowIndex) => (
            <tr key={rowIndex}>
              <th>{rowLabels[rowIndex] ?? `row ${rowIndex + 1}`}</th>
              {row.map((value, colIndex) => (
                <td key={`${rowIndex}-${colIndex}`}>
                  <input type="number" step="0.01" value={value} onChange={(event) => onChange(rowIndex, colIndex, Number(event.target.value))} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function replaceAt(values: number[], index: number, value: number) {
  const next = [...values];
  next[index] = value;
  return next;
}

function replaceMatrix(values: number[][], row: number, col: number, value: number) {
  return values.map((items, rowIndex) => (rowIndex === row ? replaceAt(items, col, value) : items));
}
