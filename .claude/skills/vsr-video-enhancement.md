# VSR 魔改版 — 视频增强模块 (Super-Resolution + Frame Interpolation)

## 架构概览

```
video_enhancer.py (enhance_video_pipeline)
  ├── 超分辨率 (SR)
  │   ├── Real-ESRGAN Python CUDA
  │   │   └── 自动下载 .pth → resources/weights/
  │   ├── Real-ESRGAN ncnn-Vulkan (sr_ncnn_backend.py)
  │   │   └── 需 .bin/.param 模型 → resources/backend/tools/sr_ncnn/models/
  │   └── waifu2x-ncnn-Vulkan (waifu2x_ncnn_backend.py)
  │       └── 模型打包在 release 中 → resources/backend/tools/waifu2x_ncnn/models-*/
  └── 帧插值 (FI)
      ├── Python CUDA RIFE (内建)
      │   └── flownet.pkl → resources/models/rife/
      └── rife-ncnn-Vulkan (rife_ncnn_backend.py)
          └── 多模型可选 → resources/backend/tools/rife_ncnn/models/rife-v3.1/
```

## 关键设计决策

### 1. 超分模型+后端分离
- **问题**: waifu2x 是独立算法，不应放在 Real-ESRGAN 的"后端"选项中
- **方案**: 所有算法统一放在模型下拉，后端下拉仅控制 Real-ESRGAN 的执行方式
- **实现**: `config.srModelName` 包含 realesr-* 和 waifu2x-* 两类模型
- **UI**: 选 waifu2x 模型时后端下拉置灰不可用
- **路由**: `video_enhancer.py:634` — 判断 `model_name.startswith("waifu2x-")`

### 2. ncnn 目录模式 vs 逐对模式
- **问题**: 逐对调用 `-0 f0 -1 f1` 每帧对启动一次 exe，加载模型 → GPU 开销巨大
- **方案**: 用 `-i indir -o outdir` 目录模式一次处理全部帧
- **效果**: 300帧视频 2x 插值，exe 启动从 299 次降到 1 次
- **多倍率**: 多级 2x 插值后交错合并，非 2^n 倍率截取前 N 帧
- **线程控制**: `-j 2:4:4` 提高并行度

### 3. 国内镜像下载策略
所有自动下载需优先尝试 GitHub raw/releases，失败后依次尝试：
```
ghfast.top/https://github.com/...
ghproxy.com/https://github.com/...
mirror.ghproxy.com/https://github.com/...
```
模板参见 `rife_ncnn_backend.py` 中的 `_RAW_BASE_URLS`

### 4. 模型文件来源

| 模型 | 来源 | 下载方式 |
|------|------|---------|
| Real-ESRGAN .pth | GitHub Releases | 自动(basicsr) |
| realesrgan-ncnn .bin/.param | GitHub LFS（不可用） | 跳过, 用 Python 后端 |
| waifu2x-ncnn .bin/.param | release 中打包 | ghfast.top 直接下载 35MB |
| rife-ncnn .bin/.param | GitHub raw 逐文件 | raw.githubusercontent.com |
| RIFE Python flownet.pkl | Flowframes 复制 | 本地复制到 resources/models/ |

### 5. 显存估算公式
`vram_estimator.py` — 关键规则：
- **串行不叠加**: 超分+插帧在主流程之后执行，不计入并发计算
- **深度系数**: 0.60~1.50 (非原 2.0)
- **超限阈值**: 95% 显存 (非原 90%)
- **并发附加**: 每多一任务 +25% 峰值 (非原 40%)
- **waifu2x**: Vulkan 几乎不耗显存，固定 1GB

## 后端接口规范

### sr_ncnn_backend.py
```python
def is_available() -> bool:        # exe + 模型 .bin 都存在
def initialize() -> None:          # 下载二进制 + 模型（失败不抛异常）
def enhance_video_ncnn(input, output, scale=4, gpu_id=0, log_cb=None, prog_cb=None)
```

### waifu2x_ncnn_backend.py
```python
def is_available() -> bool:
def enhance_video_waifu2x(input, output, scale=2, noise=-1, gpu_id=0,
                          model_arch="cunet", log_cb=None, prog_cb=None)
```

### rife_ncnn_backend.py
```python
def is_available() -> bool:        # exe + dll 存在
def interpolate_video_ncnn(input, output, multiplier=2, model_name="rife-v3.1",
                          gpu_id=0, tta=False, log_callback=None, progress_callback=None)
```

## 配置项

```python
# 超分
enableSuperResolution    # bool
srModelName              # ["realesr-animevideov3", "RealESRGAN_x4plus", ..., "waifu2x-cunet", "waifu2x-upconv_anime"]
srBackend                # ["python", "ncnn"]  — 仅 Real-ESRGAN
srTileSize               # int (0-1024)
srUseHalf                # bool

# 帧插值
enableFrameInterpolation # bool
fiMultiplier             # [2,3,4,5,6,7,8]
fiModelName              # ["rife-v3.1", "rife-v3.0", "rife-v2.4", "rife-anime"] — ncnn 模型
fiModelDir               # str (自定义路径)
fiBackend                # ["python", "ncnn"]
enhanceSrFirst           # bool (处理顺序)
```

## 常见问题

### rife-ncnn 崩溃 (STATUS_ACCESS_VIOLATION)
**原因**: Flowframes 的 exe 太旧，不支持 rife-v4.6 的 Eltwise 层
**修复**: 改用 rife-v3.1 模型（已本地下载）
**验证**: 运行 `exe -0 f0 -1 f1 -o out -m model_dir -g -1` 不报 "layer Eltwise not exists"

### realesrgan-ncnn 模型不可用
**原因**: 模型文件 (.bin/.param) 在 GitHub LFS 中，国内无法下载
**处理**: 自动回退到 Python CUDA 后端

### PermissionError 并发加载模型
**原因**: 两个并发任务同时下载/加载同一 .pth 文件
**修复**: `_RealESRGANer` 初始化加指数退避重试 (1,2,4,8,16秒)

### 帧数限制
**注意**: ncnn 后端提取帧时不应设上限（之前 sr_ncnn 限500帧，waifu2x 限1000帧，已修复）

## 性能优化（2026-06-22 更新）

### FFmpeg 管道 + 线程流水线
原逐帧串行循环 (cv2.VideoCapture → GPU → cv2.VideoWriter) 导致 GPU 利用率锯齿波动。
已重写为 FFmpeg pipe + 3 线程流水线架构，解码/推理/编码并行重叠。
详见 **[ui-audit-and-perf-optimization](ui-audit-and-perf-optimization.md)** 第三章。

### ncnn 后端帧提取提速
`_extract_frames` 从 cv2.imwrite 循环改为 `ffmpeg -q:v 1 %08d.png` 直接提取，提速 3-5 倍。

## 相关 SKILL

- **[vsr-skills-master-index](vsr-skills-master-index.md)** — 全部 SKILL 多维度评价总索引
- **[ui-audit-and-perf-optimization](ui-audit-and-perf-optimization.md)** — UI审计 + GPU管线优化方法论
- **[vsr-dev-history](vsr-dev-history.md)** — 项目全景开发历程
- **[multi-sweep-watermark-removal](multi-sweep-watermark-removal.md)** — 多循环暴力扫除算法
