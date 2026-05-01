"use client";

import { useEffect, useRef, useState, useCallback } from "react";

type Snapshot = Record<string, any>;

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const WS_BASE = API_BASE.replace(/^http/, "ws");

const mainStateOrder = ["STOP", "TOWER", "AUTO", "TUNING", "DATA"] as const;

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
    throw new Error(`Cannot reach backend ${API_BASE}`);
  }
  const text = await res.text();
  const body = text ? JSON.parse(text) : {};
  if (!res.ok) throw new Error(body.detail ?? body.message ?? res.statusText);
  return body;
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

export default function Page() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [status, setStatus] = useState("connecting...");
  const [busy, setBusy] = useState<string | null>(null);
  const [ports, setPorts] = useState<{ device: string; description: string }[]>([]);
  const [selectedPort, setSelectedPort] = useState("CH340");

  // 参数表单
  const [fanSpeed, setFanSpeed] = useState(0);
  const [motorPwm, setMotorPwm] = useState(1500);
  const [motorStep, setMotorStep] = useState(1000);
  const [mainSwitch, setMainSwitch] = useState(0);
  const [servoAngles, setServoAngles] = useState<number[]>([0, 0, 0, 0]);
  const [feedforwardValues, setFeedforwardValues] = useState<number[]>([0, 0, 0, 0]);
  const [pidParam, setPidParam] = useState<number[][]>(makeMatrix(7, 6, 0));
  const [jacobianMatrix, setJacobianMatrix] = useState<number[][]>(makeMatrix(3, 4, 0));

  const wsRef = useRef<WebSocket | null>(null);

  // 初始快照
  useEffect(() => {
    (async () => {
      try {
        const snap = await readJson("/api/snapshot");
        setSnapshot(snap);
        const form = applySnapshotToForm(snap);
        setFanSpeed(form.fanSpeed);
        setMainSwitch(form.mainSwitch);
        setServoAngles(form.servoAngles);
        setFeedforwardValues(form.feedforwardValues);
        setMotorPwm(form.fanSpeed ?? 1500);
        setPidParam(form.pidParam);
        setJacobianMatrix(form.jacobianMatrix);
        setStatus("ready");
      } catch (e) {
        setStatus(`offline: ${(e as Error).message}`);
      }
    })();
    (async () => {
      try {
        const data = await readJson("/api/ports");
        setPorts(data.ports ?? []);
      } catch {}
    })();
  }, []);

  // WebSocket 高频更新 hex + 状态
  useEffect(() => {
    const socket = new WebSocket(`${WS_BASE}/ws`);
    wsRef.current = socket;
    socket.onopen = () => setStatus("live");
    socket.onclose = () => setStatus("disconnected");
    socket.onerror = () => setStatus("socket error");
    socket.onmessage = (event) => {
      try {
        setSnapshot(JSON.parse(event.data));
      } catch {}
    };
    return () => socket.close();
  }, []);

  const patchControl = useCallback(
    async (payload: Record<string, unknown>) => {
      setBusy(Object.keys(payload)[0] ?? "update");
      try {
        const data = await readJson("/api/control", { method: "POST", body: JSON.stringify(payload) });
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
      } catch (e) {
        setStatus((e as Error).message);
      } finally {
        setBusy(null);
      }
    },
    []
  );

  const connect = async () => {
    setBusy("connect");
    try {
      const data = await readJson("/api/connect", {
        method: "POST",
        body: JSON.stringify({ com_port: selectedPort === "CH340" ? null : selectedPort, auto_keyword: "CH340" }),
      });
      setSnapshot((prev) => ({ ...(prev ?? {}), runtime: { ...(prev?.runtime ?? {}), serial: data } }));
      setStatus(data.connected ? `connected ${data.com_port ?? ""}` : `connect failed ${data.error ?? ""}`);
    } catch (e) {
      setStatus((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const disconnect = async () => {
    setBusy("disconnect");
    try {
      const data = await readJson("/api/disconnect", { method: "POST", body: "{}" });
      setSnapshot((prev) => ({ ...(prev ?? {}), runtime: { ...(prev?.runtime ?? {}), serial: data } }));
      setStatus("disconnected");
    } catch (e) {
      setStatus((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const loadJsonParams = async () => {
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
    } catch (e) {
      setStatus((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const saveJsonParams = async () => {
    setBusy("save-json");
    try {
      await readJson("/api/params/save", { method: "POST", body: "{}" });
      setStatus("json saved");
    } catch (e) {
      setStatus((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const stateMain = snapshot?.state?.main ?? "STOP";
  const txHex = snapshot?.runtime?.send?.hex ?? "";
  const rxHex = snapshot?.runtime?.receive?.last_rx_hex ?? "";
  const rxCount = snapshot?.runtime?.receive?.receive_count ?? 0;
  const rxErrors = snapshot?.runtime?.receive?.error_count ?? 0;
  const csvLogging = snapshot?.runtime?.receive?.blackbox_logging?.is_logging ?? false;
  const csvCount = snapshot?.runtime?.receive?.blackbox_logging?.record_count ?? 0;
  const serialConnected = snapshot?.runtime?.serial?.connected ?? false;
  const comPort = snapshot?.runtime?.serial?.com_port ?? "none";

  return (
    <main className="shell">
      {/* ========== 第1段: 连接区 ========== */}
      <section className="panel">
        <div className="panel-title">连接与控制</div>
        <div className="connect-bar">
          <div className="connect-left">
            <label className="port-label">
              <span>COM</span>
              <select
                value={selectedPort}
                onChange={(e) => setSelectedPort(e.target.value)}
                className="port-select"
              >
                <option value="CH340">auto CH340</option>
                {ports.map((p) => (
                  <option key={p.device} value={p.device}>
                    {p.device} {p.description}
                  </option>
                ))}
              </select>
            </label>
            <button onClick={connect} disabled={busy !== null || serialConnected}>
              connect
            </button>
            <button onClick={disconnect} disabled={busy !== null || !serialConnected}>
              disconnect
            </button>
          </div>
          <div className="connect-right">
            <button onClick={loadJsonParams} disabled={busy !== null}>
              load json
            </button>
            <button onClick={saveJsonParams} disabled={busy !== null}>
              save json
            </button>
          </div>
        </div>
        <div className="status-bar">
          <span className={`status-dot ${serialConnected ? "on" : "off"}`} />
          <span>{status}</span>
          <span className="status-sep">|</span>
          <span>COM: {comPort}</span>
          <span className="status-sep">|</span>
          <span>RX: {rxCount}</span>
          <span className="status-sep">|</span>
          <span>CSV: {csvLogging ? `recording ${csvCount}` : "idle"}</span>
        </div>
      </section>

      {/* ========== 第2段: 状态按钮 ========== */}
      <section className="panel">
        <div className="chip-row">
          {mainStateOrder.map((item) => {
            const isActive = item === stateMain;
            const isData = item === "DATA";
            let disabled = busy !== null;
            // DATA 按钮特殊处理：先切 STOP 再切 DATA
            const label = isData && !isActive && stateMain !== "STOP" ? "STOP→DATA" : item;
            return (
              <button
                key={item}
                className={isActive ? "chip active" : "chip"}
                disabled={disabled}
                onClick={async () => {
                  if (isData && stateMain !== "STOP") {
                    await patchControl({ main_state: "STOP" });
                    await new Promise((r) => setTimeout(r, 200));
                  }
                  patchControl({ main_state: item });
                }}
              >
                {label}
              </button>
            );
          })}
        </div>
      </section>

      {/* ========== 电机 PWM 脉冲 (int16, 0-10000) ========== */}
      <section className="panel">
        <div className="panel-title">电机 PWM 脉冲 (int16)</div>
        <div className="matrix-grid single">
          <label>
            <span>motor</span>
            <input
              type="number"
              step={motorStep}
              min={0}
              max={10000}
              value={motorPwm}
              onChange={(e) => {
                const v = Number(e.target.value);
                if (!isNaN(v)) setMotorPwm(Math.max(0, Math.min(10000, v)));
              }}
            />
          </label>
        </div>
        <div className="matrix-grid single" style={{ marginTop: 6 }}>
          <label>
            <span>step</span>
            <input
              type="number"
              step={1}
              min={1}
              max={1000}
              value={motorStep}
              onChange={(e) => {
                const v = Number(e.target.value);
                if (!isNaN(v)) setMotorStep(Math.max(1, Math.min(1000, v)));
              }}
            />
          </label>
        </div>
        <button onClick={() => patchControl({ fan_speed: motorPwm })} disabled={busy !== null}>
          apply motor pwm
        </button>
      </section>

      {/* ========== 第3段: 收发原始 hex 监控 ========== */}
      <section className="grid two-col">
        <article className="panel hex-panel">
          <div className="panel-title">TX 发送原始数据 (HEX)</div>
          <pre className="hex-display">{txHex || "等待发送..."}</pre>
        </article>
        <article className="panel hex-panel">
          <div className="panel-title">RX 接收原始数据 (HEX) — {rxCount} frames, {rxErrors} errors</div>
          <pre className="hex-display">{rxHex || "等待接收..."}</pre>
        </article>
      </section>

      {/* ========== 第4段: 参数调节 ========== */}
      <section className="panel">
        <div className="panel-title">舵面 / 前馈</div>
        <div className="matrix-grid four">
          {servoAngles.map((value, index) => (
            <label key={`s${index}`}>
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
        <button onClick={() => patchControl({ servo_angles: servoAngles })} disabled={busy !== null}>
          apply servo
        </button>
        <div style={{ height: 12 }} />
        <div className="matrix-grid four">
          {feedforwardValues.map((value, index) => (
            <label key={`ff${index}`}>
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
        <button onClick={() => patchControl({ feedforward_values: feedforwardValues })} disabled={busy !== null}>
          apply feedforward
        </button>
      </section>

      <section className="panel">
        <div className="panel-title">PID Matrix</div>
        <div className="pid-grid">
          {pidParam.map((row, r) => (
            <div key={r} className="pid-row">
              {row.map((value, c) => (
                <input
                  key={`${r}-${c}`}
                  type="number"
                  step="0.01"
                  value={value}
                  onChange={(e) => {
                    const next = pidParam.map((items) => [...items]);
                    next[r][c] = Number(e.target.value);
                    setPidParam(next);
                  }}
                />
              ))}
            </div>
          ))}
        </div>
        <button onClick={() => patchControl({ pid_param: pidParam })} disabled={busy !== null}>
          apply pid
        </button>
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
        <button onClick={() => patchControl({ jacobian_matrix: jacobianMatrix })} disabled={busy !== null}>
          apply jacobian
        </button>
      </section>

      {/* 折叠区: 分析报告 */}
      <section className="panel">
        <details>
          <summary className="panel-title" style={{ cursor: "pointer", display: "inline" }}>
            Analysis Reports (折叠)
          </summary>
          <div className="stack" style={{ marginTop: 10 }}>
            <div>last: {snapshot?.runtime?.analysis?.last_report_path ?? "none"}</div>
            <pre className="code-block">
              {JSON.stringify(snapshot?.runtime?.analysis ?? {}, null, 2)}
            </pre>
          </div>
        </details>
      </section>
    </main>
  );
}