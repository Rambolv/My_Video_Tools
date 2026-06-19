# VSR Modded Edition - Video Subtitle Remover  <!-- LVBOBO_markdown_BUG - 新增英文README -->

![Python](https://img.shields.io/badge/Python-3.12+-blue)
![PySide6](https://img.shields.io/badge/PySide6-6.9.0-green)
![License](https://img.shields.io/badge/License-Apache%202-red)

[简体中文](README.md) | English

> **VSR Modded Edition** — A deep fork of VSR v1.4.0 with extensive feature enhancements and UI refactoring.
> Also integrates and enhances all features from the original author's VSE pre-built packages (`vse-windows-*.7z`).
> GPU-accelerated hard-coded subtitle removal tool with both GUI and CLI interfaces.

---

## 📋 Table of Contents

- [Project Origin](#-project-origin)
- [Features](#-features)
- [Quick Start](#-quick-start)
- [UI Preview](#-ui-preview)
- [Usage Guide](#-usage-guide)
- [Architecture](docs/ARCHITECTURE_EN.md)
- [Feature Design](docs/FEATURES_EN.md)
- [Changelog](docs/CHANGELOG_EN.md)
- [FAQ](#-faq)

---

## 📖 Project Origin

This project is a deep fork of [**YaoFANGUK/video-subtitle-remover**](https://github.com/YaoFANGUK/video-subtitle-remover) (VSR v1.4.0), with extensive feature enhancements and UI refactoring.
It also integrates and enhances all features from the original author's VSE pre-built packages (`vse-windows-*.7z`), including Multi-Sweep mode, watermark template matching, adaptive masking, and more.

### Original Project Info

| Item | Description |
|------|-------------|
| **Original Author** | [YaoFANGUK](https://github.com/YaoFANGUK) |
| **Original Repository** | https://github.com/YaoFANGUK/video-subtitle-remover |
| **Original Version** | v1.4.0 |
| **Original License** | Apache License 2.0 |

### New / Improved Features in This Fork

> This modded edition fully integrates and enhances all advanced features from the original author's VSE pre-built packages (Multi-Sweep mode, watermark template matching, etc.), while adding major upgrades such as ProPainter/E2FGVI inpainting engines, PP-OCRv5 detection models, SAM2 segmentation models, and more.

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

## � Usage Guide

### 🎬 Video Subtitle Removal — Basic Workflow

#### 1️⃣ Import a Video

- Click the **「Open」** button and select a video file (supports MP4, FLV, WMV, AVI, and other common formats)
- **Multi-select** is supported — add multiple videos to the task list at once
- The video automatically plays in the left preview area, and each file's status appears in the task list

#### 2️⃣ Locate Subtitle Position

- Drag the **progress slider** below the video to quickly browse and find frames where subtitles appear
- **Keyboard shortcuts**:
  - `←` / `→`: Jump ±1 second
  - `Ctrl` + `←` / `Ctrl` + `→`: Jump ±5 seconds
  - `Shift` + `←` / `Shift` + `→`: Jump ±1 frame

#### 3️⃣ Select the Removal Area

- **Right-click** on the video to open the context menu
- Select **「Add Selection」** → **Left-click and drag** over the subtitle area to draw a green selection box
- **Multiple selections** are supported: select different subtitle or watermark areas (e.g., top-left logo + bottom subtitles)
- **Adjust selection**: Drag the edges of an existing box to resize, or drag inside to move
- **Delete selection**: Right-click on a box → "Delete Selection", or press `Delete`
- Selections are stored as **relative coordinates** and persist across frame changes

> 💡 **Tip**: If subtitle positions are fixed, select once and the area stays active across all frames — no need to re-select.

#### 4️⃣ Configure Removal Parameters

Configure the core settings in the right-side function panel:

| Parameter | Description |
|-----------|-------------|
| **Inpaint Mode** | Choose AI inpainting engine: STTN (fast), ProPainter (high quality), E2FGVI (extreme), LaMa (cartoon-friendly), OpenCV (traditional) |
| **Detection Model** | Choose OCR detection: PP-OCRv4/v5 (text detection), SAM2 (segmentation, for irregular watermarks) |
| **Processing Depth** | 0-100 continuous slider, real-time parameter interpolation. Higher = better quality but slower & more VRAM |
| **HW Acceleration** | Enable GPU (CUDA) acceleration, disable to use CPU |
| **Concurrency** | Process multiple videos simultaneously (1-8). Options exceeding VRAM are auto-marked with red ⚠️ |

#### 5️⃣ Set A-B Sections (Optional)

To process only a **specific segment** of the video (instead of the full length):

- Navigate to the start frame, press `[` to mark the start point
- Navigate to the end frame, press `]` to mark the end point
- White segment markers appear below the progress bar
- Press `\` (backslash) to delete the current segment
- Multiple A-B segments are supported; if none are set, the entire video is processed

#### 6️⃣ Start Processing

- Click the **「Start」** button to begin processing
- During processing, you can monitor in real-time:
  - **Left preview**: Side-by-side comparison of original (left) vs. inpainted (right) frames
  - **「Output Log」Tab**: Detailed processing log
  - **「Task List」Tab**: Progress percentage for each task
- Click **「Stop」** to terminate processing at any time
- Output files are saved in the original video directory (or a custom output directory), with `_no_sub` appended to the filename

---

### 🎯 Advanced Watermark Detection

Expand the "Custom Watermark" collapsible section to use these advanced features:

#### Watermark Template Capture

1. Click **「Capture Watermark」** to enter capture mode
2. **Left-click and drag** on the video to frame the watermark area (blue dashed box)
3. Release the mouse to confirm — the template is saved automatically
4. Subsequent processing will use feature matching against the template

#### Toggle Options

| Switch | Description |
|--------|-------------|
| **Aggressive Mode** | Mask dilation +50%, for stubborn watermark residue (red) |
| **Force Full-Frame Mask** | Force mask generation on ALL frames within your selected area, bypassing OCR detection (orange) |
| **Temporal Median Filter** | Cross-frame median filtering on mask areas to eliminate color shift/deformation/flickering text (blue) |

#### Multi-Sweep Mode

For **rapidly changing/deforming AI-generated logo watermarks**:

1. Click the **「Multi-Sweep」** button to enable (turns green)
2. Set **iteration count** (1-10 rounds); 2-3 recommended, 4-5 for heavy deformation
3. Each pass: deformation-adaptive mask → RGB density clustering → model inference → bright residue suppression → adaptive blending
4. Each pass uses the previous output as input, progressively removing stubborn artifacts
5. Processing time = iterations × single-pass time; output filename includes iteration info

---

### 📝 Subtitle Extraction

#### One-Click Extraction

1. After opening a video, select the **extraction mode** in the right panel:
   - **Row mode**: Group by Y-axis, suitable for horizontal subtitles (default)
   - **Column mode**: Group by X-axis, suitable for vertical text
   - **Float mode**: Position-based clustering for dynamic/floating watermarks
2. Click **「Extract」**
3. Results appear in the right preview area and the bottom "Subtitle Text" tab

#### Export Subtitles

- **「Export TXT」**: Export as plain text (.txt), no timestamps
- **「Export SRT」**: Export as standard subtitle file (.srt) with timestamps

#### Joint Proofreading

Extract with multiple OCR models and merge for highest accuracy:

1. Expand **「Joint Proofreading」** section
2. Select three different detection models (e.g., PP-OCRv4 Server, PP-OCRv5 Server, SAM2-Base)
3. Click **「Execute」** — the system runs all three models and merges results
4. Results are displayed automatically

---

### ⚙️ Advanced Settings

Click **「⚙ Advanced Settings」** to open the advanced settings page, where you can adjust:

- **Subtitle Detection**: Detection threshold, minimum text height, mask expansion, etc.
- **STTN Inpainting**: Frame interval, reference frames, dilation factor, etc.
- **ProPainter**: Subgrid size, step size, downsampling factor, etc.
- **System Settings**: Output directory, language, theme (light/dark), update check, etc.

---

### 🧠 VRAM Management

Expand the "VRAM Estimation & Monitoring" collapsible section:

- **GPU VRAM Info**: Auto-detects and displays GPU model and total VRAM
- **Current Config Estimate**: Real-time VRAM estimation based on selected models and concurrency
- **VRAM Monitoring**: When enabled, automatically collects GPU memory peaks during processing
- **Model VRAM Reference Table**: Built-in baselines for 14 models, real collected values preferred
- **Concurrency Red-Flag**: Options exceeding VRAM are auto-marked with red ⚠️

---

## �📁 Project Structure

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
