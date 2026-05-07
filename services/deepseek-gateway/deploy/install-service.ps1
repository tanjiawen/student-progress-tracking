# DeepSeek TUI Runtime API — Windows 服务安装脚本
# 必须以管理员身份运行 PowerShell
# Usage:  powershell -ExecutionPolicy Bypass -File .\install-service.ps1
#         powershell -ExecutionPolicy Bypass -File .\install-service.ps1 -WithBridge

param(
    [switch]$WithBridge = $false
)

$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "DeepSeek TUI Service Installer"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " DeepSeek TUI Runtime API — Installer" -ForegroundColor Cyan
Write-Host " Platform: Windows x64" -ForegroundColor Cyan
if ($WithBridge) { Write-Host " Mode: API + Exam Bridge" -ForegroundColor Cyan }
else { Write-Host " Mode: API only (use -WithBridge for exam bridge)" -ForegroundColor Cyan }
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── Check admin ────────────────────────────────────────────────────
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "ERROR: This script must be run as Administrator." -ForegroundColor Red
    Write-Host "Right-click PowerShell → Run as Administrator, then re-run." -ForegroundColor Yellow
    exit 1
}

# ── Locate bundled binaries ─────────────────────────────────────────
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BundledDeepseek = Join-Path $ScriptDir "bin\windows-x64\deepseek.exe"
$BundledDeepseekTui = Join-Path $ScriptDir "bin\windows-x64\deepseek-tui.exe"
$InstallDir = "C:\Program Files\DeepSeek"

if ((Test-Path $BundledDeepseek) -and (Test-Path $BundledDeepseekTui)) {
    Write-Host "[*] Bundled binaries detected — installing to $InstallDir ..." -ForegroundColor Green
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    Copy-Item $BundledDeepseek "$InstallDir\deepseek.exe" -Force
    Copy-Item $BundledDeepseekTui "$InstallDir\deepseek-tui.exe" -Force
    Write-Host "    deepseek.exe      installed" -ForegroundColor Green
    Write-Host "    deepseek-tui.exe  installed" -ForegroundColor Green
} else {
    Write-Host "[!] Bundled binaries not found at bin\windows-x64\" -ForegroundColor Yellow
    Write-Host "    Ensure deploy\bin\windows-x64\ contains deepseek.exe and deepseek-tui.exe" -ForegroundColor Yellow
    Write-Host "    Download from: https://github.com/Hmbown/DeepSeek-TUI/releases" -ForegroundColor Yellow
    exit 1
}

# ── Add to PATH ─────────────────────────────────────────────────────
$currentPath = [Environment]::GetEnvironmentVariable("PATH", "Machine")
if ($currentPath -notlike "*$InstallDir*") {
    Write-Host "[*] Adding $InstallDir to system PATH..." -ForegroundColor Green
    [Environment]::SetEnvironmentVariable("PATH", "$currentPath;$InstallDir", "Machine")
    $env:PATH = "$env:PATH;$InstallDir"
    Write-Host "    Done (restart shell for full effect)" -ForegroundColor Green
}

# ── Verify binary ───────────────────────────────────────────────────
Write-Host "[*] Verifying binary..." -ForegroundColor Green
$version = & "$InstallDir\deepseek.exe" --version 2>&1
Write-Host "    Version: $version" -ForegroundColor Green

# ── API Key setup ──────────────────────────────────────────────────
$ConfigDir = "$env:USERPROFILE\.deepseek"
$ConfigFile = "$ConfigDir\config.toml"

if (-not (Test-Path $ConfigDir)) { New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null }

if (-not (Test-Path $ConfigFile)) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Yellow
    Write-Host "  API Key Required" -ForegroundColor Yellow
    Write-Host "========================================" -ForegroundColor Yellow
    $apiKey = Read-Host "Paste your DeepSeek API key (sk-...)"
    if ($apiKey) {
        @"
api_key = "$apiKey"
provider = "deepseek"
model = "deepseek-v4-pro"
"@ | Out-File -FilePath $ConfigFile -Encoding utf8
        Write-Host "    Config saved to $ConfigFile" -ForegroundColor Green
    } else {
        Write-Host "    Skipped. Set manually: notepad $ConfigFile" -ForegroundColor Yellow
    }
} else {
    Write-Host "[*] Config already exists at $ConfigFile" -ForegroundColor Green
}

# ── Create Windows Service (via nssm or sc) ─────────────────────────
# We use sc.exe to create a simple Windows service.
$ServiceName = "DeepSeekAPI"

Write-Host "[*] Installing Windows service '$ServiceName'..." -ForegroundColor Green

