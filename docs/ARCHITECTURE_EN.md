# My AI Media Toolbox - Architecture  <!-- LVBOBO_markdown_BUG -->

[简体中文](ARCHITECTURE.md) | English

## 1. Project Overview

**My AI Media Toolbox** (based on VSR v1.4.0) is an AI-powered media processing toolkit with GPU acceleration, supporting both GUI (PySide6 + qfluentwidgets) and command-line interfaces.

- **Version**: 1.4.0
- **License**: Apache 2.0
- **Original Repository**: https://github.com/YaoFANGUK/video-subtitle-remover
- **Python**: 3.12+
- **GUI Framework**: PySide6 6.9.0 + qfluentwidgets 1.7.7

---

## 2. Overall Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Presentation Layer                    │
│  ┌────────────────┐  ┌────────────────────────────────┐  │
│  │   Home Page     │  │    Advanced Settings Page       │  │
│  │  (home_interface)│  │  (advanced_setting_interface)   │  │
│  └───────┬─────────┘  └──────────────┬─────────────────┘  │
│          │                           │                    │
│  ┌───────┴───────────────────────────┴─────────────────┐  │
│  │            Setting Interface (setting_interface)     │  │
│  │     FuncCard / HelpButton / SettingRow (func_card)  │  │
│  └──────────────────────┬──────────────────────────────┘  │
└─────────────────────────┼────────────────────────────────┘
                          │
┌─────────────────────────┼────────────────────────────────┐
│              Business Logic Layer                         │
│  ┌──────────────────────┴──────────────────────────────┐  │
│  │              SubtitleRemover (main.py)               │  │
│  │  Pipeline: Detect → Group → Inpaint → Output        │  │
│  └──┬─────────┬──────────┬──────────┬─────────────────┘  │
│     │         │          │          │                    │
│  ┌──┴──┐  ┌───┴───┐  ┌──┴───┐  ┌──┴───┐                │
│  │Detect│  │Inpaint │  │Extract│  │VRAM  │                │
│  │      │  │Models  │  │Subtitle│  │Monitor│              │
│  └──┬──┘  └───┬───┘  └──┬───┘  └──┬───┘                │
│     │         │         │          │                    │
└─────┼─────────┼─────────┼──────────┼────────────────────┘
      │         │         │          │
