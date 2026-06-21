---
name: ui-audit-and-perf-optimization
description: "UI控件死链审计方法 + GPU管线性能瓶颈诊断与FFmpeg管道优化模式"
applyTo: "**/*.py"
---

# UI控件死链审计 + GPU管线性能优化

> 本 SKILL 来自 VSR 项目的两次会话经验，总结了一套可复用的代码审查和性能优化方法论。

## 一、UI 控件死链审计方法论

### 1.1 审计流程

```
① 全局搜索信号连接 → ② 交叉验证处理程序存在性 → ③ 检查重复/覆盖 → ④ 验证配置持久化
```

### 1.2 检测模式（举一反三）

| 检测模式 | 搜索方式 | 实例 |
|---------|---------|------|
| **信号无处理程序** | `.clicked.connect` / `.currentTextChanged.connect` 缺失 | 下拉框创建后无 `.connect()` 调用 |
| **重复方法定义** | 同名 `def` 两次出现 → 第二个覆盖第一个 | `_on_power_sweep_changed` 定义两次 |
| **配置文件未同步** | `ConfigItem` 存在但 UI 不读不写 | `subtitleExtractMode` 配置项孤立 |
| **引用不存在对象** | 方法内 `self.xxx` 但类中无定义 | `update_progress()` 引用 `self.se` |
| **组件引用为 None** | 构造函数不传必需依赖 | `WatermarkTemplateWidget(video_display_component=None)` |
| **死代码类** | 类定义但全局搜索结果无实例化 | `SettingInterface` 全局搜索 0 实例化 |

### 1.3 本次 VSR 实际发现

| 严重程度 | 文件:行 | 问题 | 修复 |
|---------|--------|------|------|
| 🔴 中 | `watermark_template_widget.py:502` | `_on_power_sweep_changed` 重复定义，`_update_power_sweep_controls()` 被覆盖丢失 | 删除重复定义 |
| 🟡 低 | `home_interface.py:1081` | `_extract_mode_combo` 创建后未连接信号，选择不持久化 | 添加 `currentIndexChanged.connect()` |
| ⚫ 死码 | `gui.py:118-130` | `update_progress()` 引用不存在的 `self.se`/`self.video_slider` | 删除残留方法 |
| ⚫ 死码 | `setting_interface.py:81` | 343 行 `SettingInterface` 类全局无实例化 | 保留代码但标注 |

### 1.4 可复用审计脚本思路

```python
# 伪代码：检测所有信号连接对应的处理程序是否存在
for py_file in project_ui_files:
    for signal_match in find_signal_connections(py_file):
        handler_name = extract_handler(signal_match)
        if handler_name.startswith("lambda"):
            continue  # lambda 内联处理，跳过
        if not handler_exists_in_class(py_file, handler_name):
            report(f"死处理程序: {py_file}:{line}: {handler_name}")
```

---

## 二、GPU 管线性能瓶颈诊断

### 2.1 症状 → 根因映射

| 症状 | 根因 |
|------|------|
| GPU 利用率忽高忽低（锯齿波） | 串行逐帧循环：GPU 每帧等待 CPU I/O |
| 处理时间远超预期 | `cv2.VideoCapture` + `cv2.VideoWriter` 完全串行 |
| GPU 占用偶尔 0% | 帧解码/编码期间 GPU 完全空闲 |
| CPU 单核 100% | OpenCV 默认多线程编码与主线程竞争 GIL |

### 2.2 诊断检查清单

```
□ 处理循环是逐帧串行还是批量/流水线？
□ 帧读取方式：cv2.VideoCapture vs FFmpeg pipe？
□ 帧写入方式：cv2.VideoWriter vs FFmpeg pipe？
□ GPU 推理是否支持批处理（batch inference）？
□ 是否存在无谓的 GPU↔CPU 数据搬运（.cuda()/.cpu() 循环内调用）？
□ 磁盘 I/O 是否在主循环中（如 cv2.imwrite 逐帧写 PNG）？
□ 是否有不必要的内存复制（.copy() 在热路径中）？
```

### 2.3 性能分级：串行 → 流水线 → 批处理

```
Level 0 (串行):  read → GPU → write → read → GPU → write → ...
Level 1 (流水线): decode thread | GPU thread | encode thread  (本修复采用)
Level 2 (批处理):  decode batch → GPU batch → encode batch
Level 3 (管道批):   decode stream → GPU batch stream → encode stream
```

---

## 三、FFmpeg 管道 + 多线程流水线模式（核心模式）

### 3.1 架构图

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  FFmpeg 解码进程 │────▶│  帧队列 (Q_SIZE) │────▶│  Main 线程      │
│  stdout pipe     │     │  queue.Queue     │     │  GPU 推理       │
│  rawvideo rgb24  │     │  maxsize=8~32    │     │  逐帧/逐对       │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                      ┌─────────────────┘
                                      ▼
