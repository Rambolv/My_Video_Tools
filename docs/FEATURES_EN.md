# VSR Feature Design Document

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
