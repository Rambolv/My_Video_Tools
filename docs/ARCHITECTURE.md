# VSR魔改版 - 技术架构文档

[English](ARCHITECTURE_EN.md) | 简体中文

## 1. 项目概述

**VSR (Video Subtitle Remover)** 是一款基于 AI 的视频硬字幕去除工具，支持 GPU 加速，
提供图形化界面（PySide6 + qfluentwidgets）和命令行两种使用方式。

- **版本**: 1.4.0
- **许可证**: Apache 2.0
- **原项目地址**: https://github.com/YaoFANGUK/video-subtitle-remover
- **Python 版本**: 3.12+
- **GUI 框架**: PySide6 6.9.0 + qfluentwidgets 1.7.7

---

## 2. 整体架构

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
│  │  字幕去除主流程: 检测 → 分组 → 修复 → 输出          │  │
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

## 3. 目录结构

```
resources/
├── gui.py                          # 主窗口入口 (PySide6/FluentWindow)
├── backend/
│   ├── main.py                     # SubtitleRemover 核心类
│   ├── config.py                   # 全局配置 (qfluentwidgets QConfig)
│   ├── inpaint/                    # 图像修复算法实现
│   │   ├── sttn_auto_inpaint.py    # STTN 智能擦除
│   │   ├── sttn_det_inpaint.py     # STTN 字幕检测
│   │   ├── propainter_inpaint.py   # ProPainter
│   │   ├── e2fgvi_inpaint.py       # E2FGVI
│   │   ├── lama_inpaint.py         # LaMa
│   │   └── opencv_inpaint.py       # OpenCV 传统修复
│   ├── tools/
│   │   ├── constant.py             # 枚举常量 (InpaintMode, SubtitleDetectMode)
│   │   ├── subtitle_detect.py      # SubtitleDetect 字幕检测
│   │   ├── subtitle_extractor.py   # SubtitleExtractor 字幕提取
│   │   ├── vram_estimator.py       # VRAM 显存估算器
│   │   ├── vram_monitor.py         # VRAM 被动监控器
│   │   ├── model_config.py         # 模型路径配置
│   │   ├── hardware_accelerator.py # 硬件加速抽象层
│   │   ├── ffmpeg_cli.py           # FFmpeg 封装
│   │   ├── version_service.py      # 版本更新服务
│   │   ├── process_manager.py      # 进程管理器
│   │   ├── inpaint_tools.py        # 修复工具函数
│   │   ├── common_tools.py         # 通用工具
│   │   ├── ocr.py                  # OCR 坐标转换
│   │   ├── watermark_detect.py     # 水印模板检测
│   │   ├── sam2_detect.py          # SAM2 水印检测
│   │   └── concurrent/             # 并发任务管理
│   ├── models/                     # AI 模型文件
│   └── scenedetect/                # 场景检测
├── ui/
│   ├── home_interface.py           # 主页界面
│   ├── setting_interface.py        # 设置面板
│   ├── advanced_setting_interface.py # 高级设置页
│   ├── component/
│   │   ├── func_card.py            # 可折叠功能卡片 + 帮助按钮
│   │   ├── video_display_component.py  # 视频显示组件
│   │   ├── task_list_component.py  # 任务列表组件
│   │   └── watermark_template_widget.py # 水印模板管理
│   └── icon/
│       └── my_fluent_icon.py       # 自定义图标
├── config/
│   └── config.json                 # 持久化配置 (qconfig JSON)
├── design/                         # UI 设计资源
├── docker/                         # Docker 配置
└── test/                           # 测试文件
```

---

## 4. 核心模块说明

### 4.1 字幕检测管道 (`subtitle_detect.py`)

```python
SubtitleDetect
├── text_detector          # PaddleOCR TextDetector (cached_property)
├── detect_subtitle(img)   # 单帧检测 → [(xmin,xmax,ymin,ymax), ...]
├── detect_subtitle_with_watermark(img, frame_no)
│                          # OCR + 水印联合检测
├── find_subtitle_frame_no(sub_remover)
│                          # 全视频扫描 → {frame_no: [rects]}
├── find_continuous_ranges_with_same_mask(dict)
│                          # 连续帧区间分组
├── filter_and_merge_intervals(intervals, target_length)
│                          # 区间过滤与合并
├── get_scene_div_frame_no(v_path)
│                          # 场景分割点检测
└── unify_regions(regions) # 区域统一化
```

### 4.2 字幕提取器 (`subtitle_extractor.py`)

```python
SubtitleExtractor
├── extract(mode)          # 全流程提取 (row/column/float)
├── results_to_srt()       # → SRT 格式（含时间轴）
├── results_to_text()      # → 纯文本格式
└── _merge_by_mode()       # 按行/列/浮动模式合并OCR结果
```

### 4.3 修复算法管道

```
SubtitleRemover.run()
├── 加载视频/模型
├── find_subtitle_frame_no()  # 检测字幕帧
├── 区间分组 → 场景分割 → 区间合并
├── 按 inpaintMode 选择修复引擎:
│   ├── STTN (auto/det)   → sttn_auto_inpaint / sttn_det_inpaint
│   ├── ProPainter         → propainter_inpaint (高显存/高效果)
│   ├── E2FGVI             → e2fgvi_inpaint (48GB+ VRAM)
│   ├── LaMa               → lama_inpaint (动画类)
│   └── OpenCV             → opencv_inpaint (快速/低质量)
├── 逐区间修复 → 合并音频 → 输出
```

### 4.4 VRAM 显存估算 (`vram_estimator.py`)

