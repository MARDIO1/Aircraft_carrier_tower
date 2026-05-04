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

function apiUrl(path: string) { return `${API_BASE}${path}`; }

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
      .then((data) => { setSnapshot(data); applyForm(data); setStatus("ready"); })
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
      try { setSnapshot(JSON.parse(event.data)); } catch { /* ignore */ }
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
    try { await action(); } catch (error) { setStatus((error as Error).message); }
    finally { setBusy(""); }
  }

  async function patchControl(payload: Record<string, unknown>) {
    const data = await readJson("/api/control", { method: "POST", body: JSON.stringify(payload) });
    setSnapshot(data);
    applyForm(data);
  }

  function quickPatch(payload: Record<string, unknown>) { void patchControl(payload); }

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
      {/* ── 1. 连接栏 ── */}
      <section className="panel conn-bar">
        <h2>连接 / JSON</h2>
        <div className="toolbar">
          <label className="com-select">
            <span>COM</span>
            <select value={selectedPort} onChange={(e) => setSelectedPort(e.target.value)}>
              <option value="AUTO_CH340">auto CH340</option>
              {ports.map((p) => <option key={p.device} value={p.device}>{p.device} {p.description}</option>)}
            </select>
          </label>
          <button onClick={() => runAction("connect", () => connectPort(selectedPort, setStatus))}>connect</button>
          <button onClick={() => runAction("disconnect", () => disconnectPort(setStatus))}>disconnect</button>
          <span className="sep" />
          <button onClick={() => runAction("load json", () => loadJson(setSnapshot, applyForm, setStatus))}>load json</button>
          <button onClick={() => runAction("save json", () => saveJson(setStatus))}>save json</button>
        </div>
        <div className="status-line">
          <span className={`dot ${status === "live" ? "on" : "off"}`} />
          <span>状态: {status}</span>
          <span>串口: {serial.com_port ?? "none"}</span>
          <span>收包: {rxCount}</span>
          <span>CSV: {blackbox.is_logging ? `recording ${csvCount}` : "idle"}</span>
          <span>忙: {busy || "none"}</span>
        </div>
      </section>

      {/* ── 2. 状态栏 ── */}
      <section className="panel state-bar">
        <h2>状态控制</h2>
        <div className="state-row">
          {MAIN_STATES.map((s) => (
            <button
              key={s}
              className={s === mainState ? "active" : ""}
              onClick={() =>
                s === "TUNING"
                  ? runAction("tuning", () => startTuningSequence(setStatus, setAutoTuneStatus))
                  : runAction(`state ${s}`, () => patchControl({ main_state: s }))
              }
            >
              {s}
            </button>
          ))}
        </div>
        <div className="toolbar compact">
          <button onClick={() => runAction("flash", () => flashSave(setFlashResult, setSnapshot))}>save flash</button>
          <button onClick={() => runAction("auto jacobian", () => startAutoTune("jacobian", setAutoTuneStatus))}>auto jacobian</button>
          <button onClick={() => runAction("auto all", () => startAutoTune("all", setAutoTuneStatus))}>auto all</button>
          <span className="tag">flash: {flashResult}</span>
          <span className="tag">tune: {autoTuneStatus}</span>
        </div>
      </section>

      {/* ── 3. 收发原始数据 ── */}
      <section className="panel hex-bar">
        <h2>原始数据帧 (HEX)</h2>
        <div className="hex-line">
          <strong>TX</strong>
          <code>{send.hex ?? "等待发送..."}</code>
        </div>
        <div className="hex-line">
          <strong>RX</strong>
          <code>{receive.last_rx_hex ?? "等待接收..."}</code>
        </div>
        <div className="meta">
          <span>最近接收: {receive.last_receive_time ?? "never"}</span>
          <span>错误: {receive.error_count ?? 0}</span>
          <span>BlackBox: {snapshot?.blackbox?.received ? "yes" : "no"}</span>
        </div>
      </section>

      {/* ── 4. 参数调节区 ── */}
      <section className="panel param-bar">
        <h2>参数调节</h2>

        {/* 风扇 */}
        <div className="param-block narrow">
          <h3>Fan speed</h3>
          <div className="fan-row">
            <button onClick={() => quickPatch({ fan_speed: 1000 })}>1000</button>
            <button onClick={() => quickPatch({ fan_speed: 1400 })}>1400</button>
            <label className="fan-custom">
              <span>custom</span>
              <input type="number" step="1" value={fanCustom} onChange={(e) => setFanCustom(Number(e.target.value))} />
            </label>
            <button onClick={() => quickPatch({ fan_speed: fanCustom })}>apply</button>
          </div>
        </div>

        <div className="param-row tight">
          {/* 舵机 */}
          <div className="param-block narrow">
            <h3>Servo</h3>
            <MatrixTable
              rowLabels={["servo"]} colLabels={["1", "2", "3", "4"]}
              values={[servoAngles]}
              onChange={(r, c, v) => setServoAngles(replaceAt(servoAngles, c, v))}
              compact
            />
            <button onClick={() => quickPatch({ servo_angles: servoAngles })}>apply servo</button>
          </div>

          {/* 前馈 */}
          <div className="param-block narrow">
            <h3>Feedforward</h3>
            <MatrixTable
              rowLabels={["ff"]} colLabels={["1", "2", "3", "4"]}
              values={[feedforwardValues]}
              onChange={(r, c, v) => setFeedforwardValues(replaceAt(feedforwardValues, c, v))}
              compact
            />
            <button onClick={() => quickPatch({ feedforward_values: feedforwardValues })}>apply ff</button>
          </div>

          {/* 翼面限幅 */}
          <div className="param-block narrow">
            <h3>Surface Limit</h3>
            <MatrixTable
              rowLabels={SURFACE_ROWS} colLabels={SURFACE_COLS}
              values={surfaceVector(surfaceMin, surfaceMax, pitchNeed)}
              onChange={(row, col, v) => {
                if (row < 4) setSurfaceMin(replaceAt(surfaceMin, row, v));
                else if (row < 8) setSurfaceMax(replaceAt(surfaceMax, row - 4, v));
                else setPitchNeed(v);
              }}
              compact
            />
            <button onClick={() => runAction("apply surface", () => saveSurfaceLimit(surfaceMin, surfaceMax, pitchNeed))}>
              save surface
            </button>
          </div>
        </div>

        {/* PID */}
        <div className="param-block">
          <h3>PID 7×6 Matrix</h3>
          <MatrixTable
            rowLabels={PID_LABELS} colLabels={PID_COLS}
            values={pidParam}
            onChange={(r, c, v) => setPidParam(replaceMatrix(pidParam, r, c, v))}
          />
          <button onClick={() => runAction("apply pid", () => patchControl({ pid_param: pidParam }))}>apply pid</button>
        </div>

        {/* Jacobian */}
        <div className="param-block">
          <h3>Jacobian 3×4</h3>
          <MatrixTable
            rowLabels={JACOBIAN_ROWS} colLabels={["1", "2", "3", "4"]}
            values={jacobianMatrix}
            onChange={(r, c, v) => setJacobianMatrix(replaceMatrix(jacobianMatrix, r, c, v))}
          />
          <button onClick={() => runAction("apply jacobian", () => patchControl({ jacobian_matrix: jacobianMatrix }))}>
            apply jacobian
          </button>
        </div>
      </section>

      {/* ── 5. 分析/飞书 ── */}
      <section className="panel analysis-bar">
        <h2>分析 / 飞书</h2>
        <div className="toolbar compact">
          <button onClick={() => runAction("analysis", () => analysisRun(setStatus))}>run analysis</button>
          <button onClick={() => runAction("feishu", () => feishuStatus(setStatus))}>feishu status</button>
          <button style={{ backgroundColor: "#20b2aa", color: "white" }} onClick={async () => {
            setStatus("正在同步最新参数到飞书知识库多维表格...");
            try {
              const res = await fetch("http://127.0.0.1:8000/api/sync_feishu", { method: "POST" });
              const result = await res.json();
              if (result.success) {
                setStatus("✅ 飞书多维表格打表同步成功！");
              } else {
                setStatus("❌ 飞书同步失败: " + result.error + "\n" + result.logs);
              }
            } catch(e: any) {
              setStatus("❌ 飞书后台请求出错: " + e.message);
            }
          }}>☁️ 同步当前参数到飞书 Bitable</button>
          <span className="tag">报告: {analysis.last_report_path ?? "none"}</span>
          <span className="tag">错误: {analysis.last_error ?? "none"}</span>
        </div>
      </section>
    </main>
  );
}

