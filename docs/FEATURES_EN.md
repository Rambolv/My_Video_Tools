# VSR Modded Edition - Feature Design  <!-- LVBOBO_markdown_BUG - 新增英文文档 -->

[简体中文](FEATURES.md) | English

## 1. Video Subtitle & Watermark Removal

### 1.1 Core Settings

#### Inpainting Algorithm Selection
- **Type**: Dropdown + ? help button
- **Options**: STTN-Auto / STTN-Det / LaMa / ProPainter / E2FGVI / OpenCV
- **Function**: Select the image inpainting algorithm to fill areas after text removal
- **E2FGVI Special**: Detects GPU VRAM, shows red warning if < 48GB

#### Detection Model Selection
- **Type**: Dropdown + ? help button
- **Options**: PP-OCRv4 Server/Mobile / PP-OCRv5 Server/Mobile / SAM2-Tiny/Small/Base/Large
- **Function**: Select the AI model for detecting subtitle text regions

#### Processing Depth Slider
- **Type**: Horizontal slider (0-100) + value label + ? help button
- **Function**: Continuously adjusts interpolation coefficient for all model parameters
- **Mapping**:
  ```
  depth=0   (fastest):  mask dilation=5px,  timeline=±1fr, STTN ref=5fr,  PP dilation=4px
  depth=25  (light):    interpolated
  depth=50  (standard): mask dilation=17px, timeline=±5fr, STTN ref=12fr, PP dilation=12px
  depth=75  (deep):     interpolated
  depth=100 (extreme):  mask dilation=30px, timeline=±10fr, STTN ref=20fr, PP dilation=20px
  ```
- **Visual Feedback**: Large circular blue handle (18px), enlarges to 20px on hover

### 1.2 Performance Settings

#### Hardware Acceleration
- **Type**: SwitchButton + ? help button
- **Function**: Enable/disable GPU hardware acceleration (CUDA)

#### Max Concurrent Tasks
- **Type**: Dropdown (1-8) + ? help button
- **Special**: Auto red-flag options exceeding VRAM capacity
- **Color Coding**: Red `#e81123` + ⚠️ marker = possible VRAM overflow

### 1.3 Watermark Detection

- **Type**: Collapsible sub-section (▶/▼ arrow + left border indent)
- **Contains**: Watermark template management (capture/load/preview/enable toggle)
- **Function**: Detect deformed logos/watermarks, supports template matching, color propagation, power sweep

### 1.4 VRAM Estimation & Monitoring

- **Type**: Collapsible sub-section
- **Contains**:
  - GPU total VRAM display
  - Current config VRAM estimate (inpaint+detect+depth, color-coded)
  - VRAM passive monitor toggle
  - Model VRAM reference table (HTML table, real collected values preferred, OOM marked ☠️)

#### Color Coding System
```
≥ 95%: #e81123 (red)     - Critical
≥ 85%: #ff8c00 (orange)  - Warning
≥ 70%: #ffd700 (yellow)  - Caution
< 70%: #16ab39 (green)   - Safe
```

### 1.5 Action Buttons

| Button | Icon | Function |
|--------|------|----------|
| Open | 📂 | Select video/image files |
| Start | ▶ | Begin processing task |
| Stop | ⏹ | Terminate current processing |
| ⚙ Advanced | ⚙ | Navigate to advanced settings |

---

## 2. Subtitle Extraction

### 2.1 Extraction Modes

| Mode | Algorithm | Output Format | Use Case |
|------|-----------|---------------|----------|
| **Row Mode** | Y-axis clustering (3% tolerance) → X sort within row | Line breaks | Standard horizontal subtitles |
| **Column Mode** | X-axis clustering (3% tolerance) → Y sort within column | Column breaks | Vertical text/tables |
| **Floating Mode** | Euclidean distance clustering (5% tolerance) → Y sort | Cluster merge | Dynamic/floating watermarks |

### 2.2 Smart Deduplication

- **Progressive Text Detection**: New text fully contains previous result → overwrite as final
- **Time Window Dedup**: Same text repeats within 0.5s → skip
- **Text Normalization**: `_text_normalize()` strips whitespace/punctuation before comparison

### 2.3 Output Formats

