# VSR Modded Edition - Changelog  <!-- LVBOBO_markdown_BUG - 新增英文文档 -->

[简体中文](CHANGELOG.md) | English

## v1.4.0 (Current)

### ✨ New Features

- **Video Enhancement System**: Super-Resolution (Real-ESRGAN) + waifu2x Anime SR + Frame Interpolation (RIFE)
- **Enhancement Pipeline**: SR→FI or FI→SR processing order, any combination supported
- **Three ncnn Backends**: Real-ESRGAN ncnn, RIFE ncnn, waifu2x ncnn standalone backends
- **VRAM Active Scheduling**: Real-time VRAM pressure monitoring + adaptive batch size + dynamic GPU GC
- **Multi-Task Phased Scheduling**: Subtitle/SR/FI models load phase-by-phase to prevent VRAM stacking OOM
- **Dedicated VRAM Lock**: Prevents Windows WDDM spillover to shared memory, toggleable
- **GPU Real-Time Monitor Dialog**: nvidia-smi polling with process ranking by GPU compute load
- **STTN Pipeline Optimization**: 30~50% speed boost, 50% VRAM reduction
- **Multi-Sweep Pipeline Optimization**: Inference 3x→2x, import improvement, window reduction
- **AI Navigation Pages**: AI Video Generation, AI Audio, Video Editor — three independent pages
- **Unified Donation Dialog**: Centralized donation entry across all pages
- **Config Profile Management**: `config_profile.py` for saving/switching configurations
- **Resource Manager**: `resource_manager.py` unified model download & path management
- **Watermark Tracker**: `watermark_tracker.py` cross-frame watermark position prediction & tracking
- **Theme Change Listener**: `theme_listener.py` real-time system light/dark theme switching
- **Video Merge Tool**: `merge_video.py` multi-segment video merging
- **Model Compatibility Layer**: `model_compat.py` handles model version compatibility
- **CLI Args Handler**: `args_handler.py` command-line argument parsing
- **Distribution Builder**: `makedist.py` automated release package building

- **Processing Depth Slider**: 0-100 continuous drag, real-time interpolation of all model parameters (mask dilation, timeline, reference frames, etc.)
- **Subtitle Extraction**: Full pipeline based on PaddleOCR, supports Row/Column/Floating three modes
- **Joint Proofreading**: Three different OCR models extract separately, then merge for best results
- **VRAM Passive Monitoring**: Auto-collects GPU VRAM peaks during normal workflow, writes to `vram_records.json`
- **VRAM Estimation Reference Table**: Baseline values for all models, real collected values preferred, OOM marked ☠️
- **Concurrent Task VRAM Red-Flag**: Concurrency options exceeding VRAM auto-marked with red ⚠️
- **E2FGVI VRAM Warning**: Detects GPU VRAM when selecting E2FGVI, shows warning if < 48GB
- **Help Button System**: `?` button next to every control, click for detailed popup, hover for tooltip
- **Collapsible Function Cards**: Persistent collapse state (saved to config.json)
- **Draggable Splitter**: Main interface uses QSplitter, all areas draggable to resize
- **Auto Word Wrap**: Output log/subtitle text auto-wraps, buttons self-adapt to size

### 🎨 UI Improvements

- Function area re-layout: Left video preview + bottom tabs, right two function zones
- Visual hierarchy: SectionHeader (blue border), sub-section indent + left border line
- Slider handle enlarged: 8px → 18px circular blue handle
- Three subtitle extraction mode dropdowns: Row/Column/Floating
- Left Tab "Subtitle Text" shows SRT format, right preview shows plain text
- Export TXT / Export SRT dual buttons

### 🔧 Technical Improvements

- Original `OptionsConfigItem` processing depth changed to `RangeConfigItem(0-100)` continuous range
- `SubtitleExtractor` module: Full pipeline subtitle extraction
- `SubtitleDetect.find_subtitle_frame_no()` passes mock object to avoid None crash
- Thread-safe UI updates: Using signal-slot pattern instead of direct cross-thread calls
- `_SimpleCollapsible` refactored: Persistent expand/collapse state

### 🐛 Bug Fixes

- Fixed `PrimaryPushButton::setText` cross-thread call missing metamethod
- Fixed `find_subtitle_frame_no(sub_remover=None)` causing AttributeError
- Fixed `on_scroll_change` method incorrectly merged into `_open_advanced_settings`
- Fixed joint proofreading model name matching (spaces vs hyphens)

---

## v1.3.x (Historical)

### Key Features
- PaddleOCR PP-OCRv4/v5 subtitle text detection
- SAM2 watermark detection model support (Tiny/Small/Base/Large)
- ProPainter high-quality video inpainting
- STTN temporal inpainting (Auto + Det modes)
- LaMa inpainting (optimized for animation)
- E2FGVI high-quality temporal inpainting
- OpenCV traditional inpainting (fast mode)
- Watermark template matching (capture, color propagation, power sweep)
- Concurrent task processing (1-8 tasks)
- Hardware acceleration toggle (CUDA/ONNX)
- Multi-language interface support
- Version update check

---

## v1.2.x

### Key Features
- Basic subtitle detection & removal pipeline
- GUI interface (PySide6 + qfluentwidgets)
- Video preview & area selection
- Task list management
- Scene cut detection

---

## v1.1.0 (Initial Release)

### Key Features
- AI-based video hard subtitle removal
- GPU acceleration support (CUDA 11.8 / 12.6)
- Cross-platform: Windows/macOS/Linux
- Docker deployment support
- Pre-built package distribution (CPU/DirectML/CUDA variants)
