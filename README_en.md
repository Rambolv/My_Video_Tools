# VSR Modded Edition - Video Subtitle Remover  <!-- LVBOBO_markdown_BUG - 新增英文README -->

![Python](https://img.shields.io/badge/Python-3.12+-blue)
![PySide6](https://img.shields.io/badge/PySide6-6.9.0-green)
![License](https://img.shields.io/badge/License-Apache%202-red)

[简体中文](README.md) | English

> **VSR Modded Edition** — A deep fork of VSR v1.4.0 with extensive feature enhancements and UI refactoring.
> GPU-accelerated hard-coded subtitle removal tool with both GUI and CLI interfaces.

---

## 📋 Table of Contents

- [Project Origin](#-project-origin)
- [Features](#-features)
- [Quick Start](#-quick-start)
- [UI Preview](#-ui-preview)
- [Architecture](docs/ARCHITECTURE_EN.md)
- [Feature Design](docs/FEATURES_EN.md)
- [Changelog](docs/CHANGELOG_EN.md)
- [FAQ](#-faq)

---

## 📖 Project Origin

This project is a deep fork of [**YaoFANGUK/video-subtitle-remover**](https://github.com/YaoFANGUK/video-subtitle-remover) (VSR v1.4.0), with extensive feature enhancements and UI refactoring.

### Original Project Info

| Item | Description |
|------|-------------|
| **Original Author** | [YaoFANGUK](https://github.com/YaoFANGUK) |
| **Original Repository** | https://github.com/YaoFANGUK/video-subtitle-remover |
| **Original Version** | v1.4.0 |
| **Original License** | Apache License 2.0 |

### New / Improved Features in This Fork

#### 🚀 Core Algorithm Enhancements
- **Processing Depth Slider**: 0-100 continuous adjustment, real-time interpolation of ALL model parameters (mask dilation, timeline, reference frames, etc.)
- **Multi-Sweep Mode**: Aggressive removal for AI-generated rapidly changing/deforming logo watermarks — deformation-adaptive mask + RGB clustering + strong temporal filtering + multi-pass progressive removal
- **Watermark Template Matching**: Template capture, rotation/scale matching, feature matching, color propagation, power sweep (temporal difference), force region inpaint
- **ProPainter / E2FGVI Engines**: Added ProPainter (high quality/high VRAM) and E2FGVI (CVPR 2022, 48GB+ VRAM) inpainting algorithms
- **SAM2 Detection Models**: Added SAM2-Tiny/Small/Base/Large segmentation models alongside PaddleOCR
- **PP-OCRv5 Support**: Upgraded to PP-OCRv5 Server/Mobile for latest OCR accuracy

#### 📝 Subtitle Extraction System
- **Full Pipeline Subtitle Extraction**: Automated PaddleOCR-based extraction
- **Three Extraction Modes**: Row mode / Column mode / Floating subtitle mode
- **Joint Proofreading**: Three different OCR models extract separately, then merge and deduplicate for best accuracy
- **Multi-Format Export**: Plain text (.txt) / Standard subtitle (.srt)

#### 🖥️ Complete UI/UX Overhaul
- **GUI Framework Upgrade**: Migrated from PySimpleGUI to PySide6 + qfluentwidgets (Fluent Design)
- **Draggable Splitter Panels**: QSplitter implementation, all areas freely resizable
- **Collapsible Function Cards**: Persistent collapse state (saved to config.json)
- **Help Button System**: `?` button next to every control, click for detailed popup, hover for tooltip
- **Processing Depth Visualization**: Slider displays real-time interpolated parameters for all models
- **Startup Dialog**: Project info, hardware requirements & recommendations, donation QR code
- **Window Position Memory**: Auto-save/restore window position and size

#### 🧠 Smart VRAM Management
- **VRAM Passive Monitoring**: Automatically collects GPU memory peaks during normal workflow
- **VRAM Estimation Reference Table**: Built-in baselines for 14 models, real collected values preferred
- **Concurrent Task VRAM Red-Flag**: Concurrency options exceeding VRAM are auto-marked with red ⚠️
- **E2FGVI VRAM Warning**: Auto red alert when GPU VRAM < 48GB
- **Color-Coded System**: ≥95% red / ≥85% orange / ≥70% yellow / <70% green

#### 🔧 Technical Architecture
- **Scene Detection**: Frame-difference-based scene cut detection for optimal interval grouping
- **Hardware Acceleration Layer**: Unified CUDA / ONNX acceleration interface
- **FFmpeg CLI Wrapper**: Video codec, audio merge, format conversion
- **Process Manager**: Unified child process lifecycle management (multiprocessing)
- **Thread-Safe UI Updates**: Signal-slot mechanism replacing direct cross-thread calls
- **Split Model Auto-Merge**: Large model files stored split, auto-merged on first run (fsplit)
- **Advanced Settings Page**: Fine-grained parameter tuning for detection/STTN/ProPainter
- **Version Update Service**: Auto-check for new GitHub releases
- **Multi-Language Support**: 简体中文 / English / 日本語 / 한국어 / Tiếng Việt / Español
- **Theme Switching**: Light/Dark theme toggle
- **Auto Model Download**: AI models (~700MB) auto-download from GitHub Releases on first launch
- **One-Click Setup**: `setup_windows.ps1` handles Python runtime + dependencies + models automatically

---

## ✨ Features

### 🎬 Video Subtitle & Watermark Removal

| Feature | Description |
|---------|-------------|
| **AI Inpainting** | 6 inpaint engines: STTN, ProPainter, E2FGVI, LaMa, OpenCV |
| **Subtitle Detection** | PP-OCRv4/v5, SAM2 — 8 detection models available |
| **Processing Depth** | 0-100 continuous slider, interpolates all model parameters |
| **Watermark Detection** | Template matching, color propagation, power sweep, region inpaint |
| **Concurrent Processing** | 1-8 parallel tasks with auto VRAM red-flag warning |
| **VRAM Monitoring** | Passive real-time GPU memory collection with smart recommendations |

### 📝 Subtitle Extraction

| Feature | Description |
|---------|-------------|
| **One-Click Extract** | Auto-detect and OCR all subtitles |
| **Three Modes** | Row mode / Column mode / Floating subtitle mode |
| **Joint Proofreading** | Three OCR models combine for best results |
| **Export Formats** | Plain text (.txt) / Standard subtitle (.srt) |

### 🖥 UI Features

- **Draggable Splitter Panels** — All areas freely resizable
- **Collapsible Sections** — Persistent state across restarts
- **Help Button System** — `?` button on every control
- **VRAM Reference Table** — 14 model baselines + real collected values
- **Smart Red-Flag** — Auto warning when config exceeds VRAM
- **Multi-language Support** — 简体中文, English, 日本語 and more

---

## 🚀 Quick Start

### 📦 Source Package (Recommended, only 0.3MB)

Download `VSR-Source-v1.4.0.7z` from [Releases](https://github.com/Rambolv/My_Video_Tools/releases)

| Feature | Description |
|---------|-------------|
| 🚀 **Ultra Light** | Only 0.3MB — pure Python source code |
| 🔧 **One-Click Setup** | Run `setup_windows.ps1` to configure everything automatically |
| 📥 **Auto-Download** | Python runtime + pip dependencies + AI models (~700MB) all auto-downloaded |
| 🎯 **Ready to Use** | After setup, double-click `启动VSR魔改版.cmd` to start |

**Installation Steps:**

```powershell
# 1. Extract the downloaded .7z file
# 2. Right-click scripts/setup_windows.ps1 → "Run with PowerShell"
# 3. Wait for setup to complete (auto-downloads Python + deps + models)
# 4. Double-click 「启动VSR魔改版.cmd」to launch
```

### Run from Source (Manual)

For users who already have Python 3.12+:

```bash
# 1. Create virtual environment
python -m venv venv
# Windows
venv\Scripts\activate

# 2. Install dependencies
pip install -r resources/requirements.txt

# 3. Run
cd resources
python gui.py
```

### Docker

```bash
# CUDA 11.8 (NVIDIA 10/20/30 series)
docker run -it --name vsr --gpus all eritpchy/video-subtitle-remover:1.4.0-cuda11.8 \
  python backend/main.py -i /input/video.mp4 -o /output/video_no_sub.mp4

# CUDA 12.6 (NVIDIA 40 series)
docker run -it --name vsr --gpus all eritpchy/video-subtitle-remover:1.4.0-cuda12.6 \
  python backend/main.py -i /input/video.mp4 -o /output/video_no_sub.mp4
```

---

## 🖥 UI Preview

```
┌───────────────────────────────────┬─────────────────────────────┐
│         Video Preview Area        │   Subtitle Removal Panel    │
│  ┌─────────────────────────────┐  │   ┃ Core Settings          │
│  │                             │  │   Inpaint [STTN-Auto]  [?] │
│  │      Video Display          │  │   Detect  [PP-OCRv4]   [?] │
│  │                             │  │   Depth   [===slider===]   │
│  └─────────────────────────────┘  │   ┃ Performance            │
│  ┌─────────────────────────────┐  │   HW Accel [Switch]   [?]  │
│  │ 📋 Tasks │ 📝 Output Log    │  │   Concurrency [Combo]  [?] │
│  │ │ 📄 Subtitle Text (Tabs)  │  │   ▶ Watermark Detection    │
│  └─────────────────────────────┘  │   ▶ VRAM Estimation       │
│                                   │   [Open][Start][Stop][⚙]  │
│       Draggable Splitter          ├────────────────────────────┤
│                                   │   Subtitle Extraction      │
│                                   │   [Extract] Mode:[Row ▼]   │
│                                   │   [Export TXT][Export SRT] │
│                                   │   ▶ Joint Proofreading    │
└───────────────────────────────────┴────────────────────────────┘
```

---

## 📁 Project Structure

```
resources/
├── gui.py                  # GUI entry point
├── backend/                # Backend logic
│   ├── main.py             # Subtitle removal core
│   ├── config.py           # Global configuration
│   ├── inpaint/            # Inpainting algorithms
│   │   ├── propainter/     # ProPainter
│   │   ├── sttn_auto/      # STTN Auto
│   │   └── ...
│   └── tools/              # Utility modules
│       ├── subtitle_detect.py    # Subtitle detection
│       ├── subtitle_extractor.py # Subtitle extraction
│       ├── vram_estimator.py     # VRAM estimation
│       ├── vram_monitor.py       # VRAM monitoring
│       └── ...
├── ui/                     # UI modules
│   ├── home_interface.py   # Home page
│   ├── setting_interface.py # Settings panel
│   ├── advanced_setting_interface.py # Advanced settings
│   └── component/          # Reusable components
├── config/                 # Configuration files
└── models/                 # AI model files
```

> For detailed technical documentation, see [docs/ARCHITECTURE_EN.md](docs/ARCHITECTURE_EN.md)

---

## ❓ FAQ

**Q: "Model file not found" error?**
A: If using the source package, run `scripts/setup_windows.ps1` first to complete installation.
   AI models (~700MB) will auto-download from GitHub Releases on first launch.
   Ensure network connectivity and sufficient disk space.
   If auto-download fails, manually run `python scripts/download_models.py` to retry.

**Q: GPU VRAM insufficient?**
A: Lower the "Processing Depth" slider, reduce concurrent tasks, or choose lightweight models (PP-OCRv4 Mobile + STTN).

**Q: E2FGVI won't run?**
A: E2FGVI requires 48GB+ VRAM. A red warning will appear if your GPU VRAM is insufficient. Consider using ProPainter instead.

**Q: Subtitle extraction returns no results?**
A: Try switching extraction modes (Row/Column/Float), or change detection model (PP-OCRv5 Server has highest accuracy).

---

## 📄 License

This project is open-sourced under the [Apache License 2.0](resources/LICENSE).

**Original Project**: [YaoFANGUK/video-subtitle-remover](https://github.com/YaoFANGUK/video-subtitle-remover)