| Target | Format | Content |
|--------|--------|---------|
| Left Tab "Subtitle Text" | SRT | Index + timestamp + text |
| Right Preview Box | Plain Text | Text only, blank lines between entries |
| "Export TXT" Button | .txt | Plain text (same as preview) |
| "Export SRT" Button | .srt | Standard subtitle format |

### 2.4 Joint Proofreading

- **Type**: Collapsible sub-section
- **Function**: 3 different OCR models extract sequentially, then merge and deduplicate
- **Constraint**: Models must be different (auto-mutex)
- **Output**: Merged SRT + plain text

---

## 3. Advanced Settings (Separate Page)

Access via bottom navigation bar, includes:

### 3.1 Subtitle Detection Settings
- Pixel deviation parameters
- Area expansion parameters
- Timeline parameters
- Tolerance parameters

### 3.2 STTN Settings
- Neighbor stride
- Reference frame length
- Max loaded frames

### 3.3 ProPainter Settings
- Max loaded frames
- Mask dilation pixels
- Optical flow mask dilation

### 3.4 Other
- Save directory
- Check updates on startup

---

## 4. UI Design Guidelines

### 4.1 Interaction Patterns

| Element | Interaction |
|---------|-------------|
| ? Help Button | Click → MessageBox popup / Hover 0.6s → ToolTip |
| ▼/▶ Arrow | Click → Expand/collapse, state persists in config |
| Splitter Handle | Drag → Adjust panel ratio |
| Slider Handle | Drag → Real-time value & config update |
| Red-Flag Options | Auto-update based on VRAM headroom |

### 4.2 Visual Hierarchy

```
Function Card (CardWidget, border-radius: 8)
  ┃ SectionHeader (blue left border 3px + bold)
  ┃ SettingRow (label 80px + control + ? help)
  ┃ ▼ Sub-section (blue bold arrow 12px + left border 2px)
  ┃   │ Indented content
```

### 4.3 Responsive Design

- Main interface uses `QSplitter` (horizontal + vertical)
- Right function panel uses `QScrollArea`, auto-scrolls on overflow
- Labels enable `setWordWrap(True)`
- Buttons set `setMinimumHeight(34)` + `setMinimumWidth(80)`
- Text areas enable `setLineWrapMode(WidgetWidth)`

---

## 5. AI Model Support List

### 5.1 Subtitle Detection Models

| Model | Type | VRAM (1080p) | Characteristics |
|-------|------|-------------|-----------------|
| PP-OCRv4 Server | OCR | 0.8 GB | High accuracy |
| PP-OCRv4 Mobile | OCR | 0.4 GB | Lightweight & fast |
| PP-OCRv5 Server | OCR | 1.0 GB | Latest high accuracy |
| PP-OCRv5 Mobile | OCR | 0.5 GB | Latest lightweight |
| SAM2-Tiny | Segmentation | 3.5 GB | Lightweight segmentation |
| SAM2-Small | Segmentation | 5.0 GB | Balanced segmentation |
| SAM2-Base | Segmentation | 10.0 GB | High accuracy segmentation |
| SAM2-Large | Segmentation | 18.0 GB | Extreme precision |

### 5.2 Image Inpainting Models

| Model | VRAM (1080p) | Speed | Quality | Use Case |
|-------|-------------|-------|---------|----------|
| OpenCV | 0.3 GB | ★★★★★ | ★★ | Quick preview |
| STTN-Auto | 2.8 GB | ★★★★ | ★★★ | General subtitles |
| STTN-Det | 2.5 GB | ★★★★ | ★★★ | Fixed subtitles |
| LaMa | 2.2 GB | ★★★ | ★★★★ | Animation videos |
| E2FGVI | 48.0 GB | ★★ | ★★★★★ | Fine detail scenes |
| ProPainter | 13.0 GB | ★★ | ★★★★★ | Heavy motion |

---

## 6. VRAM Monitoring System

### 6.1 Passive Monitoring

- **Principle**: Automatically samples GPU VRAM peaks during normal workflow
- **Trigger**: `enableVramMonitoring` config item
- **Frequency**: Sample every 0.5 seconds
- **Storage**: `config/vram_records.json`
- **Deduplication**: Same config won't be re-collected

