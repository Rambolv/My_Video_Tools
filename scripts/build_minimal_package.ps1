<#
.SYNOPSIS
    VSR Minimal Package Builder
    Creates a minimal Windows pre-compiled package without AI models.
    Models will be auto-downloaded on first launch.

.DESCRIPTION
    This script creates a minimal VSR package by:
    1. Bundling the Python interpreter + all pip dependencies
    2. Bundling the source code (without model files)
    3. Excluding: models/, large design assets, test files, dev artifacts
    4. Outputting a .7z archive for GitHub Releases

    Prerequisites:
    - 7-Zip installed (https://7-zip.org/)
    - Run from project root directory

    Usage:
        powershell -ExecutionPolicy Bypass -File scripts\build_minimal_package.ps1

    Output:
        builds\VSR-Minimal-v1.4.0-windows.7z
#>

param(
    [Parameter(Mandatory = $false)]
    [string]$Version = "1.4.0",

    [Parameter(Mandatory = $false)]
    [string]$OutputDir = "builds",

    [Parameter(Mandatory = $false)]
    [switch]$SkipPython = $false
)

# ── Colors ──
$Green = "Green"
$Yellow = "Yellow"
$Red = "Red"
$Cyan = "Cyan"

function Write-Color($Color, $Message) {
    Write-Host $Message -ForegroundColor $Color
}

# ── Header ──
Clear-Host
Write-Color $Cyan "╔══════════════════════════════════════════════╗"
Write-Color $Cyan "║     VSR Minimal Package Builder v$Version    ║"
Write-Color $Cyan "╚══════════════════════════════════════════════╝"
Write-Host ""

# ── Determine project root ──
$ScriptPath = $PSScriptRoot
$ProjectRoot = Resolve-Path "$ScriptPath\.."
Set-Location $ProjectRoot
Write-Color $Green "📂 Project Root: $ProjectRoot"

# ── Check dependencies ──
$7zPath = "C:\Program Files\7-Zip\7z.exe"
if (-not (Test-Path $7zPath)) {
    $7zPath = "C:\Program Files\7-Zip\7z.exe"
}
if (-not (Test-Path $7zPath)) {
    $7zPath = Get-Command "7z" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
}
if (-not $7zPath) {
    Write-Color $Red "❌ 7-Zip not found. Please install 7-Zip first (https://7-zip.org/)"
    Write-Color $Yellow "   Or ensure 7z.exe is in your PATH"
    exit 1
}
Write-Color $Green "✅ 7-Zip: $7zPath"

# ── Check Python directory exists ──
$PythonDir = "$ProjectRoot\Python"
if (-not (Test-Path $PythonDir)) {
    Write-Color $Red "❌ Python directory not found: $PythonDir"
    Write-Color $Yellow "   Please ensure the bundled Python environment exists."
    exit 1
}
Write-Color $Green "✅ Python Environment: $PythonDir"

# ── Create output directory ──
$OutputPath = "$ProjectRoot\$OutputDir"
New-Item -ItemType Directory -Force -Path $OutputPath | Out-Null
Write-Color $Green "📁 Output Directory: $OutputPath"

# ── Package name ──
$ArchiveName = "VSR-Minimal-v${Version}-windows"
$ArchiveFile = "$OutputPath\${ArchiveName}.7z"
Write-Color $Cyan "📦 Package: ${ArchiveName}.7z"

# ── Build file list ──
Write-Color $Yellow "`n📋 Building file list..."

# Files/directories to include
$IncludeDirs = @(
    "Python",
    "resources"
)

# Files in project root
$IncludeFiles = @(
    "使用兼容模式运行.cmd",
    "Debug-进入虚拟环境.cmd",
    "README.md",
    "README_en.md",
    "LICENSE"
)

# Patterns to EXCLUDE from resources/
$ExcludePatterns = @(
    # Model files - will be auto-downloaded
    "resources\backend\models\*",
    # E2FGVI (third-party, large)
    "resources\backend\E2FGVI\*",
    # Logs
    "configs\logs\*",
    # Test files
    "resources\test\*",
    # Design assets (large GIFs)
    "resources\design\*.gif",
    "resources\design\*.jpg",
    "resources\design\*.pdf",
    # VRAM records
    "resources\backend\config\vram_records.json",
    # Watermark template images
    "resources\backend\models\watermark_templates\*",
    # Backups
    "BACKUP_*",
    # Build artifacts
    "_test_output\*",
    "builds\*",
    "opt\*",
    # Git
    ".git\*",
    ".gitignore",
    # Dev configs
    ".claude\*",
    "configs\*",
    # FFmpeg binaries
    "resources\backend\ffmpeg\*",
    # SAM2 model (large)
    "resources\backend\sam2\*"
)

# ── Start packaging ──
Write-Color $Yellow "`n🔨 Creating minimal package (this may take a while)...`n"

# Temporarily rename models dir to speed up (exclude from scan)
$ModelsDir = "$ProjectRoot\resources\backend\models"
$ModelsBackup = "$ProjectRoot\resources\backend\models_backup"
if (Test-Path $ModelsDir) {
    Rename-Item -Path $ModelsDir -NewName "models_backup" -Force
    Write-Color $Yellow "   Temporarily excluded models directory"
}

try {
    # Build 7z command arguments
    $7zArgs = @(
        "a",                                      # Add to archive
        "-t7z",                                   # 7z format
        "-mx=5",                                  # Compression level (5=normal)
        "-mfb=64",                                # Number of fast bytes
        "-md=32m",                                # Dictionary size
        "-ms=on",                                 # Solid archive
        "-mmt=on",                                # Multi-threading
        "`"$ArchiveFile`"",                        # Output file
        "-xr!`$RECYCLE.BIN",                      # Exclude recycle bin
        "-xr!Thumbs.db",                          # Exclude thumbs
        "-xr!.DS_Store",                          # Exclude macOS files
        "-xr!__pycache__",                        # Exclude Python cache
        "-xr!*.pyc",                              # Exclude compiled Python
        "-xr!*.pyo",                              # Exclude optimized Python
        "-xr!*.egg-info",                         # Exclude egg info
        "-xr!*.log",                              # Exclude logs
        "-xr!vram_records.json",                  # Exclude VRAM records
        "-xr!*.pth",                              # Exclude model files (safety)
        "-xr!*.onnx"                              # Exclude ONNX models (safety)
    )

    # Add include paths
    foreach ($dir in $IncludeDirs) {
        if (Test-Path $dir) {
            $7zArgs += "`"$dir`""
        }
    }
    foreach ($file in $IncludeFiles) {
        if (Test-Path $file) {
            $7zArgs += "`"$file`""
        }
    }

    # Execute 7z
    $arguments = $7zArgs -join " "
    $process = Start-Process -FilePath $7zPath -ArgumentList $arguments -NoNewWindow -Wait -PassThru

    if ($process.ExitCode -eq 0) {
        # Get file size
        $fileSize = (Get-Item $ArchiveFile).Length / 1GB
        Write-Color $Green "`n✅ Package created successfully!"
        Write-Color $Cyan "   📦 $ArchiveName.7z"
        Write-Color $Cyan "   💾 Size: $([math]::Round($fileSize, 2)) GB"
        Write-Color $Cyan "   📁 Path: $ArchiveFile"
    } else {
        Write-Color $Red "`n❌ 7-Zip exited with code $($process.ExitCode)"
    }
}
catch {
    Write-Color $Red "`n❌ Error: $_"
}
finally {
    # Restore models directory
    if (Test-Path "$ProjectRoot\resources\backend\models_backup") {
        Rename-Item -Path "$ProjectRoot\resources\backend\models_backup" -NewName "models" -Force
        Write-Color $Yellow "   Restored models directory"
    }
}

Write-Color $Yellow "`n📋 Next Steps:"
Write-Color $Yellow "   1. Upload ${ArchiveName}.7z to GitHub Releases"
Write-Color $Yellow "   2. Upload model files to GitHub Releases (models-v1.0 tag)"
Write-Color $Yellow "   3. Test the minimal package on a clean Windows machine`n"