```
内置基准 (1080p):
  OpenCV:     0.3 GB    | STTN-Auto:   2.8 GB
  STTN-Det:   2.5 GB    | LaMa:        2.2 GB
  E2FGVI:    48.0 GB    | ProPainter: 13.0 GB
  PP-OCRv4-S: 0.8 GB    | PP-OCRv4-M:  0.4 GB
  PP-OCRv5-S: 1.0 GB    | PP-OCRv5-M:  0.5 GB
  SAM2-Tiny:  3.5 GB    | SAM2-Small:  5.0 GB
  SAM2-Base: 10.0 GB    | SAM2-Large: 18.0 GB

处理深度系数: depth=0 → 0.55x, depth=100 → 2.00x
分辨率缩放: 以 1080p(1920x1080) 为基准线性缩放
```

### 4.5 UI 组件体系

```
FluentWindow (gui.py)
├── HomeInterface (主页)
│   ├── QSplitter (水平)
│   │   ├── 左: QSplitter (纵向)
│   │   │   ├── VideoDisplayComponent (视频预览)
│   │   │   └── QTabWidget (任务列表/输出日志/字幕文本)
│   │   └── 右: QScrollArea
│   │       ├── CollapsibleFuncCard "视频去字幕水印功能"
│   │       │   ├── 核心设置 (修复算法/检测模型/处理深度)
│   │       │   ├── 性能设置 (硬件加速/并发任务)
│   │       │   ├── ▶ 水印检测
│   │       │   ├── ▶ 显存估算与监控
│   │       │   └── 操作按钮
│   │       └── CollapsibleFuncCard "字幕提取"
│   │           ├── 一键提取/导出文本/导出SRT
│   │           └── ▶ 联合校对
│   └── AdvancedSettingInterface (高级设置页)
│       ├── 字幕检测设置
│       ├── STTN/ProPainter 设置
│       └── 关于
```

---

## 5. 数据流

### 5.1 视频去字幕流程

```
输入视频
  │
  ▼
[SubtitleDetect] ─── OCR 文本检测 ──→ 字幕框坐标
  │
  ▼
[区间分组] ─── 连续帧合并 + 场景分割
  │
  ▼
[选择修复引擎] ─── 根据 processingDepth 插值参数
  │
  ├──→ STTN:     参考帧步长/数量 ← depth 插值
  ├──→ ProPainter: mask膨胀/光流   ← depth 插值
  ├──→ E2FGVI:   最大加载帧数     ← depth 插值
  │
  ▼
[逐区间修复] ─── 生成 mask → 修复 → 写入临时帧
  │
  ▼
[合并输出] ─── 音频复制 → 封装输出文件
```

### 5.2 字幕提取流程

```
输入视频
  │
  ▼
[SubtitleDetect.find_subtitle_frame_no()]
  │  → 逐帧检测字幕框
  ▼
[区间分组] (find_continuous_ranges_with_same_mask)
  │
  ▼
[OCR 识别] ─── 取代表帧 → PaddleOCR.ocr()
  │  mode = row    → 按 Y 轴分组排序
  │  mode = column → 按 X 轴分组排序
  │  mode = float  → 位置聚类合并
  ▼
[去重合并] ─── 渐进文本检测 → 时间窗口去重
  │
  ▼
[输出]
  ├── results_to_srt()  → SRT 格式 (左侧 Tab)
  └── results_to_text() → 纯文本 (右侧预览)
```

---

## 6. 配置系统

基于 `qfluentwidgets.qconfig`，配置文件为 `config/config.json`。

**配置分组**:
| 分组 | 说明 |
|------|------|
| `Window` | 窗口位置、语言 |
| `Main` | 核心算法、处理深度、并发数 |
| `Sttn` | STTN 参数 |
| `ProPainter` | ProPainter 参数 |
| `E2FGVI` | E2FGVI 参数 |
| `Watermark` | 水印检测参数 |
| `UI` | 折叠状态持久化 |
| `SubtitleExtract` | 字幕提取模式 |

---

## 7. 关键技术依赖

| 依赖 | 版本 | 用途 |
|------|------|------|
| PySide6 | 6.9.0 | GUI 框架 |
| qfluentwidgets | 1.7.7 | Fluent Design 组件 |
| PaddleOCR | 2.10.0 | OCR 检测与识别 |
| paddlepaddle | 3.0.0 | 深度学习框架 |
| PyTorch | 2.7.0 | 深度学习框架 (修复模型) |
| OpenCV | 4.11.0 | 视频处理/图像处理 |
| FFmpeg | (系统) | 视频编码/解码/封装 |
| ONNX Runtime | 1.20.1 | 模型推理加速 |

---

## 8. 并发模型

- **GUI 线程**: 主线程处理所有 UI 操作
- **工作进程**: `multiprocessing.Process` 执行字幕去除任务
- **后台线程**: `threading.Thread` 执行字幕提取/VRAM监控
- **任务队列**: `ThreadPoolExecutor` 管理并发任务
- **进程管理**: `ProcessManager` 统一管理子进程生命周期
- **进程间通信**: `multiprocessing.Queue` + 回调注册模式

---

## 9. 扩展点

1. **新增修复算法**: 在 `InpaintMode` 枚举中添加 → 实现 inpaint 类 → 在 `SubtitleRemover.run()` 中添加分支
2. **新增检测模型**: 在 `SubtitleDetectMode` 枚举中添加 → 在 `ModelConfig` 中添加模型路径 → 实现检测逻辑
3. **新增字幕提取模式**: 在 `_merge_by_mode()` 中添加分支 → 在 UI 组合框中添加选项
4. **新增 UI 页面**: 在 `gui.py` 中创建子界面 → 通过 `addSubInterface()` 添加到导航
