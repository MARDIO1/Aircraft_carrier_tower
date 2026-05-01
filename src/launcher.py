"""
One-command launcher for the Web ground station.

Run from the repository root:
    uv run python src\\launcher.py
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT_DIR / "web"
BACKEND_URL = "http://127.0.0.1:8000/api/health"
FRONTEND_URL = "http://127.0.0.1:3000"
DETACHED_FLAGS = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


def is_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def wait_url(url: str, timeout_s: float = 45.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status < 500:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def start_backend() -> subprocess.Popen[str] | None:
    if is_port_open(8000):
        print("[launcher] backend already listening on 8000")
        return None
    print("[launcher] starting FastAPI backend")
    return subprocess.Popen(
        [sys.executable, str(ROOT_DIR / "src" / "web_server.py")],
        cwd=str(ROOT_DIR),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=DETACHED_FLAGS,
        text=True,
    )


def start_frontend() -> subprocess.Popen[str] | None:
    if is_port_open(3000):
        print("[launcher] frontend already listening on 3000")
        return None
    if not (WEB_DIR / "node_modules").exists():
        raise RuntimeError("web/node_modules not found. Run: cd web && npm install")
    print("[launcher] starting Next.js frontend")
    return subprocess.Popen(
        ["npm.cmd" if os.name == "nt" else "npm", "run", "dev"],
        cwd=str(WEB_DIR),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=DETACHED_FLAGS,
        text=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Start backend + frontend and open the dashboard.")
    parser.add_argument("--no-open", action="store_true", help="Do not open the browser.")
    parser.add_argument("--exit-after-ready", action="store_true", help="Exit once both services are healthy.")
    args = parser.parse_args()

    processes: list[subprocess.Popen[str]] = []
    try:
        backend = start_backend()
        if backend:
            processes.append(backend)
        if not wait_url(BACKEND_URL, timeout_s=45):
            raise RuntimeError(f"backend did not become healthy: {BACKEND_URL}")

        frontend = start_frontend()
        if frontend:
            processes.append(frontend)
        if not wait_url(FRONTEND_URL, timeout_s=60):
            raise RuntimeError(f"frontend did not become ready: {FRONTEND_URL}")

        print(f"[launcher] ready: {FRONTEND_URL}")
        if not args.no_open:
            webbrowser.open(FRONTEND_URL)
        if args.exit_after_ready:
            return 0

        print("[launcher] press Ctrl+C to stop services started by this launcher")
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[launcher] stopping")
        return 0
    except Exception as exc:
        print(f"[launcher] error: {exc}", file=sys.stderr)
        return 1
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()


if __name__ == "__main__":
    raise SystemExit(main())
