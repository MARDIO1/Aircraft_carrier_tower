# One-command Web startup

Run this from the project root:

```powershell
uv run python src\launcher.py
```

The launcher:

- reuses an existing backend on `127.0.0.1:8000` if it is already running;
- reuses an existing frontend on `127.0.0.1:3000` if it is already running;
- starts missing services;
- waits for health checks;
- opens `http://127.0.0.1:3000` in the default browser.

If `web/node_modules` is missing, run:

```powershell
cd web
npm install
```
