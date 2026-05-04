# Windows one-click deployment

From a fresh Windows machine, run from the project root:

```powershell
deploy_windows.bat
```

The script will:

- install `uv` if it is missing;
- use `uv` to provide Python 3.13;
- sync Python dependencies from `uv.lock`;
- install Node.js LTS with `winget` if `node`/`npm` are missing;
- install frontend dependencies from `web/package-lock.json`;
- install the Chromium runtime used by Playwright;
- start the dashboard with `uv run python src\launcher.py`.

Useful options:

```powershell
deploy_windows.bat -NoLaunch
deploy_windows.bat -SkipWeb
deploy_windows.bat -NoPlaywright
```

If Windows blocks scripts, use `deploy_windows.bat`; it launches PowerShell with a process-local execution policy bypass.

If `winget` is not available, install Node.js LTS from https://nodejs.org/ and run the script again.