// ── API helpers ──

async function connectPort(selectedPort: string, setStatus: (v: string) => void) {
  const data = await readJson("/api/connect", {
    method: "POST",
    body: JSON.stringify({ com_port: selectedPort === "AUTO_CH340" ? null : selectedPort, auto_keyword: "CH340" }),
  });
  setStatus(data.connected ? `connected ${data.com_port}` : `connect failed: ${data.error ?? "unknown"}`);
}

async function disconnectPort(setStatus: (v: string) => void) {
  await readJson("/api/disconnect", { method: "POST", body: "{}" });
  setStatus("disconnected");
}

async function loadJson(setSnapshot: (v: Snapshot) => void, applyForm: (v: Snapshot | null) => void, setStatus: (v: string) => void) {
  const data = await readJson("/api/params/load", { method: "POST", body: "{}" });
  setSnapshot(data.snapshot); applyForm(data.snapshot); setStatus("json loaded");
}

async function saveJson(setStatus: (v: string) => void) {
  await readJson("/api/params/save", { method: "POST", body: "{}" });
  setStatus("json saved");
}

async function flashSave(setFlashResult: (v: string) => void, setSnapshot: (v: Snapshot) => void) {
  const data = await readJson("/api/flash/save", { method: "POST", body: "{}" });
  setFlashResult(data.ok ? `ok status=${data.status}` : data.error ?? `fail status=${data.status}`);
  setSnapshot(data.snapshot);
}

