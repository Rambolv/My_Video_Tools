<#
.SYNOPSIS
    我的AI影音工具百宝箱 - 源码包构建工具（仅打包源代码，不含运行环境+模型）

.DESCRIPTION
    本脚本只打包 Python 源代码文件，不含运行环境和 AI 模型。
    Python 解释器和 AI 模型由 setup_windows.ps1 自动下载。

    使用方法:
        powershell -ExecutionPolicy Bypass -File scripts\build_minimal_package.ps1

    输出:
        builds\AI-Media-Toolbox-Source-v1.4.0.7z
#>

param(
    [string]$Version = "1.4.0",
    [string]$OutputDir = "builds"
)

$Green = "Green"; $Yellow = "Yellow"; $Red = "Red"; $Cyan = "Cyan"
function Write-Color($C, $M) { Write-Host $M -ForegroundColor $C }

Clear-Host
Write-Color $Cyan "====================================================="
Write-Color $Cyan "  我的AI影音工具百宝箱 - Source Package Builder v$Version"
Write-Color $Cyan "====================================================="
Write-Host ""

$ScriptPath = $PSScriptRoot
$ProjectRoot = Resolve-Path "$ScriptPath/.."
Set-Location $ProjectRoot
Write-Color $Green "[OK] Root: $ProjectRoot"

$7zPath = Get-Command "7z" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
if (-not $7zPath) { $7zPath = "C:\Program Files\7-Zip\7z.exe" }
if (-not (Test-Path $7zPath)) { Write-Color $Red "[ERR] 7-Zip not found"; exit 1 }
Write-Color $Green "[OK] 7-Zip: $7zPath"

$OutputPath = "$ProjectRoot/$OutputDir"
New-Item -ItemType Directory -Force -Path $OutputPath | Out-Null

$ArchiveName = "AI-Media-Toolbox-Source-v$Version"
$ArchiveFile = "$OutputPath/$ArchiveName.7z"
Write-Color $Cyan "Package: $ArchiveName.7z"
Remove-Item $ArchiveFile -Force -ErrorAction SilentlyContinue
Write-Host ""
Write-Color $Yellow "Packaging source code only..."

