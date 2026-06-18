<#
.SYNOPSIS
    VSR 源码包构建工具 - 仅打包源代码（不含运行环境+模型）  # LVBOBO_markdown_BUG

.DESCRIPTION
    与旧版不同，本脚本只打包 Python 源代码文件。
    Python 解释器和 AI 模型由 setup_windows.ps1 自动下载。

    使用方法:
        powershell -ExecutionPolicy Bypass -File scripts\build_minimal_package.ps1

    输出:
        builds\VSR-Source-v1.4.0.7z
#>

param(
    [string]$Version = "1.4.0",
    [string]$OutputDir = "builds"
)

$Green = "Green"; $Yellow = "Yellow"; $Red = "Red"; $Cyan = "Cyan"
function Write-Color($C, $M) { Write-Host $M -ForegroundColor $C }

Clear-Host
Write-Color $Cyan "================================================"
Write-Color $Cyan "  VSR Source Package Builder v$Version"
Write-Color $Cyan "================================================"
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

$ArchiveName = "VSR-Source-v$Version"
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

# Backend Python source only (exclude: models/sam2/ffmpeg/E2FGVI)
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
Get-ChildItem $StageDir -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force

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
Write-Color $Yellow "  3. Setup script auto-installs Python, dependencies, and models"
Write-Host ""
