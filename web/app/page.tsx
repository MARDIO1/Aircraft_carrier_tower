"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type Snapshot = Record<string, any>;
type Report = Record<string, any>;

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const WS_BASE = API_BASE.replace(/^http/, "ws");

const mainStateOrder = ["STOP", "AUTO", "TOWER", "TUNING", "DATA"] as const;
const subStateOrder = ["SERVO", "FEEDFORWARD", "PID", "JACOBIAN"] as const;

function apiUrl(path: string) {
  return `${API_BASE}${path}`;
}

async function readJson(path: string, init?: RequestInit) {
  let res: Response;
  try {
    res = await fetch(apiUrl(path), {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
    });
  } catch (error) {
    throw new Error(`Cannot reach backend ${API_BASE}. Start it with: uv run python src/launcher.py`);
  }
  const text = await res.text();
  const body = text ? JSON.parse(text) : {};
  if (!res.ok) {
    throw new Error(body.detail ?? body.message ?? res.statusText);
  }
  return body;
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function makeMatrix<T>(rows: number, cols: number, value: T): T[][] {
  return Array.from({ length: rows }, () => Array.from({ length: cols }, () => value));
}

function applySnapshotToForm(data: Snapshot) {
  return {
    fanSpeed: Number(data.control?.fan_speed ?? 0),
    mainSwitch: Number(data.control?.main_switch ?? 0),
    servoAngles: [...(data.control?.servo_angles ?? [0, 0, 0, 0])].map(Number),
    feedforwardValues: [...(data.control?.feedforward_values ?? [0, 0, 0, 0])].map(Number),
    pidParam: (data.control?.pid_param ?? makeMatrix(7, 6, 0)).map((row: number[]) => row.map(Number)),
    jacobianMatrix: (data.control?.jacobian_matrix ?? makeMatrix(3, 4, 0)).map((row: number[]) => row.map(Number)),
  };
}

function Sparkline({
  values,
  accent = "var(--accent)",
}: {
  values: number[];
  accent?: string;
}) {
  const width = 360;
  const height = 120;
  const pad = 10;
  if (!values.length) {
    return <div className="spark-empty">no data</div>;
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(1e-6, max - min);
  const points = values
    .map((value, index) => {
      const x = pad + (index * (width - pad * 2)) / Math.max(1, values.length - 1);
      const y = height - pad - ((value - min) / span) * (height - pad * 2);
      return `${x},${y}`;
    })
    .join(" ");
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="sparkline" role="img" aria-label="chart">
      <defs>
        <linearGradient id="chartFill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={accent} stopOpacity="0.35" />
          <stop offset="100%" stopColor={accent} stopOpacity="0.02" />
        </linearGradient>
      </defs>
      <polyline points={points} fill="none" stroke={accent} strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
      <polyline
        points={`${pad},${height - pad} ${points} ${width - pad},${height - pad}`}
        fill="url(#chartFill)"
        stroke="none"
      />
    </svg>
  );
}

function MetricCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      {hint ? <div className="metric-hint">{hint}</div> : null}
    </div>
  );
}

