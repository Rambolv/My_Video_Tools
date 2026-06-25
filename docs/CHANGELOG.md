# 我的AI影音工具百宝箱 - 变更日志  <!-- LVBOBO_markdown_BUG -->

[English](CHANGELOG_EN.md) | 简体中文

## v1.4.0 (当前版本)

### ✨ 新增功能

- **AI 音频工作室 (audio_studio)**：集成 VoxCPM2 语音合成引擎和 ACE-Step 1.5 音乐生成引擎
  - 语音合成 (TTS)、音色克隆、声音设计、声音转换
  - 文生音乐、歌词生曲、续写、重绘、翻唱、音源分离、LoRA 训练
  - 统一 Gradio WebUI 入口，支持一键启动
- **GPU 检测式让步机制**：`_gpu_yield_if_busy()` — 基于 torch.cuda.synchronize() 耗时判断 GPU 繁忙度
  - 仅在模型加载处理中启用，空闲时零开销
  - 检测间隔自动调整：空闲 10s → 繁忙 0.5s
- **VRAM 泄漏修复**：`@cached_property` 重绘模型改为 `@property` + 手动缓存，新增 `unload_inpaint_models()` 方法主动卸载
- **模型下载工具**：`download_models.py` 支持 --mirror 参数（auto/huggingface/hf-mirror/modelscope）
- **自动关机/退出**：任务完成后 5 秒倒计时自动关机或退出程序
- **vendor 目录重构**：按 AI 领域划分 `ai_audio/`、`ai_video/`、`ai_video_edit/`
- **路径内化**：所有外部 AI 项目路径迁移到 `vendor/ai_audio/` 下，不再依赖原始目录
- **端口自动检测**：Gradio WebUI 端口冲突时自动递增
- **配置持久化**：`user_config.json` 保存用户自定义路径设置

- **视频增强系统**：超分辨率(Real-ESRGAN) + waifu2x 动漫超分 + 帧插值(RIFE) 三大增强模块
- **增强管道串联**：超分→插帧 或 插帧→超分 两种处理顺序，支持任意组合
- **三种 ncnn 后端**：Real-ESRGAN ncnn、RIFE ncnn、waifu2x ncnn 独立后端封装
- **VRAM 主动调度系统**：显存压力实时监控 + 自适应批次大小 + 动态 GPU 内存回收
- **多任务分阶段调度**：字幕/SR/FI 模型分阶段加载，防止显存叠加 OOM
- **锁定专用显存**：防止 Windows WDDM 溢出到共享内存，可开关控制
- **GPU 实时监控弹窗**：nvidia-smi 轮询进程 GPU 占用，按计算负载排序
- **STTN 字幕处理管线全面优化**：速度提升 30~50%，显存降低 50%
- **多循环扫除管线优化**：推理次数 3x→2x、导入机制优化、窗口缩减
- **AI 功能导航页面**：AI 视频生成、AI 音频、视频编辑器三个独立导航页
- **统一打赏弹窗组件**：所有页面的捐赠入口统一管理
- **配置方案管理**：`config_profile.py` 支持多配置方案保存/切换
- **资源管理器**：`resource_manager.py` 统一管理模型下载与路径
- **水印追踪模块**：`watermark_tracker.py` 跨帧水印位置预测与追踪
- **主题切换监听**：`theme_listener.py` 实时响应系统亮/暗色主题切换
- **视频合并工具**：`merge_video.py` 支持多片段视频合并
- **模型兼容层**：`model_compat.py` 处理模型版本兼容问题
- **命令行参数处理**：`args_handler.py` CLI 参数解析
- **打包分发工具**：`makedist.py` 发布包自动化构建

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
