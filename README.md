# 我的AI影音工具百宝箱  <!-- LVBOBO_markdown_BUG -->

![Python](https://img.shields.io/badge/Python-3.12+-blue)
![PySide6](https://img.shields.io/badge/PySide6-6.9.0-green)
![License](https://img.shields.io/badge/License-Apache%202-red)

[English](README_en.md) | 简体中文

> **我的AI影音工具百宝箱** — 基于 VSR v1.4.0 深度二次开发的全能影音工具箱。
> 整合了视频字幕/水印去除、视频增强（超分+插帧）、AI 语音合成（VoxCPM2）、AI 音乐生成（ACE-Step 1.5）等丰富功能。
> 支持 GPU 加速，提供图形化界面和命令行（未完成）两种使用方式。

---

## 📋 目录

- [项目来源](#-项目来源)
- [功能特性](#-功能特性)
- [快速开始](#-快速开始)
- [界面预览](#-界面预览)
- [使用指南](#-使用指南)
- [技术架构](docs/ARCHITECTURE.md)
- [功能设计](docs/FEATURES.md)
- [变更日志](docs/CHANGELOG.md)
- [常见问题](#-常见问题)

---

## 📖 项目来源

本项目基于 [**YaoFANGUK/video-subtitle-remover**](https://github.com/YaoFANGUK/video-subtitle-remover)（VSR v1.4.0）进行深度二次开发，在原项目基础上进行了大量功能增强和 UI 重构。
同时整合强化了原作者 VSE 预构建包（`vse-windows-*.7z`）的全部功能特性，包括 Multi-Sweep 多循环暴力扫除、水印模板匹配检测、自适应遮罩等高级功能。

### 原项目信息

| 项目 | 说明 |
|------|------|
| **原作者** | [YaoFANGUK](https://github.com/YaoFANGUK) |
| **原项目地址** | https://github.com/YaoFANGUK/video-subtitle-remover |
| **原始版本** | v1.4.0 |
| **原始许可证** | Apache License 2.0 |

### 本分支新增/改进的功能

> 本魔改版全面整合并强化了原作者 VSE 预构建包的所有高级功能（Multi-Sweep 多循环暴力扫除、水印模板匹配检测等），同时在 VSE 基础上进一步增加了 ProPainter/E2FGVI 修复引擎、PP-OCRv5 检测模型、SAM2 分割模型等重磅升级。

#### 🚀 核心算法增强
- **处理深度滑块**：0-100 连续调节，实时插值所有模型参数（Mask膨胀、时间线、参考帧等），在速度与质量之间灵活平衡
- **多循环暴力扫除**：针对 AI 生成视频中快速变化/扭曲/变形的 Logo 水印，采用变形自适应遮罩 + RGB 聚类 + 强时序滤波 + 多轮渐进清除
- **水印模板匹配检测**：支持模板截取、旋转/缩放匹配、特征匹配、颜色传播、强力清扫（时序差分）、强制区域重绘
- **ProPainter / E2FGVI 修复引擎**：新增 ProPainter（高效果/高显存）和 E2FGVI（CVPR 2022，48GB+ VRAM）两种高质量修复算法
- **SAM2 检测模型**：新增 SAM2-Tiny/Small/Base/Large 四档分割模型，配合 PaddleOCR 使用
- **PP-OCRv5 检测模型**：升级支持 PP-OCRv5 Server/Mobile 最新 OCR 检测
- **视频超分辨率（Real-ESRGAN）**：内置 Real-ESRGAN 超分算法，支持 Python CUDA（可用）和 ncnn-Vulkan（⚠️ 国内无法下载模型，自动回退 Python）两种后端
- **waifu2x 动漫超分**：集成 waifu2x-ncnn-vulkan，支持 cunet / upconv_anime 两种模型架构
- **帧插值（RIFE）**：内置 RIFE 光流插帧算法，支持 Python CUDA（⚠️ 实验性，需验证）和 ncnn-Vulkan（⚠️ 可靠但速度较慢）两种后端

#### 📝 字幕提取系统
- **全流程字幕提取**：基于 PaddleOCR 的自动化管道，支持一键提取
- **三种提取模式**：按行提取 / 按列提取 / 提取浮动字幕
- **联合校对**：三个不同 OCR 模型分别提取后合并去重择优
- **多格式导出**：纯文本 (.txt) / 标准字幕 (.srt)

#### 🖥️ UI/UX 全面重构
- **GUI 框架升级**：从 PySimpleGUI 全面重构为 PySide6 + qfluentwidgets（Fluent Design）
- **可拖拽分割面板**：QSplitter 实现，所有区域自由调整大小
- **可折叠功能区**：支持持久化折叠状态（保存到 config.json）
- **帮助按钮系统**：所有控件旁 `?` 按钮，点击弹出详细说明，悬停显示工具提示
- **处理深度可视化**：滑块实时显示当前深度对应的所有模型参数插值
- **启动弹窗**：显示项目信息、硬件依赖与推荐设置、捐赠二维码
- **窗口位置记忆**：自动保存/恢复窗口位置和大小

#### 🧠 显存智能管理
- **VRAM 被动监控**：跟随正常工作流程自动采集 GPU 显存峰值
- **显存估算参考表**：内置 14 个模型的 VRAM 基准值，真实采集值优先显示
- **并发任务显存标红**：超出显存容量的并发选项自动以红色 ⚠️ 标记
- **E2FGVI 显存警告**：选择 E2FGVI 时检测 GPU 显存，不足 48GB 显示红色警告
- **颜色编码系统**：≥95% 红色 / ≥85% 橙色 / ≥70% 黄色 / <70% 绿色

#### 🔧 技术架构改进
- **场景检测分割**：基于帧间差异的场景切换检测，优化区间分组
- **硬件加速抽象层**：统一 CUDA / ONNX 硬件加速接口
- **FFmpeg CLI 封装**：视频编解码/音频合并/格式转换
- **进程管理器**：统一管理子进程生命周期（multiprocessing）
- **线程安全 UI 更新**：使用信号槽机制替代直接跨线程调用
- **分片模型自动合并**：大模型文件分片存储，首次运行自动合并（fsplit）
- **高级设置页面**：独立页面提供字幕检测/STTN/ProPainter 等细粒度参数调节
- **版本更新检查**：自动检测 GitHub 新版本发布
- **多语言界面支持**：简体中文 / English / 日本語 / 한국어 / Tiếng Việt / Español
- **主题切换**：亮色/暗色主题一键切换
- **模型自动下载**：首次启动自动从 GitHub Releases 下载 AI 模型（~700MB）
- **一键安装脚本**：`setup_windows.ps1` 自动完成 Python 环境 + 依赖 + 模型全流程配置

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

### 🎨 视频增强（超分辨率 & 插帧）

| 功能 | 说明 | 状态 |
|------|------|------|
| **超分辨率 Real-ESRGAN** | Python CUDA（✅ 已验证 75帧 640→2560 耗时10s） / ncnn-Vulkan（模型受限） | ✅ / ⚠️ |
| **waifu2x 动漫超分** | waifu2x-ncnn-vulkan，cunet / upconv_anime 模型 | ✅ |
| **帧插值 RIFE（Python）** | Python CUDA（✅ CLI 75帧 2x 2.5s，✅ 子进程导入已修复 importlib） | ✅ |
| **帧插值 RIFE（ncnn）** | ncnn-Vulkan 配对模式稳定但较慢（每对帧启动一次 exe） | ⚠️ |
| **音频保留** | 插帧后自动保留原始音频，不改变时长 | ✅ |
| **组合管道** | SR + FI 串联（✅ 已验证 75帧 4x超分+2x插帧 共计183s） | ✅ |

### 📝 字幕提取

| 功能 | 说明 |
|------|------|
| **一键提取** | 自动检测并 OCR 识别全部字幕 |
| **三种模式** | 按行提取 / 按列提取 / 提取浮动字幕 |
| **联合校对** | 三个不同模型分别提取后合并择优 |
| **格式导出** | 纯文本 (.txt) / 标准字幕 (.srt) |

### 🎵 AI 音频工作室（新增）

| 功能 | 说明 |
|------|------|
| **语音合成 (TTS)** | VoxCPM2 引擎，多音色文本转语音，48kHz 输出 |
| **音色克隆** | 从参考音频克隆任意音色 |
| **声音设计** | 文本描述生成定制声音 |
| **声音转换** | 输入音频转换音色 |
| **文生音乐** | ACE-Step 1.5 引擎，文本生成完整乐曲 |
| **歌词生曲** | 输入歌词生成配乐演唱 |
| **音源分离** | 分离人声/伴奏/鼓/贝斯/其他 |
| **翻唱/续写/重绘** | 音乐智能编辑 |

### 🖥 UI 特性

- **AI 功能导航页** — AI 视频生成、AI 音频、视频编辑器三个独立页面
- **可拖拽分割面板** — 所有区域自由调整大小
- **可折叠功能区** — 状态持久化，下次启动保持
- **帮助按钮系统** — 每个控件旁 ? 按钮，点击/悬停查看说明
- **显存参考表** — 内置 14 个模型的 VRAM 基准 + 真实采集值
- **智能标红** — 超出显存配置自动红色预警
- **多语言支持** — 简体中文、English、日本語等

---

## 🚀 快速开始

### 📦 源码安装包（推荐，仅 0.3MB）

从 [Releases](https://github.com/Rambolv/My_Video_Tools/releases) 下载 `AI-Media-Toolbox-Source-v1.4.0.7z`
| 🚀 **超小体积** | 仅 0.3MB，仅含 Python 源码 |
| 🔧 **一键安装** | 运行 setup_windows.ps1 自动完成全部配置 |
| 📥 **自动下载** | Python 环境 + pip 依赖 + AI 模型（~700MB）全自动下载 |
| 🎯 **开箱即用** | 安装完成后双击「启动我的AI影音工具百宝箱.cmd」即可使用 |

**Windows 全量版（含运行环境 + 全部模型，解压即用）：**
- ☁️ 百度网盘：[下载 MyvideoTools.rar](https://pan.baidu.com/s/1MEeQeiTiXTVd_Z5AMTKgdg?pwd=32as)（提取码: `32as`）
- 
# VSR_PLUS 1.0 — 字幕去除器增强版

> 从 My Video Tools 剥离出的**字幕去除专用模块**，仅保留字幕去除 + 超分辨率 + 帧插值核心功能，去除音频AI等附属功能。
| 平台 | 下载链接 |
|------|---------|
| Windows GPU (NVIDIA CUDA 12.6) | https://pan.baidu.com/s/1z3Zo-JzpuFXQGty8e8pELw?pwd=c6qq

**安装步骤：**

```powershell
# 1. 解压下载的 .7z 文件
# 2. 右键 scripts/setup_windows.ps1 → 「使用 PowerShell 运行」
# 3. 等待安装完成（Python 环境 + 依赖包 + AI 模型自动下载）
# 4. 双击「启动我的AI影音工具百宝箱.cmd」开始使用
```

### 从源码手动运行

适用于已经有 Python 3.12+ 环境的用户：

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

## � 使用指南

### 🎬 视频去字幕 — 基本流程

#### 1️⃣ 导入视频

- 点击 **「打开」** 按钮，选择视频文件（支持 MP4、FLV、WMV、AVI 等常见格式）
- 支持**多选**，批量添加多个视频到任务列表
- 添加后视频自动在左侧预览区域播放，任务列表显示每个文件的状态

#### 2️⃣ 定位字幕位置

- 拖动视频下方的 **进度条滑块** 快速浏览视频，找到字幕出现的画面
- **快捷键**：
  - `←` / `→`：前后跳转 1 秒
  - `Ctrl` + `←` / `Ctrl` + `→`：前后跳转 5 秒
  - `Shift` + `←` / `Shift` + `→`：前后跳转 1 帧

#### 3️⃣ 框选去除区域

- **右键** 在视频画面上点击 → 弹出上下文菜单
- 选择 **「新增选区」** → 在字幕区域 **按住左键拖拽** 即可画出绿色选框
- 支持 **多个选区**：可分别框选不同位置的字幕或水印（例如左上角台标 + 底部字幕）
- **调整选区**：点击已有选框的边缘拖拽调整大小，或拖拽选框内部移动位置
- **删除选区**：右键点击选框 →「删除选区」或选中后按 `Delete` 键
- 选框以 **相对坐标** 存储，切换视频帧后自动保留

> 💡 **提示**：如果字幕位置固定，框选一次后切换其他帧选区保持不变，无需重复框选。

#### 4️⃣ 设置去除参数

在右侧功能区配置核心参数：

| 参数 | 说明 |
|------|------|
| **修复算法** | 选择 AI 修复引擎：STTN（快速）、ProPainter（高质量）、E2FGVI（极致）、LaMa（动画适合）、OpenCV（传统方法） |
| **检测模型** | 选择 OCR 检测模型：PP-OCRv4/v5（文字检测）、SAM2（分割检测，适合不规则水印） |
| **处理深度** | 0-100 连续滑块，实时插值所有模型参数。数值越高效果越好，但速度越慢、显存占用越大 |
| **硬件加速** | 开启后使用 GPU（CUDA）加速推理，关闭则使用 CPU |
| **并发任务** | 同时处理多个视频的数量（1-8）。超出显存的选项自动标红 ⚠️ |

#### 5️⃣ 设置 A-B 分区（可选）

如果只想处理视频的 **某一段**（而非全片）：

- 定位到起始帧，按 `[` 键标记起点
- 定位到结束帧，按 `]` 键标记终点
- 进度条下方会出现白色分段标记
- 按 `\` 键（反斜杠）删除当前分段
- 支持多个 A-B 分段，不设置则处理全片

#### 6️⃣ 开始处理

- 点击 **「开始」** 按钮启动处理
- 处理过程中可实时查看：
  - 左侧预览区：原始画面（左）与修复后画面（右）对比
  - 底部「输出日志」Tab：查看详细处理日志
  - 底部「任务列表」Tab：查看每个任务的进度百分比
- 点击 **「停止」** 可随时终止正在处理的任务
- 处理完成后输出文件保存在原视频目录（或自定义输出目录），文件名自动添加 `_no_sub` 后缀

---

### 🎯 水印检测高级功能

展开「自定义水印」折叠区，可使用以下高级功能：

#### 水印模板截取

1. 点击 **「截取水印模板」** 按钮进入截取模式
2. 在视频画面上 **按住左键拖拽** 框选水印区域（蓝色虚线框）
3. 松开鼠标确认，系统自动保存水印模板
4. 后续处理时会基于模板进行特征匹配和修复

#### 选项开关

| 开关 | 说明 |
|------|------|
| **强力去水印** | 开启后遮罩膨胀 +50%，适合顽固水印残留（红色标识） |
| **强制全帧遮罩** | 在您框选的区域上对所有帧强制生成遮罩，不依赖 OCR 检测（橙色标识） |
| **时序中值滤波** | 对遮罩区域做跨帧中值滤波，消除变色/变形/闪动文字（蓝色标识） |

#### 多循环暴力扫除

针对 AI 生成视频中**快速变化/扭曲/变形的 Logo 水印**：

1. 点击 **「多循环暴力扫除」** 按钮开启（按钮变绿）
2. 设置 **扫除次数**（1-10 轮），推荐 2-3 轮，重度变形可用 4-5 轮
3. 每轮执行：变形自适应遮罩 → RGB 密度聚类 → 模型推理 → 亮色残留压制 → 自适应混合
4. 上一轮输出作为下一轮输入，逐步磨除顽固水印
5. 处理时间 = 轮数 × 单轮时间，输出文件名包含轮数信息

---

### 📝 字幕提取

#### 一键提取

1. 打开视频后，在右侧「字幕提取」功能区选择**提取模式**：
   - **按行提取**：按 Y 轴分组，适合横向字幕（默认）
   - **按列提取**：按 X 轴分组，适合竖向排列文字
   - **提取浮动字幕**：位置聚类合并，适合动态/浮动水印字幕
2. 点击 **「一键提取」** 按钮
3. 提取结果自动显示在右侧预览区和底部「字幕文本」Tab

#### 导出字幕

- **「导出文本」**：导出为纯文本文件 (.txt)，不含时间轴
- **「导出 SRT」**：导出为标准字幕文件 (.srt)，含时间轴信息

#### 联合校对

使用多个 OCR 模型分别提取后合并去重，获得最高准确率：

1. 展开 **「联合校对（多模型择优）」** 折叠区
2. 选择三个不同的检测模型（如 PP-OCRv4 Server、PP-OCRv5 Server、SAM2-Base）
3. 点击 **「执行校对」**，系统依次用三个模型提取后合并去重
4. 结果自动显示在预览区

---

### ⚙️ 高级设置

点击 **「⚙ 高级设置」** 按钮进入高级设置页面，可调节：

- **字幕检测**：检测阈值、最小文本高度、遮罩扩展像素等
- **STTN 修复**：帧间隔、参考帧数、膨胀系数等
- **ProPainter 修复**：子网格大小、步长、下采样因子等
- **系统设置**：输出目录、语言、主题（亮色/暗色）、更新检查等

---

### 🧠 显存管理

展开「显存估算与监控」折叠区：

- **GPU 显存总量**：自动检测并显示当前 GPU 型号与显存
- **当前配置预估**：根据选择的模型和并发数实时估算显存占用
- **显存监控开关**：开启后每次处理自动采集 GPU 显存峰值，写入本地记录
- **模型显存参考表**：内置 14 个模型的 VRAM 基准值，真实采集值优先显示
- **并发选项标红**：超出显存的并发数自动以红色 ⚠️ 标记

---

## �📁 项目结构

```
resources/
├── gui.py                     # GUI 主入口
├── backend/
│   ├── main.py                # 字幕去除核心
│   ├── config.py              # 全局配置
│   ├── inpaint/               # 修复算法
│   ├── tools/                 # 工具模块
│   └── audio_studio/          # 🆕 AI 音频工作室
│       ├── core/              # VoxCPM2 + ACE 引擎封装
│       ├── webui/             # Gradio WebUI
│       ├── config.py          # 音频配置
│       └── download_models.py # 模型下载
├── ui/
│   ├── home_interface.py      # 主页
│   ├── audio_ai_page.py       # 🆕 AI 音频页面
│   ├── ai_video_generation_page.py # 🆕 AI 视频生成
│   ├── video_editor_page.py   # 🆕 视频编辑器
│   └── component/
├── config/
└── models/

vendor/                          # 🆕 第三方 AI 项目
└── ai_audio/
    ├── voxcpm2/                 # VoxCPM2 语音合成
    ├── ace_step/                # ACE-Step 1.5 音乐生成
    └── models/                  # 共享模型缓存
```

> 详细技术文档请见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## ❓ 常见问题

**Q: 提示"无法找到模型文件"？**
A: 如果是源码安装包，请先运行 `scripts/setup_windows.ps1` 完成全部安装。
   首次运行会自动从 GitHub Releases 下载 AI 模型（~700MB），请确保网络连接正常并有足够磁盘空间。
   如果自动下载失败，可手动运行 `python scripts/download_models.py` 重试下载。

**Q: GPU 显存不足怎么办？**
A: 降低"处理深度"滑块、减少并发任务数、选择轻量模型（PP-OCRv4 Mobile + STTN）。

**Q: E2FGVI 无法运行？**
A: E2FGVI 需要 48GB+ VRAM。您的 GPU 显存不足时会显示红色警告，建议使用 ProPainter 替代。

**Q: 字幕提取没有结果？**
A: 尝试切换提取模式（按行/按列/浮动），或更换检测模型（PP-OCRv5 Server 精度最高）。

---

## 📄 许可与致谢

### 本项目许可证
- **主程序**: [Apache License 2.0](resources/LICENSE)
- **仓库地址**: https://github.com/Rambolv/My_Video_Tools

### 参考与集成的第三方项目

本项目在 VSR 基础上集成了多个优秀的开源 AI 项目，各自遵循其原始许可证：

| 项目 | 说明 | 许可证 | 集成方式 |
|------|------|--------|---------|
| [YaoFANGUK/video-subtitle-remover](https://github.com/YaoFANGUK/video-subtitle-remover) | 原版 VSR v1.4.0，视频字幕去除基础框架 | Apache 2.0 | 本项目的原始基础 |
| [OpenBMB/VoxCPM2](https://github.com/OpenBMB/VoxCPM2) | 语音合成引擎（TTS/音色克隆/声音设计） | MIT | `vendor/ai_audio/voxcpm2/` |
| [ACE-Step/acestep-v15](https://github.com/ACE-Step/acestep-v15) | ACE-Step 1.5 音乐生成引擎 | Apache 2.0 | `vendor/ai_audio/ace_step/` |
| [xinntao/Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) | 通用超分辨率算法 | BSD 3-Clause | pip 包 `realesrgan` |
| [waifu2x-ncnn-vulkan](https://github.com/nihui/waifu2x-ncnn-vulkan) | 动漫超分辨率 ncnn 后端 | MIT | `resources/backend/tools/waifu2x_ncnn_backend.py` |
| [rife-ncnn-vulkan](https://github.com/nihui/rife-ncnn-vulkan) | RIFE 帧插值 ncnn 后端 | MIT | `resources/backend/tools/rife_ncnn_backend.py` |
| [PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) | OCR 文本检测与识别 | Apache 2.0 | pip 包 `paddleocr` |
| [facebookresearch/sam2](https://github.com/facebookresearch/sam2) | SAM2 分割模型 | Apache 2.0 | pip 包 `sam2` |
| [ProPainter](https://github.com/sczhou/ProPainter) | 视频修复算法（光流传播） | MIT | `resources/backend/inpaint/propainter_inpaint.py` |
| [STTN](https://github.com/researchmm/STTN) | 时序修复 Transformer | MIT | `resources/backend/inpaint/sttn_*_inpaint.py` |
| [E2FGVI](https://github.com/MCG-NKU/E2FGVI) | 高质量时序修复（CVPR 2022） | MIT | `resources/backend/inpaint/e2fgvi_inpaint.py` |
| [LaMa](https://github.com/advimman/lama) | 图像修复（大遮罩修复） | Apache 2.0 | `resources/backend/inpaint/lama_inpaint.py` |
| [qfluentwidgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets) | Fluent Design UI 组件库 | Apache 2.0 | pip 包 `qfluentwidgets` |

### 功能特性概览

| 模块 | 功能 | 说明 |
|------|------|------|
| **视频去字幕水印** | 6 种修复算法 | STTN、ProPainter、E2FGVI、LaMa、OpenCV |
| | 8 种检测模型 | PP-OCRv4/v5 Server/Mobile、SAM2 Tiny/Small/Base/Large |
| | 处理深度滑块 | 0-100 连续调节，实时插值所有模型参数 |
| | 多循环暴力扫除 | 针对 AI 变形水印的多轮渐进清除 |
| | 水印模板匹配 | 截取/旋转缩放匹配/颜色传播/强力清扫 |
| | 并发处理 | 1-8 任务并行，智能 VRAM 标红预警 |
| **视频增强** | Real-ESRGAN 超分 | Python CUDA / ncnn 双后端，4 种模型 |
| | waifu2x 动漫超分 | ncnn-Vulkan 后端，cunet / upconv_anime |
| | RIFE 帧插值 | Python CUDA / ncnn 双后端，2x/3x/4x/8x |
| | 组合管道 | 超分→插帧 或 插帧→超分，任意串联 |
| **AI 音频工作室** | VoxCPM2 语音引擎 | TTS、音色克隆、声音设计、声音转换（48kHz） |
| | ACE-Step 1.5 音乐引擎 | 文生音乐、歌词生曲、续写/重绘/翻唱、音源分离、LoRA |
| | 统一 Gradio WebUI | 端口自检、路径可配置、中文帮助系统 |
| **智能资源管理** | VRAM 监控 | 被动采集+主动调度，颜色编码预警（红/橙/黄/绿） |
| | GPU 检测式让步 | 基于 `torch.cuda.synchronize()` 智能检测，仅模型处理时生效 |
| | 模型主动卸载 | 任务完成后自动 `unload_inpaint_models()` 释放显存 |
| | AI 音频模型 ~14GB | 下载脚本支持国内镜像（hf-mirror.com / ModelScope） |

---

**原项目**: [YaoFANGUK/video-subtitle-remover](https://github.com/YaoFANGUK/video-subtitle-remover)