### 6.2 Data Usage

- Collected values override `_MODEL_VRAM_BASELINE_1080P` built-in baselines
- Used for concurrent task VRAM red-flagging
- OOM records marked as ☠️

### 6.3 Estimation Formula

```
Single task VRAM = max(model baseline × resolution factor × depth factor, detection VRAM) × 1.10
Multi-task VRAM = first task VRAM + second model×0.5 + (concurrency-1) × first task VRAM × 0.40
Overflow check = total > GPU VRAM × 0.90 (10% headroom)
```

---

## 7. Video Enhancement (Super-Resolution & Frame Interpolation)

### 7.1 Overview

This module is a newly added video quality enhancement feature for the VSR Modded Edition, containing **Super-Resolution (SR)** and **Frame Interpolation (FI)** sub-modules, which can be used separately or in combination (SR first, then FI).

### 7.2 Super-Resolution (Real-ESRGAN)

| Item | Description |
|------|-------------|
| **Algorithm** | Real-ESRGAN (BSRGAN improvement, BSD 3-Clause License) |
| **Python CUDA Backend** | `realesrgan` pip package, models auto-download to `resources/weights/` |
| **ncnn-Vulkan Backend** | Via `realesrgan-ncnn-vulkan.exe`, ⚠️ model files hosted on GitHub LFS, restricted in China, auto-fallback to Python |

**Status Indicators**:
- ✅ **Python CUDA**: Working (requires realesrgan pip package)
- ⚠️ **ncnn-Vulkan**: Model files (.bin/.param) on GitHub LFS — auto-fallback to Python when download fails

**Available Models**:
```
realesr-general-x4v3         # ⚠️ Default, may need download
RealESRGAN_x4plus            # ✅ General 4x SR
RealESRGAN_x4plus_anime_6B   # Anime-optimized
RealESRGAN_x2plus            # 2x SR
```

### 7.3 waifu2x Anime Super-Resolution

| Item | Description |
|------|-------------|
| **Engine** | waifu2x-ncnn-vulkan (MIT License, v20250915) |
| **Backend** | ncnn-Vulkan (only option) |
| **Model Architectures** | `cunet` (general anime) / `upconv_anime` (lightweight anime) |
| **Denoise Level** | 0-3 |
| **Scale Ratio** | 1x-10x (custom step 0.1) |
| **Multi-threading** | Configurable, default `1:2:2` (process:scale:denoise) |

**Status**: ✅ Working

### 7.4 Frame Interpolation (RIFE)

| Item | Description |
|------|-------------|
| **Algorithm** | RIFE (Real-Time Intermediate Flow Estimation) v3.x |
| **Model Source** | Flowframes RIFE39 model (flownet.pkl, 27MB) |
| **Interpolation Multiplier** | 2x / 3x / 4x / 8x |

#### Python CUDA Backend

| Aspect | Description |
|--------|-------------|
| **Principle** | PyTorch loads flownet.pkl, optical flow interpolation |
| **Status** | ⚠️ **Experimental** — import issue recently fixed (relative import), pending user validation |
| **Dependency** | PyTorch (CUDA), pre-installed in embedded Python |
| **Model Path** | `resources/models/rife/flownet.pkl` |

**Known Issues**:
- ⚠️ `No module named 'model.RIFE_HDv3'` → ✅ Fixed (changed to `from .model.RIFE_HDv3`)
  - Root cause: QPT environment modifies sys.path, absolute imports fail
- ⚠️ Fix pending user verification after restart

#### ncnn-Vulkan Backend

| Aspect | Description |
|--------|-------------|
| **Engine** | `rife-ncnn-vulkan.exe` (from Flowframes, 4.1MB) |
| **Mode** | Pair mode (`-0 f0 -1 f1 -o out`), process one pair at a time |
| **Status** | ⚠️ **Pair mode works but slow** — launches exe per pair, N frames = N-1 launches |

**Known Issues**:
- ❌ **Directory mode deprecated**: Old exe produces garbage output with rife-v3 (4 input → 8 corrupted output frames)
- ⚠️ **Pair mode silent failures**: `STATUS_ACCESS_VIOLATION` on some PNG decodes, still writes output file
- ⚠️ **Model compatibility**: Old exe doesn't support rife-v4.6 `Eltwise` layer, use rife-v3.1 models