┌─────┼─────────┼─────────┼──────────┼────────────────────┐
│     │  AI/ML Models Layer            │                    │
│  ┌──┴──────────┐ ┌──────┴──────┐ ┌──┴───────────┐       │
│  │PaddleOCR    │ │ProPainter  │ │STTN / LaMa   │       │
│  │PP-OCRv4/v5  │ │E2FGVI      │ │OpenCV        │       │
│  │SAM2         │ │             │ │              │       │
│  └─────────────┘ └─────────────┘ └──────────────┘       │
│                                                          │
│  ┌──────────────────────────────────────────────────┐    │
│  │            Hardware Abstraction Layer              │    │
│  │  HardwareAccelerator / FFmpegCLI / VRAM Monitor   │    │
│  └──────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
```

---

## 3. Directory Structure

```
resources/
├── gui.py                          # Main window entry (PySide6/FluentWindow)
├── backend/
│   ├── main.py                     # SubtitleRemover core class
│   ├── config.py                   # Global config (qfluentwidgets QConfig)
│   ├── inpaint/                    # Inpainting algorithm implementations
│   │   ├── sttn_auto_inpaint.py    # STTN auto inpainting
│   │   ├── sttn_det_inpaint.py     # STTN detection-based inpainting
│   │   ├── propainter_inpaint.py   # ProPainter
│   │   ├── e2fgvi_inpaint.py       # E2FGVI
│   │   ├── lama_inpaint.py         # LaMa
│   │   └── opencv_inpaint.py       # OpenCV traditional inpainting
│   ├── tools/
│   │   ├── constant.py             # Enum constants (InpaintMode, SubtitleDetectMode)
│   │   ├── subtitle_detect.py      # SubtitleDetect
│   │   ├── subtitle_extractor.py   # SubtitleExtractor
│   │   ├── video_enhancer.py       # VideoEnhancer (SR+FI pipeline)
│   │   ├── vram_estimator.py       # VRAM estimator
│   │   ├── vram_monitor.py         # VRAM passive monitor
│   │   ├── model_config.py         # Model path config
│   │   ├── hardware_accelerator.py # Hardware acceleration abstraction
│   │   ├── ffmpeg_cli.py           # FFmpeg wrapper
│   │   ├── version_service.py      # Version update service
│   │   ├── process_manager.py      # Process manager
│   │   ├── resource_manager.py     # Resource manager (model download)
│   │   ├── inpaint_tools.py        # Inpainting utility functions
│   │   ├── common_tools.py         # Common utilities
│   │   ├── ocr.py                  # OCR coordinate conversion
│   │   ├── watermark_detect.py     # Watermark template detection
│   │   ├── watermark_tracker.py    # Cross-frame watermark tracking
│   │   ├── sam2_detect.py          # SAM2 watermark detection
│   │   ├── model_compat.py         # Model compatibility layer
│   │   ├── config_profile.py       # Config profile management
│   │   ├── args_handler.py         # CLI args handling
│   │   ├── makedist.py             # Distribution builder
│   │   ├── merge_video.py          # Video merge tool
│   │   ├── gpu_process_monitor.py  # GPU process real-time monitor
│   │   ├── theme_listener.py       # System theme listener
│   │   ├── subtitle_remover_remote_call.py # Remote call interface
│   │   ├── sr_ncnn_backend.py      # Real-ESRGAN ncnn backend
│   │   ├── rife_ncnn_backend.py    # RIFE ncnn backend
│   │   ├── waifu2x_ncnn_backend.py # waifu2x ncnn backend
│   │   ├── concurrent/             # Concurrent task management
│   │   ├── rife_ncnn/              # RIFE ncnn engine files
│   │   ├── sr_ncnn/                # SR ncnn engine files
│   │   ├── waifu2x_ncnn/           # waifu2x ncnn engine files
│   │   └── train/                  # Model training scripts
│   ├── models/                     # AI model files
│   └── scenedetect/                # Scene detection
├── ui/
│   ├── home_interface.py           # Home page interface
│   ├── ai_video_generation_page.py # AI Video Generation page
│   ├── audio_ai_page.py            # AI Audio page
│   ├── video_editor_page.py        # Video Editor page
│   ├── setting_interface.py        # Settings panel
│   ├── advanced_setting_interface.py # Advanced settings page
│   ├── component/
│   │   ├── func_card.py            # Collapsible function card + help button
│   │   ├── video_display_component.py  # Video display component
│   │   ├── task_list_component.py  # Task list component
│   │   ├── watermark_template_widget.py # Watermark template management
│   │   ├── startup_dialog.py       # Startup dialog (project info/donation)
│   │   ├── donation_dialog.py      # Unified donation dialog
│   │   └── gpu_monitor_dialog.py   # GPU real-time monitor dialog
│   └── icon/
│       └── my_fluent_icon.py       # Custom icons
├── config/
│   └── config.json                 # Persistent config (qconfig JSON)
├── design/                         # UI design resources
├── docker/                         # Docker configuration
└── test/                           # Test files
```

---

## 4. Core Module Description

### 4.1 Subtitle Detection Pipeline (`subtitle_detect.py`)

```python
SubtitleDetect
├── text_detector          # PaddleOCR TextDetector (cached_property)
├── detect_subtitle(img)   # Single frame detection → [(xmin,xmax,ymin,ymax), ...]
├── detect_subtitle_with_watermark(img, frame_no)
│                          # OCR + watermark joint detection
├── find_subtitle_frame_no(sub_remover)
│                          # Full video scan → {frame_no: [rects]}
├── find_continuous_ranges_with_same_mask(dict)
│                          # Continuous frame interval grouping
├── filter_and_merge_intervals(intervals, target_length)
│                          # Interval filtering and merging
├── get_scene_div_frame_no(v_path)
│                          # Scene cut detection
└── unify_regions(regions) # Region unification
```

### 4.2 Subtitle Extractor (`subtitle_extractor.py`)

```python
SubtitleExtractor
├── extract(mode)          # Full pipeline (row/column/float)
├── results_to_srt()       # → SRT format (with timestamps)
├── results_to_text()      # → Plain text format
└── _merge_by_mode()       # Merge OCR results by row/column/float mode
```

### 4.3 Inpainting Pipeline

```
SubtitleRemover.run()
├── Load video/models
├── find_subtitle_frame_no()  # Detect subtitle frames
├── Interval grouping → Scene detection → Interval merging
├── Select inpaint engine by inpaintMode:
│   ├── STTN (auto/det)   → sttn_auto_inpaint / sttn_det_inpaint
│   ├── ProPainter         → propainter_inpaint (high VRAM/high quality)
│   ├── E2FGVI             → e2fgvi_inpaint (48GB+ VRAM)
│   ├── LaMa               → lama_inpaint (animation)
│   └── OpenCV             → opencv_inpaint (fast/low quality)
├── Per-interval inpainting → Merge audio → Output
```

### 4.4 VRAM Estimation (`vram_estimator.py`)

```
Built-in baselines (1080p):
  OpenCV:     0.3 GB    | STTN-Auto:   2.8 GB
  STTN-Det:   2.5 GB    | LaMa:        2.2 GB
  E2FGVI:    48.0 GB    | ProPainter: 13.0 GB
  PP-OCRv4-S: 0.8 GB    | PP-OCRv4-M:  0.4 GB
  PP-OCRv5-S: 1.0 GB    | PP-OCRv5-M:  0.5 GB
  SAM2-Tiny:  3.5 GB    | SAM2-Small:  5.0 GB
  SAM2-Base: 10.0 GB    | SAM2-Large: 18.0 GB

