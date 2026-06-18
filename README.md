# VSR - Video Subtitle Remover (视频字幕去除器)

![Python](https://img.shields.io/badge/Python-3.12+-blue)
![PySide6](https://img.shields.io/badge/PySide6-6.9.0-green)
![License](https://img.shields.io/badge/License-Apache%202-red)

[English](README_en.md) | 简体中文

> **基于 AI 的视频硬字幕去除工具** — 支持 GPU 加速，提供图形化界面和命令行两种使用方式。

---

## 📋 目录

- [项目来源](#-项目来源)
- [功能特性](#-功能特性)
- [快速开始](#-快速开始)
- [界面预览](#-界面预览)
- [技术架构](docs/ARCHITECTURE.md)
- [功能设计](docs/FEATURES.md)
- [变更日志](docs/CHANGELOG.md)
- [常见问题](#-常见问题)

---

## 📖 项目来源

本项目基于 [**YaoFANGUK/video-subtitle-remover**](https://github.com/YaoFANGUK/video-subtitle-remover)（VSR v1.1.0）进行深度二次开发，在原项目基础上进行了大量功能增强和 UI 重构。

### 原项目信息

| 项目 | 说明 |
|------|------|
| **原作者** | [YaoFANGUK](https://github.com/YaoFANGUK) |
| **原项目地址** | https://github.com/YaoFANGUK/video-subtitle-remover |
| **原始版本** | v1.1.0 |
| **原始许可证** | Apache License 2.0 |

### 本分支新增/改进的功能

- **处理深度滑块**：0-100 连续调节，实时插值所有模型参数
- **字幕提取功能**：基于 PaddleOCR 的全流程 OCR 提取，支持按行/按列/浮动三种模式
- **联合校对**：三个不同 OCR 模型分别提取后合并择优
- **VRAM 显存监控**：被动采集真实显存数据，智能标红预警
- **可折叠功能区 UI**：qfluentwidgets 重构，支持持久化折叠状态
- **帮助按钮系统**：所有控件旁 `?` 按钮，点击/悬停查看详细说明
- **可拖拽分割面板**：QSplitter 实现，所有区域自由调整大小
- **显存参考表**：内置 14 个模型的 VRAM 基准 + OOM 危险标记
- **E2FGVI 显存警告**：不足 48GB 显存时自动红色预警
- **并发任务标红**：超出显存容量的选项自动红色 ⚠️ 标记
- **模型显存参考表**：HTML 表格展示，真实采集值优先
- **自动换行 & 自适应按钮**：文本溢出自动换行，按钮自适应大小

---

## ✨ 功能特性

### 🎬 视频去字幕水印

| 功能 | 说明 |
|------|------|
| **AI 修复算法** | 支持 6 种修复引擎：STTN、ProPainter、E2FGVI、LaMa、OpenCV |
| **字幕检测** | PP-OCRv4/v5、SAM2 共 8 种检测模型可选 |
| **处理深度滑块** | 0-100 连续调节，实时插值所有模型参数 |
| **水印检测** | 模板匹配、颜色传播、强力清扫、区域重绘 |
| **并发处理** | 1-8 任务并行，自动 VRAM 标红预警 |
| **VRAM 监控** | 被动采集真实显存数据，智能推荐 |

### 📝 字幕提取

| 功能 | 说明 |
|------|------|
| **一键提取** | 自动检测并 OCR 识别全部字幕 |
| **三种模式** | 按行提取 / 按列提取 / 提取浮动字幕 |
| **联合校对** | 三个不同模型分别提取后合并择优 |
| **格式导出** | 纯文本 (.txt) / 标准字幕 (.srt) |

### 🖥 UI 特性

- **可拖拽分割面板** — 所有区域自由调整大小
- **可折叠功能区** — 状态持久化，下次启动保持
- **帮助按钮系统** — 每个控件旁 ? 按钮，点击/悬停查看说明
- **显存参考表** — 内置 14 个模型的 VRAM 基准 + 真实采集值
- **智能标红** — 超出显存配置自动红色预警
- **多语言支持** — 简体中文、English、日本語等

---

## 🚀 快速开始

### Windows 预构建包

从原项目 Releases 下载对应版本：

| 包名 | 环境 | 适用 GPU |
|------|------|---------|
| `vsr-windows-cuda-12.6.7z` | CUDA 12.6 | NVIDIA 5.0-8.9 算力 |
| `vsr-windows-cuda-11.8.7z` | CUDA 11.8 | NVIDIA 3.5-8.9 算力 |
| `vsr-windows-directml.7z` | DirectML | 非 NVIDIA 显卡 |
| `vsr-windows-cpu.7z` | CPU | 通用 |

### 运行

```bash
# 解压后双击运行
使用兼容模式运行.cmd

# 或直接命令行
cd resources
../Python/python.exe gui.py
```

### 从源码运行

```bash
# 1. 创建虚拟环境
python -m venv venv
# Windows
venv\Scripts\activate

# 2. 安装依赖
pip install -r resources/requirements.txt

# 3. 运行
cd resources
python gui.py
```

### Docker

```bash
# CUDA 11.8 (10/20/30 系显卡)
docker run -it --name vsr --gpus all eritpchy/video-subtitle-remover:1.4.0-cuda11.8 \
  python backend/main.py -i /input/video.mp4 -o /output/video_no_sub.mp4

# CUDA 12.6 (40 系显卡)
docker run -it --name vsr --gpus all eritpchy/video-subtitle-remover:1.4.0-cuda12.6 \
  python backend/main.py -i /input/video.mp4 -o /output/video_no_sub.mp4
```

---

## 🖥 界面预览

```
┌───────────────────────────────────┬─────────────────────────────┐
│         视频预览区域               │   视频去字幕水印功能        │
│  ┌─────────────────────────────┐  │   ┃ 核心设置               │
│  │                             │  │   修复算法 [STTN-Auto] [?] │
│  │      Video Display          │  │   检测模型 [PP-OCRv4]  [?] │
│  │                             │  │   处理深度 [===slider===]  │
│  └─────────────────────────────┘  │   ┃ 性能设置               │
│  ┌─────────────────────────────┐  │   硬件加速 [Switch]  [?]  │
│  │ 📋 任务列表 │ 📝 输出日志   │  │   并发任务 [Combo]   [?]  │
│  │ │ 📄 字幕文本 (Tab 切换)   │  │   ▶ 水印检测              │
│  └─────────────────────────────┘  │   ▶ 显存估算与监控        │
│                                   │   [打开][开始][停止][⚙]   │
│          可拖拽分割线             ├─────────────────────────────┤
│                                   │   字幕提取                 │
│                                   │   [一键提取] 模式:[按行 ▼] │
│                                   │   [导出文本][导出SRT] [?] │
│                                   │   ▶ 联合校对              │
└───────────────────────────────────┴─────────────────────────────┘
```

---

## 📁 项目结构

```
resources/
├── gui.py                  # GUI 主入口
├── backend/                # 后端逻辑
│   ├── main.py             # 字幕去除核心
│   ├── config.py           # 全局配置
│   ├── inpaint/            # 修复算法
│   │   ├── propainter/     # ProPainter
│   │   ├── sttn_auto/      # STTN 自动
│   │   └── ...
│   └── tools/              # 工具模块
│       ├── subtitle_detect.py    # 字幕检测
│       ├── subtitle_extractor.py # 字幕提取
│       ├── vram_estimator.py     # VRAM 估算
│       ├── vram_monitor.py       # VRAM 监控
│       └── ...
├── ui/                     # 界面模块
│   ├── home_interface.py   # 主页
│   ├── setting_interface.py # 设置面板
│   ├── advanced_setting_interface.py # 高级设置
│   └── component/          # 可复用组件
├── config/                 # 配置文件
└── models/                 # AI 模型文件
```

> 详细技术文档请见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## ❓ 常见问题

**Q: 提示"无法找到模型文件"？**
A: 模型文件被分片存储，首次运行会自动合并。确保有足够的磁盘空间。

**Q: GPU 显存不足怎么办？**
A: 降低"处理深度"滑块、减少并发任务数、选择轻量模型（PP-OCRv4 Mobile + STTN）。

**Q: E2FGVI 无法运行？**
A: E2FGVI 需要 48GB+ VRAM。您的 GPU 显存不足时会显示红色警告，建议使用 ProPainter 替代。

**Q: 字幕提取没有结果？**
A: 尝试切换提取模式（按行/按列/浮动），或更换检测模型（PP-OCRv5 Server 精度最高）。

---

## 📄 许可证

本项目基于 [Apache License 2.0](resources/LICENSE) 开源。

**原项目**: [YaoFANGUK/video-subtitle-remover](https://github.com/YaoFANGUK/video-subtitle-remover)