export default function Page() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [reports, setReports] = useState<any[]>([]);
  const [activeReport, setActiveReport] = useState<Report | null>(null);
  const [status, setStatus] = useState("connecting...");
  const [busy, setBusy] = useState<string | null>(null);
  const [fanSpeed, setFanSpeed] = useState(0);
  const [mainSwitch, setMainSwitch] = useState(0);
  const [servoAngles, setServoAngles] = useState<number[]>([0, 0, 0, 0]);
  const [feedforwardValues, setFeedforwardValues] = useState<number[]>([0, 0, 0, 0]);
  const [pidParam, setPidParam] = useState<number[][]>(makeMatrix(7, 6, 0));
  const [jacobianMatrix, setJacobianMatrix] = useState<number[][]>(makeMatrix(3, 4, 0));

  const wsRef = useRef<WebSocket | null>(null);
  const blackbox = snapshot?.blackbox ?? {};

  const gyroSeries = useMemo(() => {
    const preview = activeReport?.preview ?? [];
    return {
      roll: preview.map((row: any) => Number(row.gyro_x ?? 0)),
      pitch: preview.map((row: any) => Number(row.gyro_y ?? 0)),
      yaw: preview.map((row: any) => Number(row.gyro_z ?? 0)),
    };
  }, [activeReport]);

  useEffect(() => {
    void (async () => {
      try {
        const snap = await readJson("/api/snapshot");
        setSnapshot(snap);
        const form = applySnapshotToForm(snap);
        setFanSpeed(form.fanSpeed);
        setMainSwitch(form.mainSwitch);
        setServoAngles(form.servoAngles);
        setFeedforwardValues(form.feedforwardValues);
        setPidParam(form.pidParam);
        setJacobianMatrix(form.jacobianMatrix);
        setStatus("ready");
      } catch (error) {
        setStatus(`offline: ${(error as Error).message}`);
      }
    })();
    void (async () => {
      try {
        const data = await readJson("/api/analysis/reports");
        setReports(data.reports ?? []);
      } catch {
        setReports([]);
      }
    })();
  }, []);

  useEffect(() => {
    const socket = new WebSocket(`${WS_BASE}/ws`);
    wsRef.current = socket;
    socket.onopen = () => setStatus("live");
    socket.onclose = () => setStatus("disconnected");
    socket.onerror = () => setStatus("socket error");
    socket.onmessage = (event) => {
      try {
        setSnapshot(JSON.parse(event.data));
      } catch {
        // ignore
      }
    };
    return () => socket.close();
  }, []);

  async function patchControl(payload: Record<string, unknown>) {
    setBusy(Object.keys(payload)[0] ?? "update");
    const optimisticMainState = typeof payload.main_state === "string" ? payload.main_state : null;
    const optimisticSubState = typeof payload.sub_state === "string" ? payload.sub_state : null;
    if (optimisticMainState || optimisticSubState) {
      setSnapshot((prev) => {
        if (!prev) {
          return prev;
        }
        return {
          ...prev,
          state: {
            ...prev.state,
            ...(optimisticMainState ? { main: optimisticMainState } : {}),
            ...(optimisticSubState ? { sub: optimisticSubState } : {}),
          },
        };
      });
    }
    try {
      const data = await readJson("/api/control", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setSnapshot(data);
      if (data.control) {
        const form = applySnapshotToForm(data);
        setFanSpeed(form.fanSpeed);
        setMainSwitch(form.mainSwitch);
        setServoAngles(form.servoAngles);
        setFeedforwardValues(form.feedforwardValues);
        setPidParam(form.pidParam);
        setJacobianMatrix(form.jacobianMatrix);
      }
    } catch (error) {
      setStatus((error as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function connect() {
    setBusy("connect");
    try {
      const data = await readJson("/api/connect", {
        method: "POST",
        body: JSON.stringify({ auto_keyword: "CH340" }),
      });
      setSnapshot((prev) => ({ ...(prev ?? {}), runtime: { ...(prev?.runtime ?? {}), serial: data } }));
      setStatus(data.connected ? `connected ${data.com_port ?? ""}` : `connect failed ${data.error ?? ""}`);
    } catch (error) {
      setStatus((error as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function disconnect() {
    setBusy("disconnect");
    try {
      const data = await readJson("/api/disconnect", { method: "POST", body: "{}" });
      setSnapshot((prev) => ({ ...(prev ?? {}), runtime: { ...(prev?.runtime ?? {}), serial: data } }));
      setStatus("disconnected");
    } catch (error) {
      setStatus((error as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function runAnalysis() {
    setBusy("analysis");
    try {
      const data = await readJson("/api/analysis/run", {
        method: "POST",
        body: JSON.stringify({ write_feishu_draft: true }),
      });
      setActiveReport(data);
      const index = await readJson("/api/analysis/reports");
      setReports(index.reports ?? []);
    } catch (error) {
      setStatus((error as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function loadJsonParams() {
    setBusy("load-json");
    try {
      const data = await readJson("/api/params/load", { method: "POST", body: "{}" });
      setSnapshot(data.snapshot);
      const form = applySnapshotToForm(data.snapshot);
      setFanSpeed(form.fanSpeed);
      setMainSwitch(form.mainSwitch);
      setServoAngles(form.servoAngles);
      setFeedforwardValues(form.feedforwardValues);
      setPidParam(form.pidParam);
      setJacobianMatrix(form.jacobianMatrix);
      setStatus("json loaded");
    } catch (error) {
      setStatus((error as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function saveJsonParams() {
    setBusy("save-json");
    try {
      const latest = await readJson("/api/control", {
        method: "POST",
        body: JSON.stringify({
          fan_speed: fanSpeed,
          main_switch: mainSwitch,
          servo_angles: servoAngles,
          feedforward_values: feedforwardValues,
          pid_param: pidParam,
          jacobian_matrix: jacobianMatrix,
        }),
      });
      setSnapshot(latest);
      const data = await readJson("/api/params/save", { method: "POST", body: "{}" });
      setSnapshot(data.snapshot);
      setStatus("json saved");
    } catch (error) {
      setStatus((error as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function loadReport(path: string) {
    try {
      const report = await readJson(`/api/analysis/report?path=${encodeURIComponent(path)}`);
      setActiveReport(report);
    } catch (error) {
      setStatus((error as Error).message);
    }
  }

  const stateMain = snapshot?.state?.main ?? "STOP";
  const stateSub = snapshot?.state?.sub ?? "SERVO";

  return (
    <main className="shell">
      <div className="aurora aurora-a" />
      <div className="aurora aurora-b" />
      <header className="hero">
        <div>
          <div className="eyebrow">AIRCRAFT CARRIER TOWER</div>
          <h1>地面站 Web 控制台</h1>
          <p>实时串口、黑匣子、调参、分析和飞书同步的统一入口。</p>
        </div>
        <div className="hero-card">
          <div className="hero-status">{status}</div>
          <div className="hero-detail">serial: {snapshot?.runtime?.serial?.com_port ?? "none"}</div>
          <div className="hero-detail">blackbox: {blackbox.received ? "locked" : "waiting"}</div>
          <div className="hero-actions">
            <button onClick={connect} disabled={busy !== null}>connect</button>
            <button onClick={disconnect} disabled={busy !== null}>disconnect</button>
            <button onClick={loadJsonParams} disabled={busy !== null}>load json</button>
            <button onClick={saveJsonParams} disabled={busy !== null}>save json</button>
          </div>
        </div>
      </header>

      <section className="grid metrics">
        <MetricCard label="Main State" value={stateMain} hint={`Sub: ${stateSub}`} />
        <MetricCard label="RX Count" value={String(snapshot?.runtime?.receive?.receive_count ?? 0)} hint={`Errors: ${snapshot?.runtime?.receive?.error_count ?? 0}`} />
        <MetricCard label="Reports" value={`${reports.length}`} hint="analysis index items" />
        <MetricCard label="BlackBox" value={blackbox.received ? "live" : "idle"} hint={`timestamp ${blackbox.timestamp ?? 0}`} />
      </section>

      <section className="grid two-col">
        <article className="panel">
          <div className="panel-title">实时姿态</div>
          <Sparkline values={gyroSeries.roll} />
          <div className="mini-grid">
            <div className="mini">roll {String(blackbox.angle?.[0] ?? 0)}</div>
            <div className="mini">pitch {String(blackbox.angle?.[1] ?? 0)}</div>
            <div className="mini">yaw {String(blackbox.angle?.[2] ?? 0)}</div>
          </div>
        </article>
        <article className="panel">
          <div className="panel-title">连接状态</div>
          <div className="stack">
            <div>Serial: {snapshot?.runtime?.serial?.connected ? "connected" : "offline"}</div>
            <div>Send: {snapshot?.runtime?.send?.running ? "running" : "stopped"}</div>
            <div>Receive: {snapshot?.runtime?.receive?.running ? "running" : "stopped"}</div>
            <div>Logging: {snapshot?.runtime?.receive?.blackbox_logging?.is_logging ? "on" : "off"}</div>
          </div>
        </article>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div className="panel-title">状态与控制</div>
          <div className="chip-row">
            {mainStateOrder.map((item) => (
              <button
                key={item}
                className={item === stateMain ? "chip active" : "chip"}
                onClick={() => patchControl({ main_state: item })}
                disabled={busy !== null}
              >
                {item}
              </button>
            ))}
            {stateMain === "TUNING"
              ? subStateOrder.map((item) => (
                  <button
                    key={item}
                    className={item === stateSub ? "chip active" : "chip"}
                    onClick={() => patchControl({ sub_state: item })}
                    disabled={busy !== null}
                  >
                    {item}
                  </button>
                ))
              : null}
          </div>
        </div>

        <div className="control-grid">
          <label>
            <span>main switch</span>
            <input value={mainSwitch} onChange={(e) => setMainSwitch(Number(e.target.value))} onBlur={() => patchControl({ main_switch: mainSwitch })} />
          </label>
          <label>
            <span>fan speed</span>
            <input type="number" value={fanSpeed} onChange={(e) => setFanSpeed(Number(e.target.value))} onBlur={() => patchControl({ fan_speed: fanSpeed })} />
          </label>
          <button onClick={() => patchControl({ request_save_to_flash: true })} disabled={busy !== null}>save flash</button>
          <button onClick={() => patchControl({ nav_confirm: true })} disabled={busy !== null}>toggle confirm</button>
        </div>
      </section>

      <section className="grid two-col">
        <article className="panel">
          <div className="panel-title">舵面 / 前馈</div>
          <div className="matrix-grid four">
            {servoAngles.map((value, index) => (
              <label key={index}>
                <span>{`servo ${index + 1}`}</span>
                <input
                  type="number"
                  step="0.1"
                  value={value}
                  onChange={(e) => {
                    const next = [...servoAngles];
                    next[index] = Number(e.target.value);
                    setServoAngles(next);
                  }}
                />
              </label>
            ))}
          </div>
          <button onClick={() => patchControl({ servo_angles: servoAngles })} disabled={busy !== null}>apply servo</button>
          <div style={{ height: 12 }} />
          <div className="matrix-grid four">
            {feedforwardValues.map((value, index) => (
              <label key={index}>
                <span>{`ff ${index + 1}`}</span>
                <input
                  type="number"
                  step="0.1"
                  value={value}
                  onChange={(e) => {
                    const next = [...feedforwardValues];
                    next[index] = Number(e.target.value);
                    setFeedforwardValues(next);
                  }}
                />
              </label>
            ))}
          </div>
          <button onClick={() => patchControl({ feedforward_values: feedforwardValues })} disabled={busy !== null}>apply feedforward</button>
        </article>

        <article className="panel">
          <div className="panel-title">曲线预览</div>
          <div className="stack small">
            <div>roll rms {blackbox.angle ? Number(blackbox.angle[0] ?? 0).toFixed(2) : "0.00"}</div>
            <div>pitch rms {blackbox.angle ? Number(blackbox.angle[1] ?? 0).toFixed(2) : "0.00"}</div>
            <div>yaw rms {blackbox.angle ? Number(blackbox.angle[2] ?? 0).toFixed(2) : "0.00"}</div>
          </div>
          <Sparkline values={gyroSeries.pitch} accent="var(--accent2)" />
          <Sparkline values={gyroSeries.yaw} accent="var(--accent3)" />
        </article>
      </section>

      <section className="panel">
        <div className="panel-title">PID Matrix</div>
        <div className="matrix-toolbar">
          <label>
            <span>selected pid</span>
            <input
              type="number"
              min={0}
              max={6}
              value={snapshot?.control?.selected_pid ?? 0}
              onChange={(e) => patchControl({ selected_pid: Number(e.target.value) })}
            />
          </label>
          <label>
            <span>tuning state</span>
            <input
              type="number"
              min={-1}
              max={6}
              value={snapshot?.control?.pid_tuning_state ?? -1}
              onChange={(e) => patchControl({ pid_tuning_state: Number(e.target.value) })}
            />
          </label>
        </div>
        <div className="pid-grid">
          {pidParam.map((row: number[], r: number) => (
            <div key={r} className="pid-row">
              {row.map((value, c) => (
                <input
                  key={`${r}-${c}`}
                  type="number"
                  step="0.01"
                  value={value}
                  onChange={(e) => {
                    const next = pidParam.map((items: number[]) => [...items]);
                    next[r][c] = Number(e.target.value);
                    setPidParam(next);
                  }}
                />
              ))}
            </div>
          ))}
        </div>
        <button onClick={() => patchControl({ pid_param: pidParam })} disabled={busy !== null}>apply pid</button>
      </section>

      <section className="panel">
        <div className="panel-title">Jacobian Matrix</div>
        <div className="pid-grid jacobian">
          {jacobianMatrix.map((row, r) => (
            <div key={r} className="pid-row">
              {row.map((value, c) => (
                <input
                  key={`${r}-${c}`}
                  type="number"
                  step="0.01"
                  value={value}
                  onChange={(e) => {
                    const next = jacobianMatrix.map((items) => [...items]);
                    next[r][c] = Number(e.target.value);
                    setJacobianMatrix(next);
                  }}
                />
              ))}
            </div>
          ))}
        </div>
        <button onClick={() => patchControl({ jacobian_matrix: jacobianMatrix })} disabled={busy !== null}>apply jacobian</button>
      </section>

      <section className="grid two-col">
        <article className="panel">
          <div className="panel-title">分析报告</div>
          <div className="stack">
            <button onClick={runAnalysis} disabled={busy !== null}>run latest analysis</button>
            <div>reports: {reports.length}</div>
            <div>last: {snapshot?.runtime?.analysis?.last_report_path ?? "none"}</div>
            <div className="small-note">reports are loaded on demand to keep control latency low</div>
          </div>
          <div className="report-list">
            {reports.map((report) => (
              <button key={report.path} className="report-item" onClick={() => loadReport(report.path)}>
                <div>{report.created_at}</div>
                <div>{report.source_csv}</div>
              </button>
            ))}
          </div>
        </article>

        <article className="panel">
          <div className="panel-title">Feishu 预研</div>
          <div className="stack small">
            <div>connector: not wired yet</div>
            <div>sync mode: draft export first</div>
            <div>draft: analysis_reports/feishu_drafts</div>
          </div>
          <pre className="code-block">
            {JSON.stringify(activeReport?.correlations ?? snapshot?.runtime?.analysis ?? {}, null, 2)}
          </pre>
        </article>
      </section>
    </main>
  );
}