Depth coefficient: depth=0 → 0.55x, depth=100 → 2.00x
Resolution scaling: linear scaling based on 1080p (1920x1080)
```

### 4.5 UI Component Architecture

```
FluentWindow (gui.py)
├── HomeInterface
│   ├── QSplitter (horizontal)
│   │   ├── Left: QSplitter (vertical)
│   │   │   ├── VideoDisplayComponent
│   │   │   └── QTabWidget (Tasks/Output Log/Subtitle Text)
│   │   └── Right: QScrollArea
│   │       ├── CollapsibleFuncCard "Video Subtitle/Watermark Removal"
│   │       │   ├── Core Settings (Inpaint/Detect/Depth)
│   │       │   ├── Performance (HW Accel/Concurrency)
│   │       │   ├── ▶ Watermark Detection
│   │       │   ├── ▶ VRAM Estimation & Monitor
│   │       │   └── Action Buttons
│   │       └── CollapsibleFuncCard "Subtitle Extraction"
│   │           ├── One-click Extract / Export TXT / Export SRT
│   │           └── ▶ Joint Proofreading
│   └── AdvancedSettingInterface
│       ├── Subtitle Detection Settings
│       ├── STTN/ProPainter Settings
│       └── About
```

---

## 5. Data Flow

### 5.1 Video Subtitle Removal Flow

```
Input Video
  │
  ▼
[SubtitleDetect] ─── OCR Text Detection ──→ Subtitle Box Coordinates
  │
  ▼
[Interval Grouping] ─── Continuous Frame Merge + Scene Cut
  │
  ▼
[Select Inpaint Engine] ─── Parameter interpolation by processingDepth
  │
  ├──→ STTN:     Ref frame step/count ← depth interpolation
  ├──→ ProPainter: mask dilation/optical flow ← depth interpolation
  ├──→ E2FGVI:   Max loaded frames ← depth interpolation
  │
  ▼
[Per-Interval Inpainting] ─── Generate mask → Inpaint → Write temp frames
  │
  ▼
[Merge Output] ─── Copy audio → Package output file
```

### 5.2 Subtitle Extraction Flow

```
Input Video
  │
  ▼
[SubtitleDetect.find_subtitle_frame_no()]
  │  → Frame-by-frame subtitle box detection
  ▼
[Interval Grouping] (find_continuous_ranges_with_same_mask)
  │
  ▼
[OCR Recognition] ─── Sample frames → PaddleOCR.ocr()
  │  mode = row    → Y-axis grouping & sorting
  │  mode = column → X-axis grouping & sorting
  │  mode = float  → Position clustering
  ▼
[Dedup & Merge] ─── Progressive text detection → Time window dedup
  │
  ▼
[Output]
  ├── results_to_srt()  → SRT format (left Tab)
  └── results_to_text() → Plain text (right preview)
