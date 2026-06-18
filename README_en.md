# VSR - Video Subtitle Remover

![Python](https://img.shields.io/badge/Python-3.12+-blue)
![PySide6](https://img.shields.io/badge/PySide6-6.9.0-green)
![License](https://img.shields.io/badge/License-Apache%202-red)

[简体中文](README.md) | English

> **AI-powered hard-coded subtitle removal tool** — GPU-accelerated with both GUI and CLI interfaces.

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

This project is a deep fork of [**YaoFANGUK/video-subtitle-remover**](https://github.com/YaoFANGUK/video-subtitle-remover) (VSR v1.1.0), with extensive feature enhancements and UI refactoring.

### Original Project Info

| Item | Description |
|------|-------------|
| **Original Author** | [YaoFANGUK](https://github.com/YaoFANGUK) |
| **Original Repository** | https://github.com/YaoFANGUK/video-subtitle-remover |
| **Original Version** | v1.1.0 |
| **Original License** | Apache License 2.0 |

### New / Improved Features in This Fork

- **Processing Depth Slider**: 0-100 continuous adjustment, real-time interpolation of all model parameters
- **Subtitle Extraction**: Full pipeline OCR extraction via PaddleOCR, supports row/column/float modes
- **Joint Proofreading**: Three different OCR models extract and combine results for best accuracy
- **VRAM Monitoring**: Passive collection of real GPU memory data with smart red-flag warnings
- **Collapsible Function UI**: qfluentwidgets redesign with persistent collapse state
- **Help Button System**: `?` button next to every control, click/hover for detailed explanation
- **Draggable Splitter Panels**: QSplitter implementation, all areas freely resizable
- **VRAM Reference Table**: Built-in VRAM baselines for 14 models + OOM danger markers
- **E2FGVI VRAM Warning**: Auto red alert when GPU VRAM < 48GB
- **Concurrent Task Red-Flag**: Options exceeding VRAM capacity auto-marked with red ⚠️
- **Auto Word Wrap & Adaptive Buttons**: Text overflow auto-wraps, buttons self-adapt to size

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

### Windows Pre-built Packages

Download the appropriate version from the Releases page:

| Package | Environment | Compatible GPU |
|---------|-------------|----------------|
| `vsr-windows-cuda-12.6.7z` | CUDA 12.6 | NVIDIA Compute 5.0-8.9 |
| `vsr-windows-cuda-11.8.7z` | CUDA 11.8 | NVIDIA Compute 3.5-8.9 |
| `vsr-windows-directml.7z` | DirectML | Non-NVIDIA GPUs |
| `vsr-windows-cpu.7z` | CPU | Universal |

### Run

```bash
# Extract and double-click
使用兼容模式运行.cmd

# Or via command line
cd resources
../Python/python.exe gui.py
```

### Run from Source

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
A: Model files are stored in split format. They will auto-merge on first run. Ensure sufficient disk space.

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
