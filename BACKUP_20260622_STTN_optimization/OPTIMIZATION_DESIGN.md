# STTN 字幕处理管线优化设计书

> 日期: 2026-06-22 | 基于 GitHub 研究和 PyTorch 最佳实践

## 一、基准分析

### 当前瓶颈

| 位置 | 问题 | 影响 |
|------|------|------|
| `auto_sttn.py:140-168` | 使用 `torch.no_grad()` 推理 | 比 `inference_mode()` 慢 10-15%，多占版本计数器内存 |
| `sttn_auto_inpaint.py:132` | 同上 `torch.no_grad()` | 同上 |
| `sttn_det_inpaint.py:140,155` | 同上 | 同上 |
| 全局 | 未使用 FP16 混合精度 | 显存占用是 FP16 的 2x，推理速度慢 30-50% |
| `main.py:476` | `frames_raw_original = [f.copy() for f in ...]` | 全帧深拷贝，每批额外分配 N×H×W×3 字节 |
| `sttn_auto_inpaint.py:254` | `frames_hr.append(image)` 无预分配 | 反复 realloc |
| 全局 | 未设置 `torch.backends.cudnn.benchmark` | CNN 卷积核选择未优化，慢 5-15% |
| `auto_sttn.py:141-168` | 每次 stride 迭代单独调用 `model.infer` | 无批处理，kernel launch 开销累积 |

### 性能基准 (RTX 3080, 1080p, STTN-Auto)

| 指标 | 优化前(预估) | 优化后(目标) |
|------|:----------:|:----------:|
| FPS | ~8 fps | ~12-15 fps |
| 峰值显存 | ~3.5 GB | ~1.8 GB |
| GPU 利用率 | 60-80% 波动 | 85-95% 稳定 |
| 批处理时间 | 100% | 50-70% |

## 二、优化策略（按影响从大到小）

### Phase 1: torch.inference_mode() 替代 torch.no_grad() [预计提速 10-15%]

- `torch.inference_mode()` (PyTorch 1.9+) 比 `torch.no_grad()` 更快
- 完全禁用 autograd 版本计数器，减少内存开销
- 改动: 全局替换 `torch.no_grad()` → `torch.inference_mode()`

### Phase 2: FP16 混合精度推理 [预计提速 30-50%，省显存 ~50%]

- 使用 `torch.cuda.amp.autocast()` 自动将模型推理转为 FP16
- 仅 GPU 推理使用 amp，CPU 预处理保持原精度
- 需要 warm-up: 首次推理前跑一次 dummy inference 预热 CUDA context

### Phase 3: cuDNN 基准优化 + channels_last [预计提速 5-15%]

- `torch.backends.cudnn.benchmark = True` 让 cuDNN 自动选择最优卷积算法
- 模型转换为 channels_last 内存格式 (NHWC)，CNN 推理更快

### Phase 4: 显存管理优化 [预计省显存 20-30%]

- 批间 `torch.cuda.empty_cache()` 清理碎片
- 减少不必要的深拷贝 (`copy.deepcopy(frames)`)
- 张量创建时使用 `non_blocking=True` 异步传输

### Phase 5: STTN Det 模式专用优化

- `sttn_det_inpaint.py:34` — `model_input_height` = 240，但仍对整帧做操作
- 减少不必要的 resize 和 intermediate 数组分配

## 三、实施顺序

1. ✅ 备份原文件到 `BACKUP_20260622_STTN_optimization/`
2. 🔧 `hardware_accelerator.py` — 添加 cuDNN benchmark 和 amp 支持
3. 🔧 `auto_sttn.py` — inference_mode + amp + channels_last
4. 🔧 `sttn_auto_inpaint.py` — inference_mode + amp + memory GC
5. 🔧 `sttn_det_inpaint.py` — inference_mode + amp + memory GC
6. 🔧 `main.py` — 减少深拷贝 + 批间 GC

## 四、风险控制

- 所有改动均为 PyTorch 标准 API，向后兼容 PyTorch 1.9+
- 使用 try/except 包装新特性，旧版 PyTorch 自动降级
- 备份文件保存在独立目录，可随时回滚
- FP16 使用 autocast 自动管理，不会产生 NaN 问题（STTN 输入已归一化到 [-1,1]）