```

---

## 6. Configuration System

Based on `qfluentwidgets.qconfig`, config file at `config/config.json`.

**Config Groups**:
| Group | Description |
|-------|-------------|
| `Window` | Window position, language |
| `Main` | Core algorithm, processing depth, concurrency |
| `Sttn` | STTN parameters |
| `ProPainter` | ProPainter parameters |
| `E2FGVI` | E2FGVI parameters |
| `Watermark` | Watermark detection parameters |
| `UI` | Collapse state persistence |
| `SubtitleExtract` | Subtitle extraction mode |

---

## 7. Key Dependencies

| Dependency | Version | Purpose |
|-----------|---------|---------|
| PySide6 | 6.9.0 | GUI framework |
| qfluentwidgets | 1.7.7 | Fluent Design components |
| PaddleOCR | 2.10.0 | OCR detection & recognition |
| paddlepaddle | 3.0.0 | Deep learning framework |
| PyTorch | 2.7.0 | Deep learning framework (inpaint/VoxCPM2/ACE) |
| torchaudio | 2.7.0 | Audio processing (VoxCPM2/ACE) |
| OpenCV | 4.11.0 | Video/image processing |
| FFmpeg | (system) | Video encode/decode/mux |
| ONNX Runtime | 1.20.1 | Model inference acceleration |
| Gradio | 6.19.0 | 🆕 AI Audio WebUI framework |
| huggingface_hub | 1.20.1 | 🆕 Model download (VoxCPM2/ACE) |

---

## 8. Concurrency Model

- **GUI Thread**: Main thread for all UI operations
- **Worker Process**: `multiprocessing.Process` for subtitle removal tasks
- **Background Threads**: `threading.Thread` for subtitle extraction / VRAM monitoring
- **Task Queue**: `ThreadPoolExecutor` for concurrent task management
- **Process Management**: `ProcessManager` for child process lifecycle
- **IPC**: `multiprocessing.Queue` + callback registration pattern

---

## 9. Extension Points

1. **Add new inpainting algorithm**: Add to `InpaintMode` enum → implement inpaint class → add branch in `SubtitleRemover.run()`
2. **Add new detection model**: Add to `SubtitleDetectMode` enum → add model path in `ModelConfig` → implement detection logic
3. **Add new subtitle extraction mode**: Add branch in `_merge_by_mode()` → add option in UI combo box
4. **Add new UI page**: Create sub-interface in `gui.py` → add to navigation via `addSubInterface()`

---

## 10. AI Audio Studio Architecture (Post-v1.4.0)

### 10.1 Overview

```
VSR Main UI (PySide6)
  └── AI Audio Nav Page (audio_ai_page.py)
        ├── Launch VoxCPM2 WebUI ──→ launch_voxcpm.py
        │                            └── VoxCPM2Engine (voice_engine.py)
        │                                ├── TTS Pipeline
        │                                ├── Voice Clone
        │                                ├── Voice Design
        │                                └── Voice Conversion
        │
        ├── Launch ACE-Step WebUI ──→ launch_ace.py
        │                            └── AceStepEngine (music_engine.py)
        │                                ├── Text-to-Music / Lyrics-to-Song
        │                                ├── Continue / Repaint / Cover
        │                                ├── Source Separation
        │                                └── LoRA Training
        │
        └── Unified Gradio WebUI ──→ webui/app.py
                                     ├── 🎤 Voice Tab
                                     ├── 🎵 Music Tab
                                     ├── 🛠 Tools Tab
                                     ╰── ⚙️ Path Settings Tab
```

### 10.2 Directory Layout

```
resources/backend/audio_studio/
├── __init__.py
├── config.py                # AudioStudioConfig
├── user_config.json         # User path persistence
├── core/
│   ├── voice_engine.py      # VoxCPM2Engine
│   └── music_engine.py      # AceStepEngine
├── webui/
│   ├── app.py               # Unified Gradio entry
│   ├── voice_tab.py
│   ├── music_tab.py
│   └── tools_tab.py
├── launch_voxcpm.py
├── launch_ace.py
├── download_models.py       # Mirror-support model download
└── test_integration.py      # 41/41 tests ✅

vendor/ai_audio/
├── voxcpm2/                 # VoxCPM2 voice engine
├── ace_step/                # ACE-Step 1.5 music engine
└── models/hub/              # Shared HF model cache
```

### 10.3 Thread Safety

All engine generation methods use `threading.Lock()` (`_gen_lock`) to prevent concurrent CUDA access.

### 10.4 Path Internalization

All external paths auto-computed to `vendor/ai_audio/` via `AudioStudioConfig.__post_init__()`, `HF_HOME` points to shared model cache.

### 10.5 Detection-based GPU Yield

```
_gpu_yield_if_busy() — active only when _gpu_yield_enabled=True
  ├── torch.cuda.synchronize() < 1ms → interval 10s
  └── sync > 10ms → interval 0.5s, sleep(0.001)
```