### 7.5 Performance Benchmarks

**Test Platform**: RTX 4090, 75 frames 640×360 input

| Operation | Output Resolution/FPS | Time |
|-----------|----------------------|------|
| Real-ESRGAN 4x SR (Python CUDA) | 2560×1440 | 10.1s |
| RIFE 2x FI (Python CUDA) | 30fps | 2.5s |
| SR→FI Pipeline | 2560×1440 @ 30fps | 182.7s |
| STTN Auto (optimized) | - | Speed +30~50%, VRAM -50% |
| Multi-Sweep (optimized) | - | Inference 3x→2x |

---

## 8. New Feature Modules (Post-v1.4.0)

### 8.1 VRAM Active Scheduling System

Built on top of passive monitoring, the new active scheduling system:

- **Real-time VRAM Pressure Monitoring**: Continuously tracks dedicated GPU memory usage
- **Adaptive Batch Size**: Dynamically adjusts frames per batch based on remaining VRAM
- **Dynamic GPU Memory Reclamation**: Triggers `torch.cuda.empty_cache()` during idle
- **Multi-Task Phased Scheduling**: Subtitle/SR/FI models load phase-by-phase to prevent OOM
- **Dedicated VRAM Lock**: Prevents Windows WDDM spillover, 96% soft-limit for onboard memory only

### 8.2 New Pages

| Page | File | Description |
|------|------|-------------|
| AI Video Generation | `ai_video_generation_page.py` | AI video generation entry |
| AI Audio Processing | `audio_ai_page.py` | Audio processing features |
| Video Editor | `video_editor_page.py` | Video clip editing |

### 8.3 ncnn Backend System

| Backend | Engine | Status |
|---------|--------|--------|
| `sr_ncnn_backend.py` | realesrgan-ncnn-vulkan | ✅ Python preferred, ncnn fallback |
| `rife_ncnn_backend.py` | rife-ncnn-vulkan | ⚠️ Pair mode works but slow |
| `waifu2x_ncnn_backend.py` | waifu2x-ncnn-vulkan | ✅ Working |

### 8.4 New Tool Modules

| Module | Description |
|--------|-------------|
| `resource_manager.py` | Unified model download & path management |
| `config_profile.py` | Multi-config save/switch |
| `watermark_tracker.py` | Cross-frame watermark position tracking |
| `model_compat.py` | Model version compatibility |
| `theme_listener.py` | System theme real-time switching |
| `gpu_process_monitor.py` | GPU process real-time monitoring |
| `merge_video.py` | Multi-segment video merging |

### 8.5 New UI Components

| Component | Description |
|-----------|-------------|
| `startup_dialog.py` | Startup dialog (project info, hardware tips, donation QR) |
| `donation_dialog.py` | Unified donation dialog component |
| `gpu_monitor_dialog.py` | GPU real-time monitor dialog (process ranking table) |

---

### 7.5 Enhancement Pipeline Workflow

```
Input video → [Optional] Super-Resolution (Real-ESRGAN / waifu2x)
             → [Optional] Frame Interpolation (RIFE)
             → Output video (original audio preserved)
```

The pipeline is chained by `VideoSuperResolution` and `VideoFrameInterpolation` classes:
1. SR stage: Extract all frames → process each frame → encode as temp video
2. FI stage: Extract SR'd frames → RIFE interpolation → encode final video + original audio

### 7.6 Configuration Parameters (config.json)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `srModelName` | `RealESRGAN_x4plus` | SR model name |
| `srBackend` | `python` | SR backend: `python` / `ncnn` |
| `srScale` | 4 | SR scale factor |
| `waifu2xModelArch` | `cunet` | waifu2x model architecture |
| `waifu2xDenoise` | 0 | waifu2x denoise level |
| `waifu2xScale` | 2 | waifu2x scale factor |
| `fiModelName` | `rife-v3.1` | FI model name |
| `fiBackend` | `python` | FI backend: `python` / `ncnn` |
| `fiMultiplier` | 2 | FI multiplier (2/3/4/8) |
| `fiNcnnThreads` | `1:2:2` | ncnn thread config (process:scale:denoise) |
