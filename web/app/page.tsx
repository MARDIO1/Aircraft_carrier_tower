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
const SURFACE_LABELS = ["surface 1", "surface 2", "surface 3", "surface 4"];

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

  const initial = formFromSnapshot(null);
  const [fanSpeed, setFanSpeed] = useState(initial.fanSpeed);
  const [servoAngles, setServoAngles] = useState(initial.servoAngles);
  const [feedforwardValues, setFeedforwardValues] = useState(initial.feedforwardValues);
  const [pidParam, setPidParam] = useState(initial.pidParam);
  const [jacobianMatrix, setJacobianMatrix] = useState(initial.jacobianMatrix);
  const [surfaceMin, setSurfaceMin] = useState(initial.surfaceMin);
  const [surfaceMax, setSurfaceMax] = useState(initial.surfaceMax);
  const [pitchNeed, setPitchNeed] = useState(initial.pitchNeed);
  const wsRef = useRef<WebSocket | null>(null);

  function applyForm(next: Snapshot | null) {
    const form = formFromSnapshot(next);
    setFanSpeed(form.fanSpeed);
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
        // Ignore one bad frame instead of freezing controls.
      }
    };
    return () => socket.close();
  }, []);

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

  async function patchControl(payload: Record<string, unknown>, syncForm = false) {
    const data = await readJson("/api/control", { method: "POST", body: JSON.stringify(payload) });
    setSnapshot(data);
    if (syncForm) applyForm(data);
  }

  const serial = snapshot?.runtime?.serial ?? {};
  const receive = snapshot?.runtime?.receive ?? {};
  const send = snapshot?.runtime?.send ?? {};
  const analysis = snapshot?.runtime?.analysis ?? {};
  const mainState = snapshot?.state?.main ?? "STOP";
  const connected = Boolean(serial.connected);
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
          <button
            onClick={() =>
              runAction("connect", async () => {
                const data = await readJson("/api/connect", {
                  method: "POST",
                  body: JSON.stringify({
                    com_port: selectedPort === "AUTO_CH340" ? null : selectedPort,
                    auto_keyword: "CH340",
                  }),
                });
                setStatus(data.connected ? `connected ${data.com_port}` : `connect failed: ${data.error ?? "unknown"}`);
              })
            }
          >
            connect
          </button>
          <button
            onClick={() =>
              runAction("disconnect", async () => {
                await readJson("/api/disconnect", { method: "POST", body: "{}" });
                setStatus("disconnected");
              })
            }
          >
            disconnect
          </button>
          <button
            onClick={() =>
              runAction("load json", async () => {
                const data = await readJson("/api/params/load", { method: "POST", body: "{}" });
                setSnapshot(data.snapshot);
                applyForm(data.snapshot);
                setStatus("json loaded");
              })
            }
          >
            load json
          </button>
          <button
            onClick={() =>
              runAction("save json", async () => {
                await readJson("/api/params/save", { method: "POST", body: "{}" });
                setStatus("json saved");
              })
            }
          >
            save json
          </button>
        </div>
      </section>

      <section className="panel">
        <h2>2. State</h2>
        <div className="state-row">
          {MAIN_STATES.map((state) => (
            <button
              key={state}
              className={state === mainState ? "active" : ""}
              onClick={() => runAction(`state ${state}`, () => patchControl({ main_state: state }))}
            >
              {state}
            </button>
          ))}
        </div>
        <div className="toolbar compact">
          <button
            onClick={() =>
              runAction("flash", async () => {
                const data = await readJson("/api/flash/save", { method: "POST", body: "{}" });
                setFlashResult(data.ok ? `ok status=${data.status}` : data.error ?? `fail status=${data.status}`);
                setSnapshot(data.snapshot);
              })
            }
          >
            save flash
          </button>
          <button onClick={() => runAction("auto jacobian", () => startAutoTune("jacobian"))}>auto jacobian</button>
          <button onClick={() => runAction("auto surface", () => startAutoTune("surface_limit"))}>auto surface</button>
          <button onClick={() => runAction("auto all", () => startAutoTune("all"))}>auto all</button>
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
        <div className="param-block">
          <h3>Motor / Servo / Feedforward</h3>
          <div className="grid four">
            <NumberField label="fan speed" value={fanSpeed} onChange={setFanSpeed} />
            {servoAngles.map((value, index) => (
              <NumberField
                key={`servo-${index}`}
                label={`servo ${index + 1}`}
                value={value}
                onChange={(next) => setServoAngles(replaceAt(servoAngles, index, next))}
              />
            ))}
            {feedforwardValues.map((value, index) => (
              <NumberField
                key={`ff-${index}`}
                label={`ff ${index + 1}`}
                value={value}
                onChange={(next) => setFeedforwardValues(replaceAt(feedforwardValues, index, next))}
              />
            ))}
          </div>
          <div className="toolbar compact">
            <button onClick={() => runAction("apply fan", () => patchControl({ fan_speed: fanSpeed }))}>apply fan</button>
            <button onClick={() => runAction("apply servo", () => patchControl({ servo_angles: servoAngles }))}>apply servo</button>
            <button onClick={() => runAction("apply ff", () => patchControl({ feedforward_values: feedforwardValues }))}>apply feedforward</button>
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

        <div className="param-block">
          <h3>Jacobian 3x4</h3>
          <MatrixTable
            rowLabels={JACOBIAN_ROWS}
            colLabels={SURFACE_LABELS}
            values={jacobianMatrix}
            onChange={(row, col, value) => setJacobianMatrix(replaceMatrix(jacobianMatrix, row, col, value))}
          />
          <button onClick={() => runAction("apply jacobian", () => patchControl({ jacobian_matrix: jacobianMatrix }))}>
            apply jacobian
          </button>
        </div>

        <div className="param-block">
          <h3>Surface Limit</h3>
          <div className="grid four">
            {surfaceMin.map((value, index) => (
              <NumberField
                key={`min-${index}`}
                label={`min ${index + 1}`}
                value={value}
                onChange={(next) => setSurfaceMin(replaceAt(surfaceMin, index, next))}
              />
            ))}
            {surfaceMax.map((value, index) => (
              <NumberField
                key={`max-${index}`}
                label={`max ${index + 1}`}
                value={value}
                onChange={(next) => setSurfaceMax(replaceAt(surfaceMax, index, next))}
              />
            ))}
            <NumberField label="pitch need" value={pitchNeed} onChange={setPitchNeed} />
          </div>
          <button
            onClick={() =>
              runAction("apply surface", () =>
                patchControl({
                  surface_angle_min_d: surfaceMin,
                  surface_angle_max_d: surfaceMax,
                  pitch_need: pitchNeed,
                })
              )
            }
          >
            apply surface limit
          </button>
        </div>
      </section>

      <section className="panel">
        <h2>5. Analysis / Feishu</h2>
        <div className="toolbar compact">
          <button
            onClick={() =>
              runAction("analysis", async () => {
                const data = await readJson("/api/analysis/run", { method: "POST", body: JSON.stringify({}) });
                setStatus(`analysis report: ${data.report_path ?? "done"}`);
              })
            }
          >
            run analysis
          </button>
          <button
            onClick={() =>
              runAction("feishu", async () => {
                const data = await readJson("/api/feishu/research");
                setStatus(`feishu connector: ${data.available_connector ? "available" : "local draft only"}`);
              })
            }
          >
            feishu status
          </button>
          <span>last report: {analysis.last_report_path ?? "none"}</span>
          <span>last error: {analysis.last_error ?? "none"}</span>
        </div>
      </section>
    </main>
  );

  async function startAutoTune(mode: string) {
    const data = await readJson(`/api/auto-tune?mode=${mode}`, { method: "POST", body: "{}" });
    setAutoTuneStatus(data.ok ? `${mode} started` : data.error ?? "failed");
  }
}

function NumberField({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return (
    <label>
      <span>{label}</span>
      <input type="number" step="0.01" value={value} onChange={(event) => onChange(Number(event.target.value))} />
    </label>
  );
}

function MatrixTable({
  rowLabels,
  colLabels,
  values,
  onChange,
}: {
  rowLabels: string[];
  colLabels: string[];
  values: number[][];
  onChange: (row: number, col: number, value: number) => void;
}) {
  return (
    <div className="table-wrap">
      <table>
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
