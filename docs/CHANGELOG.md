# VSR魔改版 变更日志  <!-- LVBOBO_markdown_BUG -->

[English](CHANGELOG_EN.md) | 简体中文

## v1.4.0 (当前版本)

### ✨ 新增功能

- **处理深度滑块**：0-100 连续可拖动，实时插值所有模型参数（mask膨胀、时间线、参考帧等）
- **字幕提取功能**：基于 PaddleOCR 的全流程字幕提取，支持按行/按列/浮动三种模式
- **联合校对**：三个不同 OCR 模型分别提取后合并择优
- **VRAM 被动监控**：跟随正常工作流程自动采集 GPU 显存峰值，写入 `vram_records.json`
- **显存估算参考表**：所有模型的显存基准值，优先显示真实采集值，OOM 标记 ☠️
- **并发任务显存标红**：超出显存的并发数自动红色 ⚠️ 标记
- **E2FGVI 显存警告**：选择 E2FGVI 时检测 GPU 显存，不足 48GB 显示警告
- **帮助按钮系统**：所有控件旁 `?` 按钮，点击弹出详细说明，悬停显示工具提示
- **可折叠功能卡片**：支持持久化折叠状态（保存到 config.json）
- **可拖拽分割器**：主界面使用 QSplitter，所有区域可拖拽调整大小
- **自动换行**：输出日志/字幕文本自动换行，按钮自适应大小

### 🎨 UI 改进

- 功能区重新布局：左侧视频预览 + 底栏 Tab，右侧两个功能大区
- 视觉层次区分：SectionHeader（蓝色边框）、子功能区缩进+左边框线
- 滑块手柄放大：从 8px → 18px 圆形蓝色手柄
- 三种字幕提取模式下拉框：按行/按列/浮动
- 左侧 Tab「字幕文本」显示 SRT 格式，右侧预览显示纯文本
- 导出文本 / 导出 SRT 双按钮

### 🔧 技术改进

- 原有 `OptionsConfigItem` 处理深度改为 `RangeConfigItem(0-100)` 连续范围
- `SubtitleExtractor` 模块：全流程字幕提取管道
- `SubtitleDetect.find_subtitle_frame_no()` 传入 mock 对象避免 None 崩溃
- 线程安全 UI 更新：使用信号槽替代直接跨线程调用
- `_SimpleCollapsible` 重构：持久的展开/折叠状态

### 🐛 Bug 修复

- 修复 `PrimaryPushButton::setText` 跨线程调用找不到元方法问题
- 修复 `find_subtitle_frame_no(sub_remover=None)` 导致的 AttributeError
- 修复 `on_scroll_change` 方法被错误合并到 `_open_advanced_settings`
- 修复联合校对模型名匹配（空格 vs 连字符）

---

## v1.3.x (历史版本)

### 主要功能
- 基于 PaddleOCR 的 PP-OCRv4/v5 字幕文本检测
- SAM2 水印检测模型支持（Tiny/Small/Base/Large）
- ProPainter 高质量视频修复算法
- STTN 时序修复算法（Auto + Det 两种模式）
- LaMa 修复算法（动画类视频优化）
- E2FGVI 高质量时序修复算法
- OpenCV 传统修复算法（快速模式）
- 水印模板匹配检测（含模板截取、颜色传播、强力清扫）
- 并发任务处理（1-8 个并发任务）
- 硬件加速开关（CUDA/ONNX）
- 多语言界面支持
- 版本更新检查

---

## v1.2.x

### 主要功能
- 基础字幕检测与去除管道
- 图形化界面（PySide6 + qfluentwidgets）
- 视频预览与选区绘制
- 任务列表管理
- 场景检测分割

---

## v1.1.0 (初始发布)

### 主要功能
- 基于 AI 的视频硬字幕去除
- 支持 GPU 加速（CUDA 11.8 / 12.6）
- Windows/macOS/Linux 多平台支持
- Docker 部署支持
- 预构建包分发型（CPU/DirectML/CUDA 多版本）
