# VSR Modded Edition - Quick Start Guide

[简体中文](QUICK_START.md) | English

> VSR Modded Edition — AI-powered hard subtitle & watermark removal tool

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

### 3️⃣ Advanced Settings

Available in the "Settings" page:
- **Processing Depth**: 0=fast/light, 100=thorough
- **Inpainting Model**: ProPainter (best), STTN, LaMa, E2FGVI
- **VRAM Monitor**: Prevents out-of-memory errors

---

## ❓ FAQ

**Q：Processing is slow?**
- First run loads models (slower), subsequent runs are faster
- Lower "Processing Depth" in settings to speed up
- Check GPU is being used (NVIDIA is fastest)

**Q：Watermark not fully removed?**
- Enable "多循环暴力扫除" and increase iteration count
- Make sure the watermark area is fully selected
- Try ProPainter or LaMa model

**Q：Out of memory (OOM)?**
- Enable VRAM monitoring in settings
- Lower processing depth
- Reduce concurrent tasks

**Q：Where is the output file?**
- Same directory as input video, with `_no_sub` suffix
- Multi-sweep adds iteration count: e.g., `video_3clean_no_sub.mp4`

---

## 🔗 Links

- [GitHub Repository](https://github.com/Rambolv/Video_Tools)
- [Full Documentation](README_en.md)
- [Report Issues](https://github.com/Rambolv/Video_Tools/issues)
