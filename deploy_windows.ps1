param(
    [switch]$SkipWeb,
    [switch]$NoLaunch,
    [switch]$NoPlaywright
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-WarnLine {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Test-Command {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Add-PathIfExists {
    param([string]$Path)
    if ($Path -and (Test-Path -LiteralPath $Path) -and ($env:Path -notlike "*$Path*")) {
        $env:Path = "$Path;$env:Path"
    }
}

function Refresh-ToolPath {
    Add-PathIfExists (Join-Path $env:USERPROFILE ".local\bin")
    Add-PathIfExists (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links")
    Add-PathIfExists (Join-Path $env:ProgramFiles "nodejs")
}

function Configure-UvStorage {
    param([string]$ProjectRoot)
    $env:UV_CACHE_DIR = Join-Path $ProjectRoot ".uv-cache"
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $ProjectRoot ".uv-python"
}

function Install-Uv {
    if (Test-Command "uv") {
        Write-Ok "uv found: $((Get-Command uv).Source)"
        return
    }

    Write-Step "Installing uv"
    $installer = "https://astral.sh/uv/install.ps1"
    Invoke-Expression (Invoke-RestMethod $installer)
    Refresh-ToolPath

    if (-not (Test-Command "uv")) {
        throw "uv was installed, but it is not available in PATH. Open a new terminal and run deploy_windows.bat again."
    }
    Write-Ok "uv installed"
}

function Install-Node {
    if (Test-Command "node" -and Test-Command "npm") {
        Write-Ok "Node.js found: $(node --version), npm: $(npm --version)"
        return
    }

    Write-Step "Installing Node.js LTS"
    if (-not (Test-Command "winget")) {
        throw "Node.js is missing and winget is not available. Install Node.js LTS from https://nodejs.org/, then run this script again."
    }

    winget install --id OpenJS.NodeJS.LTS --exact --silent --accept-package-agreements --accept-source-agreements
    Refresh-ToolPath

    if (-not (Test-Command "node") -or -not (Test-Command "npm")) {
        throw "Node.js was installed, but node/npm is not available in PATH. Open a new terminal and run deploy_windows.bat again."
    }
    Write-Ok "Node.js installed: $(node --version), npm: $(npm --version)"
}

function Run-Checked {
    param(
        [string]$Title,
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$WorkingDirectory
    )

    Write-Step $Title
    Push-Location $WorkingDirectory
    try {
        & $FilePath @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "$Title failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }
}

function Ensure-Python313 {
    Write-Step "Checking Python 3.13"
    & uv python find 3.13 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Ok "Python 3.13 is available to uv"
        return
    }

    Run-Checked `
        -Title "Installing Python 3.13 with uv" `
        -FilePath "uv" `
        -Arguments @("python", "install", "3.13") `
        -WorkingDirectory $RootDir
}

if ($PSVersionTable.Platform -and $PSVersionTable.Platform -ne "Win32NT") {
    throw "This deployment script is for Windows."
}

$RootDir = Split-Path -Parent $PSCommandPath
Set-Location $RootDir
Refresh-ToolPath
Configure-UvStorage $RootDir

Write-Host "Aircraft Carrier Tower Windows deployment" -ForegroundColor White
Write-Host "Project root: $RootDir"
Write-Host "uv cache: $env:UV_CACHE_DIR"

Install-Uv

Ensure-Python313

Run-Checked `
    -Title "Syncing Python dependencies from uv.lock" `
    -FilePath "uv" `
    -Arguments @("sync", "--locked") `
    -WorkingDirectory $RootDir

if (-not $SkipWeb) {
    Install-Node

    $WebDir = Join-Path $RootDir "web"
    if (-not (Test-Path -LiteralPath $WebDir)) {
        throw "web directory not found: $WebDir"
    }

    if (Test-Path -LiteralPath (Join-Path $WebDir "package-lock.json")) {
        Run-Checked `
            -Title "Installing web dependencies with npm ci" `
            -FilePath "npm" `
            -Arguments @("ci") `
            -WorkingDirectory $WebDir
    }
    else {
        Run-Checked `
            -Title "Installing web dependencies with npm install" `
            -FilePath "npm" `
            -Arguments @("install") `
            -WorkingDirectory $WebDir
    }

    if (-not $NoPlaywright) {
        Run-Checked `
            -Title "Installing Playwright browser runtime" `
            -FilePath "npx" `
            -Arguments @("playwright", "install", "chromium") `
            -WorkingDirectory $WebDir
    }
}
else {
    Write-WarnLine "Skipping web dependency installation."
}

Write-Step "Deployment complete"
Write-Ok "Python environment is ready."
if (-not $SkipWeb) {
    Write-Ok "Web environment is ready."
}

if (-not $NoLaunch) {
    Write-Step "Starting dashboard"
    Write-Host "Press Ctrl+C in the launcher window to stop services started by it."
    & uv run python "src\launcher.py"
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Run later with:"
Write-Host "  uv run python src\launcher.py"