async function startAutoTune(mode: string, setAutoTuneStatus: (v: string) => void) {
  const data = await readJson(`/api/auto-tune?mode=${mode}`, { method: "POST", body: "{}" });
  setAutoTuneStatus(data.ok ? `${mode} started` : data.error ?? "failed");
}

async function startTuningSequence(setStatus: (v: string) => void, setAutoTuneStatus: (v: string) => void) {
  const data = await readJson("/api/tuning/run", { method: "POST", body: "{}" });
  setStatus(data.ok ? "tuning sequence started" : data.error ?? "failed");
  setAutoTuneStatus(data.ok ? `${data.status?.stage ?? "running"}` : data.error ?? "failed");
}

async function analysisRun(setStatus: (v: string) => void) {
  const data = await readJson("/api/analysis/run", { method: "POST", body: JSON.stringify({}) });
  setStatus(`analysis report: ${data.report_path ?? "done"}`);
}

async function feishuStatus(setStatus: (v: string) => void) {
  const data = await readJson("/api/feishu/research");
  setStatus(`feishu connector: ${data.available_connector ? "available" : "local draft only"}`);
}

async function saveSurfaceLimit(surfaceMin: number[], surfaceMax: number[], pitchNeed: number) {
  await readJson("/api/control", {
    method: "POST",
    body: JSON.stringify({ surface_angle_min_d: surfaceMin, surface_angle_max_d: surfaceMax, pitch_need: pitchNeed }),
  });
  await readJson("/api/params/save", { method: "POST", body: "{}" });
}

function surfaceVector(surfaceMin: number[], surfaceMax: number[], pitchNeed: number) {
  return [...surfaceMin, ...surfaceMax, pitchNeed].map((v) => [v]);
}

// ── Components ──

function MatrixTable({
  rowLabels, colLabels, values, onChange, compact = false,
}: {
  rowLabels: string[]; colLabels: string[]; values: number[][];
  onChange: (row: number, col: number, value: number) => void; compact?: boolean;
}) {
  return (
    <div className={`table-wrap ${compact ? "compact" : ""}`}>
      <table className={compact ? "compact" : ""}>
        <thead>
          <tr>
            <th />
            {colLabels.map((l) => <th key={l}>{l}</th>)}
          </tr>
        </thead>
        <tbody>
          {values.map((row, ri) => (
            <tr key={ri}>
              <th>{rowLabels[ri] ?? `row ${ri + 1}`}</th>
              {row.map((v, ci) => (
                <td key={`${ri}-${ci}`}>
                  <input type="number" step="0.01" value={v} onChange={(e) => onChange(ri, ci, Number(e.target.value))} />
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
  const next = [...values]; next[index] = value; return next;
}

function replaceMatrix(values: number[][], row: number, col: number, value: number) {
  return values.map((items, ri) => (ri === row ? replaceAt(items, col, value) : items));
}