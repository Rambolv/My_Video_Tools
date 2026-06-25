---
name: vsr-dev-history
description: "我的AI影音工具百宝箱全量开发历程、设计思维、架构演进与发布策略"
applyTo: "**/*.{py,md,ps1,cmd}"
---

# 我的AI影音工具百宝箱 — 开发历程与设计思维

## 一、项目概述

基于 [YaoFANGUK/video-subtitle-remover](https://github.com/YaoFANGUK/video-subtitle-remover) v1.4.0 深度二次开发，专注于视频硬字幕/水印去除的 AI 工具。

**本仓库**: https://github.com/Rambolv/My_Video_Tools

## 二、功能开发历程（按优先级排序）

### 2.1 核心算法增强

#### 1. 处理深度滑块 (Processing Depth Slider)
- **设计思维**: 原版各模型参数（mask膨胀、时间线、参考帧等）分散在各设置页，用户难以调优
- **解决方案**: 单一 0-100 滑块通过线性插值(lerp)联动所有参数，一键在速度与质量间平衡
- **关键代码**: `resources/backend/main.py` 中 `apply_processing_depth()` 函数
- **插值映射**:
  ```
  depth=0  → mask膨胀=5px,  时间线=±1帧,  STTN参考=5帧
  depth=50 → mask膨胀=17px, 时间线=±5帧,  STTN参考=12帧
  depth=100→ mask膨胀=30px, 时间线=±10帧, STTN参考=20帧
  ```

#### 2. 多循环暴力扫除 (Multi-Sweep Mode)
- **设计思维**: AI生成视频水印每帧变形扭曲，单次修复无法彻底清除
- **算法管道**: 变形自适应遮罩 → 密度峰值RGB背景聚类(31帧) → 强时序中值滤波(15帧) → 3次模型推理加权(50%+30%+20%) → 亮色残留压制 → 残留边缘检测填充 → 自适应原始保护混合 → 锐化羽化
- **多轮机制**: 每轮输出作为下轮输入，逐轮渐进清除
- **详见**: `.claude/skills/multi-sweep-watermark-removal.md`

#### 3. 水印模板匹配检测
- **功能**: 支持用户截取水印样本 → 旋转/缩放模板匹配 → 特征匹配 + 颜色传播 + 强力清扫（时序差分）+ 强制区域重绘
- **组件**: `resources/ui/component/watermark_template_widget.py`

#### 4. 新增修复引擎
- **ProPainter**: 高质量视频修复，需 13GB+ VRAM，适合剧烈运动场景
- **E2FGVI** (CVPR 2022): 流式视频修复，支持任意分辨率，需 48GB+ VRAM
- **SAM2 检测**: 新增 Tiny/Small/Base/Large 四档分割模型
- **PP-OCRv5**: 升级支持最新 OCR 检测模型

### 2.2 字幕提取系统

#### 1. 全流程字幕提取
- 自动检测 → OCR识别 → 去重合并 → 多格式导出
- **三种模式**: 按行(Y轴聚类) / 按列(X轴聚类) / 浮动(欧氏距离聚类)
- **模块**: `resources/backend/tools/subtitle_extractor.py`

#### 2. 联合校对
- 3个不同OCR模型依次提取 → 合并去重择优 → 输出SRT+纯文本
- **互斥约束**: 三个模型不可重复

### 2.3 UI/UX 全面重构

| 特性 | 设计要点 |
|------|---------|
| **PySide6 + qfluentwidgets** | 从 PySimpleGUI 全面迁移，Fluent Design 风格 |
| **可拖拽分割面板** | QSplitter 水平+纵向布局，所有区域自由调整 |
| **可折叠功能区** | `_SimpleCollapsible` 组件，状态持久化到 config.json |
| **帮助按钮系统** | 每个控件旁 ? 按钮，点击 MessageBox / 悬停 ToolTip |
| **启动弹窗** | 项目信息 + 硬件推荐 + 捐赠二维码 + "我已捐助"累计计数 |
| **窗口位置记忆** | 自动保存/恢复窗口位置大小 |
| **主题切换** | 亮色/暗色主题无缝切换 |
| **多语言支持** | 简体中文 / English / 日本語 / 한국어 / Tiếng Việt / Español |

### 2.4 VRAM 显存智能管理

- **被动监控**: 每 0.5s 采样 GPU 显存峰值，写入 `vram_records.json`
- **估算参考表**: 内置 14 个模型 VRAM 基准值，真实采集值优先
- **并发标红**: 超出显存的选项自动红色 ⚠️ 标记
- **颜色编码**: ≥95%红 / ≥85%橙 / ≥70%黄 / <70%绿

### 2.5 技术架构改进

- **场景检测**: 基于帧间差异的场景切换检测，优化区间分组
- **硬件加速抽象层**: 统一 CUDA / ONNX 接口
- **FFmpeg CLI 封装**: 视频编解码/音频合并
- **进程管理器**: multiprocessing 子进程生命周期管理
- **线程安全 UI**: 信号槽替代直接跨线程调用
- **分片模型合并**: fsplit 大模型分片存储，首次运行自动合并

## 三、合规清理 (Compliance Cleanup)

- **移除内容**: 百度网盘下载链接、Baidu Pan/Disk 品牌引用
- **保留内容**: Alipay 捐赠二维码、WeChat 图片文件
- **标记**: 所有修改处标注 `LVBOBO_markdown_BUG` 标记
- **配置文件**: `startup_dialog.py` 中捐赠计数默认重置为 0

## 四、发布策略

### 4.1 源码包方案（推荐）
- **包名**: `VSR-Source-v1.4.0.7z` (仅 0.3MB)
- **内容**: 纯 Python 源代码，不含运行环境和模型
- **安装**: `scripts/setup_windows.ps1` 一键脚本
  - 自动下载 Python 3.12 嵌入式环境
  - pip 安装全部依赖（torch, paddlepaddle, opencv 等）
  - 从 GitHub Releases 下载 AI 模型（~700MB）
  - 创建启动快捷方式

### 4.2 模型管理
- **工具**: `scripts/download_models.py`
- **来源**: GitHub Releases 标签 `models-v1.0`
- **模型清单**: big-lama(~196MB), propainter(~190MB), sttn-auto(~63MB), sttn-det(~63MB), ocr-v4-server(~108MB), ocr-v4-mobile(~5MB), ocr-v5-server(~84MB), ocr-v5-mobile(~5MB)

### 4.3 打包工具
- `scripts/build_minimal_package.ps1` — 构建仅含源码的发布包

## 五、Git 管理规范

- **主分支**: `main`（GitHub 默认分支）
- **提交规范**: `type: message` 格式（feat/fix/docs/chore）
- **敏感文件**: `config/`, `Python/`, `*.log`, `*.pth`, `*.onnx` 在 `.gitignore` 中排除

## 六、相关文件索引

| 领域 | 文件路径 |
|------|---------|
| 主处理逻辑 | `resources/backend/main.py` |
| 全局配置 | `resources/backend/config.py` |
| 模型配置+自动下载 | `resources/backend/tools/model_config.py` |
| 字幕检测 | `resources/backend/tools/subtitle_detect.py` |
| 字幕提取 | `resources/backend/tools/subtitle_extractor.py` |
| 水印检测 | `resources/backend/tools/watermark_detect.py` |
| 暴力扫除 | `resources/backend/tools/inpaint_tools.py` |
| VRAM估算 | `resources/backend/tools/vram_estimator.py` |
| VRAM监控 | `resources/backend/tools/vram_monitor.py` |
| 硬件加速 | `resources/backend/tools/hardware_accelerator.py` |
| 主页UI | `resources/ui/home_interface.py` |
| 设置页UI | `resources/ui/setting_interface.py` |
| 高级设置UI | `resources/ui/advanced_setting_interface.py` |
| 启动弹窗 | `resources/ui/component/startup_dialog.py` |
| 水印模板 | `resources/ui/component/watermark_template_widget.py` |
| 功能卡片 | `resources/ui/component/func_card.py` |
| 视频显示 | `resources/ui/component/video_display_component.py` |
| 任务列表 | `resources/ui/component/task_list_component.py` |
| 模型下载 | `scripts/download_models.py` |
| 一键安装 | `scripts/setup_windows.ps1` |
| 打包脚本 | `scripts/build_minimal_package.ps1` |

## 七、AI SKILL 索引

本项目的全部 AI SKILL 及其多维评价详见 **[vsr-skills-master-index](vsr-skills-master-index.md)**。

| SKILL | 领域 | 用途 |
|-------|------|------|
| [vsr-skills-master-index](vsr-skills-master-index.md) | 元认知 | 全部 SKILL 多维度分类评价总索引 |
| [multi-sweep-watermark-removal](multi-sweep-watermark-removal.md) | 算法 | 多循环暴力扫除算法设计文档 |
| [vsr-video-enhancement](vsr-video-enhancement.md) | 架构 | 视频增强模块（SR+FI）架构与后端规范 |
| [ui-audit-and-perf-optimization](ui-audit-and-perf-optimization.md) | 质量+性能 | UI死链审计方法论 + GPU管线性能优化模式 |