# Remove old service if exists
sc.exe stop $ServiceName 2>$null
sc.exe delete $ServiceName 2>$null
Start-Sleep -Seconds 1

# Create service
$binPath = "`"$InstallDir\deepseek.exe`" serve --http --host 127.0.0.1 --port 7878 --workers 4"
sc.exe create $ServiceName binPath= $binPath start= auto DisplayName= "DeepSeek TUI Runtime API"
sc.exe description $ServiceName "DeepSeek TUI Agent Runtime API Server — localhost:7878"
sc.exe start $ServiceName

Start-Sleep -Seconds 3
$svcStatus = sc.exe query $ServiceName
Write-Host $svcStatus

# ── Smoke test ──────────────────────────────────────────────────────
Write-Host ""
Write-Host "[*] Smoke testing API..." -ForegroundColor Green
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:7878/health" -TimeoutSec 5 -UseBasicParsing
    Write-Host "    Health check: $($response.StatusCode) OK" -ForegroundColor Green
} catch {
    Write-Host "    Health check FAILED: $_" -ForegroundColor Red
    Write-Host "    Check Event Viewer → Windows Logs → Application for errors." -ForegroundColor Yellow
}

# ── Install Exam Bridge (optional) ──────────────────────────────────
if ($WithBridge) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  Installing Exam Bridge" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan

    # Check Python
    $python = Get-Command python3 -ErrorAction SilentlyContinue
    if (-not $python) { $python = Get-Command python -ErrorAction SilentlyContinue }
    if (-not $python) {
        Write-Host "ERROR: python3 not found. Install from https://python.org" -ForegroundColor Red
    } else {
        $BridgePy = Join-Path $ScriptDir "exam-bridge.py"
        $BridgeKey = "brg-" + (-join ((48..57) + (97..122) | Get-Random -Count 16 | ForEach-Object { [char]$_ }))
        Write-Host "    Bridge API key: $BridgeKey (save this!)" -ForegroundColor Green

        # Create bridge service
        $BridgeServiceName = "DeepSeekExamBridge"
        sc.exe stop $BridgeServiceName 2>$null
        sc.exe delete $BridgeServiceName 2>$null
        Start-Sleep -Seconds 1

        $bridgeBinPath = "`"$($python.Source)`" `"$BridgePy`""
        $bridgeEnv = "DEEPSEEK_API_BASE=http://127.0.0.1:7878 BRIDGE_HOST=127.0.0.1 BRIDGE_PORT=8888 BRIDGE_API_KEY=$BridgeKey"

        sc.exe create $BridgeServiceName binPath= "$bridgeBinPath" start= auto DisplayName= "DeepSeek Exam Bridge"
        sc.exe description $BridgeServiceName "DeepSeek Exam Bridge — localhost:8888"

        # For env vars, use a wrapper batch file
        $BridgeWrapper = "$InstallDir\exam-bridge-start.bat"
        @"
@echo off
set DEEPSEEK_API_BASE=http://127.0.0.1:7878
set BRIDGE_HOST=127.0.0.1
set BRIDGE_PORT=8888
set BRIDGE_API_KEY=$BridgeKey
$($python.Source) "$BridgePy"
"@ | Out-File -FilePath $BridgeWrapper -Encoding ascii

        sc.exe delete $BridgeServiceName 2>$null
        Start-Sleep -Seconds 1
        sc.exe create $BridgeServiceName binPath= "`"$BridgeWrapper`"" start= auto DisplayName= "DeepSeek Exam Bridge"

        sc.exe start $BridgeServiceName
        Start-Sleep -Seconds 2

        try {
            $bResp = Invoke-WebRequest -Uri "http://127.0.0.1:8888/health" -TimeoutSec 3 -UseBasicParsing
            Write-Host "    Exam Bridge health: $($bResp.Content)" -ForegroundColor Green
        } catch {
            Write-Host "    Exam Bridge health FAILED" -ForegroundColor Red
        }
    }
}

# ── Final summary ───────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Installation Complete" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Running services:"
Write-Host "  DeepSeek API:  http://127.0.0.1:7878  (health: /health)"
if ($WithBridge) {
    Write-Host "  Exam Bridge:   http://127.0.0.1:8888  (health: /health)"
}
Write-Host ""
Write-Host "Manage services:"
Write-Host "  sc.exe query DeepSeekAPI"
Write-Host "  sc.exe stop DeepSeekAPI"
Write-Host "  sc.exe start DeepSeekAPI"
Write-Host ""
Write-Host "Logs: Event Viewer → Windows Logs → Application"
Write-Host "Config: $ConfigFile"
Write-Host ""
Write-Host "To test: curl http://127.0.0.1:7878/health"
