# My AI Media Toolbox - Quick Start Guide  <!-- LVBOBO_markdown_BUG -->

[简体中文](QUICK_START.md) | English

> My AI Media Toolbox — AI-powered comprehensive media processing toolkit

## 📥 Step 1: Download

### Windows Users (Pre-built Package — Extract & Run)

| Your GPU | Download |
|---------|----------|
| **NVIDIA GPU** (GTX 1060+) | `vsr-windows-nvidia-cuda-12.6.7z` |
| **NVIDIA Legacy** (GTX 750~1050) | `vsr-windows-nvidia-cuda-11.8.7z` |
| **NVIDIA RTX 50-series** | `vsr-windows-nvidia-cuda-12.8.7z` |
| **AMD / Intel GPU** | `vsr-windows-directml.7z` |
| **No dedicated GPU** | `vsr-windows-cpu.7z` |

**Download Links:**
- ☁️ Google Drive: [Download](https://drive.google.com/drive/folders/1NRgLNoHHOmdO4GxLhkPbHsYfMOB_3Elr?usp=sharing)

> 💡 Not sure which GPU you have? Press `Win+R`, type `dxdiag`, check the "Display" tab.

---

## 🚀 Step 2: Run

### Option A: GUI Mode (Recommended)

```
1. Extract the downloaded .7z file
2. Double-click "使用兼容模式运行.cmd"
   (If it doesn't work, try "启动程序.exe")
3. Click "选择视频" to pick your video
4. Drag to select the watermark/subtitle area
5. Click "开始处理" to start
```

### Option B: Docker (Linux/Mac)

```bash
# NVIDIA GPU
docker run -it --gpus all eritpchy/video-subtitle-remover:1.4.0-cuda12.6 \
  python backend/main.py -i /input/video.mp4 -o /output/video_no_sub.mp4

# CPU
docker run -it eritpchy/video-subtitle-remover:1.4.0-cpu \
  python backend/main.py -i /input/video.mp4 -o /output/video_no_sub.mp4
```

---

## 🎯 Feature Quick Tour

### 1️⃣ Basic Subtitle Removal

Open app → Select subtitle area → Click "Start"

Best for: Static subtitles at video bottom/top

### 2️⃣ Multi-Sweep Mode (for AI Watermarks)

> For **white semi-transparent deforming watermarks** on AI-generated videos

How to use:
```
① Toggle "多循环暴力扫除" button ON
② Set iterations (recommended: 2~3)
③ Click "开始处理"
```

How it works:
```
Each pass: cleaned output → re-detect → re-inpaint
           Progressively removes stubborn watermarks
```

### 3️⃣ Subtitle Extraction

One-click subtitle text extraction:
- Extraction modes: **Row mode** (default), **Column mode**, **Float mode**
- Click "Extract", results displayed automatically
- Export as plain text (.txt) or standard subtitle (.srt)
- Expand "Joint Proofreading" to use 3 OCR models for best accuracy

### 4️⃣ Video Enhancement (SR + FI)

New "Video Enhancement" section:

| Feature | Description |
|---------|-------------|
| **Real-ESRGAN SR** | Upscale video clarity, supports 2x/4x |
| **waifu2x Anime SR** | Anime-optimized super-resolution |
| **RIFE Frame Interpolation** | Boost frame rate (2x/3x/4x/8x) for smoother video |
| **Combined Pipeline** | Chain SR + FI in either order |

### 5️⃣ Advanced Settings

Available in the "Settings" page:
- **Processing Depth**: 0=fast/light, 100=thorough
- **Inpainting Model**: ProPainter, STTN, LaMa, E2FGVI, OpenCV
- **Detection Model**: PP-OCRv4/v5, SAM2-Tiny/Small/Base/Large
- **VRAM Management**: Passive monitoring + Active scheduling + Dedicated VRAM lock
- **GPU Monitor**: View process GPU usage in real-time

### 6️⃣ AI Navigation Pages

Bottom nav bar provides three independent pages:
- 🤖 **AI Video Generation** — AI video creation tools
- 🎵 **AI Audio** — Audio processing features
- ✂️ **Video Editor** — Video clip editing

---

## ❓ FAQ

**Q：Processing is slow?**
- First run loads models (slower), subsequent runs are faster
- Lower "Processing Depth" in settings to speed up
- Check GPU is being used (NVIDIA is fastest)

**Q：Watermark not fully removed?**
- Enable "Multi-Sweep" mode and increase iteration count
- Make sure the watermark area is fully selected
- Try ProPainter or LaMa model

**Q：Out of memory (OOM)?**
- Enable VRAM monitoring & active scheduling
- Lower processing depth
- Reduce concurrent tasks
- Enable "Dedicated VRAM Lock" to prevent spillover

**Q：Where is the output file?**
- Same directory as input video, with operation tag in filename
- Multi-sweep adds iteration count: e.g., `video_3clean.mp4`

**Q：How to check GPU usage?**
- Click "View GPU Occupancy" in the VRAM section
- Dialog shows all GPU processes ranked by compute load

---

## 🔗 Links

- [GitHub Repository](https://github.com/Rambolv/My_Video_Tools)
- [Full Documentation](README_en.md)
- [Report Issues](https://github.com/Rambolv/My_Video_Tools/issues)
