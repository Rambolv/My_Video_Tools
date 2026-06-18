<#
.SYNOPSIS
    VSR Windows 一键安装脚本
    自动下载 Python 运行环境、安装依赖、下载 AI 模型

.DESCRIPTION
    使用方式:
        1. 下载 VSR-Source-v1.4.0.zip 并解压
        2. 右键 setup_windows.ps1 -> "使用 PowerShell 运行"
        3. 等待安装完成
        4. 双击「启动VSR魔改版.cmd」开始使用
#>

$ErrorActionPreference = "Stop"
$ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptPath

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  VSR 魔改版 - Windows 一键安装" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# ── 配置 ──
$PythonVersion = "3.12.9"
$PythonDir = "$ScriptPath\Python"
$RequirementsFile = "$ScriptPath\resources\requirements.txt"

# ── 1. 检查/下载 Python ──
Write-Host "[1/4] 检查 Python 运行环境..." -ForegroundColor Yellow
$pythonExe = "$PythonDir\python.exe"

if (-not (Test-Path $pythonExe)) {
    Write-Host "  -> 下载嵌入式 Python $PythonVersion ..." -ForegroundColor Gray
    $url = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
    $zipPath = "$env:TEMP\python-embed.zip"
    try {
        Invoke-WebRequest -Uri $url -OutFile $zipPath -UseBasicParsing
        Expand-Archive -Path $zipPath -DestinationPath $PythonDir -Force
        Write-Host "  [OK] Python 下载完成" -ForegroundColor Green
    } catch {
        Write-Host "  [ERR] 下载失败: $_" -ForegroundColor Red
        Write-Host "  请手动下载 https://www.python.org/downloads/ 并安装 Python $PythonVersion"
        exit 1
    }
} else {
    Write-Host "  [OK] Python 已就绪" -ForegroundColor Green
}

# ── 2. 安装 pip 依赖 ──
Write-Host "[2/4] 安装 Python 依赖包..." -ForegroundColor Yellow

# 嵌入式 Python 需要先启用 pip
$pythonLib = "$PythonDir\python312._pth"
if (Test-Path $pythonLib) {
    $content = Get-Content $pythonLib -Raw
    if ($content -match "^#import site") {
        $content = $content -replace "^#import site", "import site"
        Set-Content -Path $pythonLib -Value $content
        Write-Host "  -> 已启用 pip 支持" -ForegroundColor Gray
    }
}

# 下载 get-pip.py
$getPip = "$env:TEMP\get-pip.py"
if (-not (Test-Path "$PythonDir\Scripts\pip.exe")) {
    Write-Host "  -> 安装 pip..." -ForegroundColor Gray
    Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $getPip -UseBasicParsing
    & $pythonExe $getPip --no-warn-script-location 2>&1 | Out-Null
}

# 安装依赖
if (Test-Path $RequirementsFile) {
    Write-Host "  -> 安装依赖包（可能需要 10-30 分钟）..." -ForegroundColor Gray
    & $pythonExe -m pip install -r $RequirementsFile --no-warn-script-location 2>&1 | ForEach-Object {
        if ($_ -match "^Collecting|^Installing|^Successfully|^ERROR") { Write-Host "     $_" -ForegroundColor Gray }
    }
    Write-Host "  [OK] 依赖安装完成" -ForegroundColor Green
} else {
    Write-Host "  [WARN] 未找到 requirements.txt" -ForegroundColor Yellow
}

# ── 3. 下载 AI 模型 ──
Write-Host "[3/4] 下载 AI 模型（约 700MB）..." -ForegroundColor Yellow
$downloadScript = "$ScriptPath\scripts\download_models.py"
if (Test-Path $downloadScript) {
    & $pythonExe $downloadScript 2>&1 | ForEach-Object { Write-Host "     $_" }
    Write-Host "  [OK] 模型下载完成" -ForegroundColor Green
} else {
    Write-Host "  [WARN] 未找到模型下载脚本，请手动下载模型" -ForegroundColor Yellow
}

# ── 4. 创建启动脚本 ──
Write-Host "[4/4] 创建启动快捷方式..." -ForegroundColor Yellow
$launchScript = "$ScriptPath\启动VSR魔改版.cmd"
@"
@echo off
chcp 65001 >nul
cd /d "%~dp0resources"
"%~dp0Python\python.exe" gui.py %*
pause
"@ | Set-Content -Path $launchScript -Encoding Default

Write-Host "  [OK] 启动脚本已创建" -ForegroundColor Green

# ── 完成 ──
Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  安装完成！" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  双击「启动VSR魔改版.cmd」开始使用" -ForegroundColor White
Write-Host ""