┌─────────────────┐     ┌─────────────────┐
│  FFmpeg 编码进程 │◀────│  结果队列        │
│  stdin pipe      │     │  queue.Queue     │
│  libx264 crf 18  │     │  maxsize=8~32    │
└─────────────────┘     └─────────────────┘
```

### 3.2 实现模板

```python
import subprocess, threading, queue
import numpy as np

def enhance_video_pipelined(input_path, output_path, fps, w, h, enhance_fn):
    ff = "ffmpeg"
    frame_size = w * h * 3
    out_w, out_h = w * scale, h * scale

    # FFmpeg 解码器 (→ stdout pipe)
    decoder = subprocess.Popen(
        [ff, "-i", input_path, "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-vcodec", "rawvideo", "-an", "-loglevel", "error", "-"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)

    # FFmpeg 编码器 (← stdin pipe)
    encoder = subprocess.Popen(
        [ff, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{out_w}x{out_h}", "-r", str(fps), "-i", "-",
         "-vcodec", "libx264", "-crf", "18", "-preset", "fast",
         "-pix_fmt", "yuv420p", "-loglevel", "error", output_path],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    Q_SIZE = 16
    frame_q = queue.Queue(maxsize=Q_SIZE)
    result_q = queue.Queue(maxsize=Q_SIZE)
    STOP = object()
    errors = {"err": None}

    # Reader thread
    def reader():
        try:
            while True:
                raw = decoder.stdout.read(frame_size)
                if not raw or len(raw) < frame_size: break
                frame_q.put(np.frombuffer(raw, dtype=np.uint8).reshape((h, w, 3)).copy())
        except Exception as e:
            errors["err"] = e
        finally:
            frame_q.put(STOP)

    # Writer thread
    def writer():
        try:
            while True:
                item = result_q.get()
                if item is STOP: break
                encoder.stdin.write(item.tobytes())
        except Exception as e:
            errors["err"] = e
        finally:
            encoder.stdin.close()

    threading.Thread(target=reader, daemon=True).start()
    threading.Thread(target=writer, daemon=True).start()

    # Main: GPU inference
    while True:
        frame = frame_q.get()
        if frame is STOP: break
        result_q.put(enhance_fn(frame))

    result_q.put(STOP)
    # cleanup: wait threads, kill procs if needed
```

### 3.3 关键参数选择

| 参数 | 推荐值 | 理由 |
|------|--------|------|
| `Q_SIZE` | `max(8, min(32, total_frames // 10))` | 自适应：视频越长队列越深，保证流水线不饿 |
| `-preset` | `fast` (非 `medium`) | GPU 连续输出时 CPU 编码必须跟上，fast 比 medium 快 2x |
| `-crf` | `18` (高质量) | 中间产物保持质量，避免二次编码损失 |
| `-pix_fmt` | `yuv420p` | 兼容性最好 |
| Daemon threads | `True` | 主进程退出时自动清理 |

### 3.4 适配帧插值（Frame Pairs）

SR 是逐帧独立处理，FI 需要帧对 (N, N+1)。适配方式：

```python
# 读取首帧直接写出
prev_frame = frame_q.get()
result_q.put(prev_frame)

while True:
    curr_frame = frame_q.get()
    if curr_frame is STOP: break
    mid_frames = interpolate(prev_frame, curr_frame, multiplier - 1)
    for mf in mid_frames:
        result_q.put(mf)
    result_q.put(curr_frame)
    prev_frame = curr_frame
```

### 3.5 ncnn 后端特殊处理

ncnn 二进制需要文件夹输入，不能用管道。优化手段：
- **帧提取**：用 `ffmpeg -q:v 1 %08d.png` 替代 `cv2.imwrite` 循环（快 3-5 倍）
- **视频组装**：用 `ffmpeg -framerate fps -i %08d.png` 替代 `cv2.VideoWriter` 循环
- GPU 利用率由 ncnn 二进制保证（内部连续处理所有帧）

---

## 四、适用场景

| 场景 | 适用模式 |
|------|---------|
| Python AI 模型逐帧推理 + 视频 I/O | ✅ FFmpeg 管道 + 线程流水线 |
| ncnn 外部二进制 + 文件夹输入 | ✅ FFmpeg 帧提取/组装提速 |
| 多进程并行任务 | ✅ 每个子进程独立管道，互不干扰 |
| 低延迟实时处理 | ⚠️ 管道引入 1-2 帧延迟，非零延迟场景可能不合适 |

## 五、相关文件

- `resources/backend/tools/video_enhancer.py` — Python SR/FI 管道实现
- `resources/backend/tools/sr_ncnn_backend.py` — ncnn SR 后端
- `resources/backend/tools/waifu2x_ncnn_backend.py` — waifu2x ncnn 后端
- `resources/backend/tools/rife_ncnn_backend.py` — RIFE ncnn 后端
- `resources/ui/home_interface.py` — UI 控件审计样本
- `resources/ui/component/watermark_template_widget.py` — 重复方法 BUG 样本
- `resources/gui.py` — 死代码残留样本