# Create staging dir
$StageDir = "$env:TEMP\vsr-package-$Version"
if (Test-Path $StageDir) { Remove-Item $StageDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $StageDir | Out-Null
New-Item -ItemType Directory -Force -Path "$StageDir\resources\backend" | Out-Null
Write-Host "  -> Copying source files..."

# ── Backend Python source only (exclude: models/sam2/ffmpeg/E2FGVI) ──
$backendItems = @("main.py", "config.py", "__init__.py", "inpaint", "tools", "scenedetect", "interface")
foreach ($item in $backendItems) {
    $src = "$ProjectRoot\resources\backend\$item"
    $dst = "$StageDir\resources\backend\$item"
    if (Test-Path $src) {
        if (Test-Path $src -PathType Container) {
            Copy-Item $src $dst -Recurse -Force -ErrorAction SilentlyContinue
        } else {
            Copy-Item $src $dst -Force -ErrorAction SilentlyContinue
        }
    }
}

# ── 🆕 AI 音频工作室 ──
Copy-Item "$ProjectRoot\resources\backend\audio_studio" "$StageDir\resources\backend\audio_studio" -Recurse -Force -ErrorAction SilentlyContinue
# 移除音频 studio 内的模型缓存（太大，由 download_models.py 下载）
if (Test-Path "$StageDir\resources\backend\audio_studio\ace_checkpoints") {
    Remove-Item "$StageDir\resources\backend\audio_studio\ace_checkpoints" -Recurse -Force -ErrorAction SilentlyContinue
}

Copy-Item "$ProjectRoot\resources\backend\config" "$StageDir\resources\backend\config" -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item "$ProjectRoot\resources\ui" "$StageDir\resources\ui" -Recurse -Force
Copy-Item "$ProjectRoot\resources\gui.py" "$StageDir\resources\gui.py" -Force
Copy-Item "$ProjectRoot\resources\requirements.txt" "$StageDir\resources\requirements.txt" -Force
Copy-Item "$ProjectRoot\config\config.json" "$StageDir\config\config.json" -Force -ErrorAction SilentlyContinue
Copy-Item "$ProjectRoot\scripts" "$StageDir\scripts" -Recurse -Force
Copy-Item "$ProjectRoot\docs" "$StageDir\docs" -Recurse -Force
Copy-Item "$ProjectRoot\README.md" "$StageDir\README.md" -Force
Copy-Item "$ProjectRoot\README_en.md" "$StageDir\README_en.md" -Force
Copy-Item "$ProjectRoot\LICENSE" "$StageDir\LICENSE" -Force
Copy-Item "$ProjectRoot\MEMORY.md" "$StageDir\MEMORY.md" -Force -ErrorAction SilentlyContinue

# ── 🆕 vendor 第三方 AI 项目源码（不含模型权重） ──
New-Item -ItemType Directory -Force -Path "$StageDir\vendor\ai_audio" | Out-Null

# VoxCPM2 源码（排除 models/ 权重目录）
Copy-Item "$ProjectRoot\vendor\ai_audio\voxcpm2\voxcpm" "$StageDir\vendor\ai_audio\voxcpm2\voxcpm" -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item "$ProjectRoot\vendor\ai_audio\voxcpm2\assets" "$StageDir\vendor\ai_audio\voxcpm2\assets" -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item "$ProjectRoot\vendor\ai_audio\voxcpm2\conf" "$StageDir\vendor\ai_audio\voxcpm2\conf" -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item "$ProjectRoot\vendor\ai_audio\voxcpm2\examples" "$StageDir\vendor\ai_audio\voxcpm2\examples" -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item "$ProjectRoot\vendor\ai_audio\voxcpm2\scripts" "$StageDir\vendor\ai_audio\voxcpm2\scripts" -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item "$ProjectRoot\vendor\ai_audio\voxcpm2\pyproject.toml" "$StageDir\vendor\ai_audio\voxcpm2\pyproject.toml" -Force -ErrorAction SilentlyContinue
Copy-Item "$ProjectRoot\vendor\ai_audio\voxcpm2\README.md" "$StageDir\vendor\ai_audio\voxcpm2\README.md" -Force -ErrorAction SilentlyContinue
Copy-Item "$ProjectRoot\vendor\ai_audio\voxcpm2\README_zh.md" "$StageDir\vendor\ai_audio\voxcpm2\README_zh.md" -Force -ErrorAction SilentlyContinue
Copy-Item "$ProjectRoot\vendor\ai_audio\voxcpm2\LICENSE" "$StageDir\vendor\ai_audio\voxcpm2\LICENSE" -Force -ErrorAction SilentlyContinue

# ACE-Step 源码（排除 checkpoints/ 权重目录）
Copy-Item "$ProjectRoot\vendor\ai_audio\ace_step\acestep" "$StageDir\vendor\ai_audio\ace_step\acestep" -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item "$ProjectRoot\vendor\ai_audio\ace_step\assets" "$StageDir\vendor\ai_audio\ace_step\assets" -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item "$ProjectRoot\vendor\ai_audio\ace_step\docs" "$StageDir\vendor\ai_audio\ace_step\docs" -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item "$ProjectRoot\vendor\ai_audio\ace_step\examples" "$StageDir\vendor\ai_audio\ace_step\examples" -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item "$ProjectRoot\vendor\ai_audio\ace_step\scripts" "$StageDir\vendor\ai_audio\ace_step\scripts" -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item "$ProjectRoot\vendor\ai_audio\ace_step\.env.example" "$StageDir\vendor\ai_audio\ace_step\.env.example" -Force -ErrorAction SilentlyContinue
Copy-Item "$ProjectRoot\vendor\ai_audio\ace_step\pyproject.toml" "$StageDir\vendor\ai_audio\ace_step\pyproject.toml" -Force -ErrorAction SilentlyContinue
Copy-Item "$ProjectRoot\vendor\ai_audio\ace_step\requirements.txt" "$StageDir\vendor\ai_audio\ace_step\requirements.txt" -Force -ErrorAction SilentlyContinue

# 清理 __pycache__
Get-ChildItem $StageDir -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Get-ChildItem $StageDir -Recurse -Directory -Filter "*.egg-info" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# Create archive
Write-Host "  -> Creating archive..."
$7zArgs = "a -t7z -mx=7 -mfb=64 -md=64m -ms=on -mmt=on `"$ArchiveFile`" `"$StageDir\*`""
$process = Start-Process -FilePath $7zPath -ArgumentList $7zArgs -NoNewWindow -Wait -PassThru
Remove-Item $StageDir -Recurse -Force -ErrorAction SilentlyContinue

if ($process.ExitCode -eq 0) {
    $size = (Get-Item $ArchiveFile).Length / 1MB
    Write-Color $Green "[OK] Package created!"
    Write-Host "     File: $ArchiveName.7z"
    Write-Host "     Size: $([math]::Round($size, 1)) MB"
    Write-Host "     Path: $ArchiveFile"
} else {
    Write-Color $Red "[ERR] 7-Zip exited with code $($process.ExitCode)"
}

Write-Host ""
Write-Color $Yellow "Next Steps:"
Write-Color $Yellow "  1. Upload $ArchiveName.7z to GitHub Releases (tag: v$Version)"
Write-Color $Yellow "  2. Users: download -> unzip -> right-click setup_windows.ps1 -> Run with PowerShell"
Write-Color $Yellow "  3. Setup script auto-installs Python, dependencies, and all AI models"
Write-Host ""
Write-Color $Cyan "Note: VoxCPM2 and ACE-Step model weights (~14GB total) are downloaded"
Write-Color $Cyan "      separately by setup_windows.ps1 and download_models.py scripts."
Write-Host ""
