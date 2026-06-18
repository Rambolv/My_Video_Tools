---
name: multi-sweep-watermark-removal
description: "多循环暴力扫除：专杀AI急速变化/扭曲/变形Logo水印"
applyTo: "**/*.py"
---

# 多循环暴力扫除 (Multi-Sweep Watermark Removal)

## 问题描述
AI生成视频中的水印具有以下特征：
- **白色/淡白色半透明**：水印通过α混合与原始画面融合
- **每帧变形扭曲**：文字/Logo每帧改变形状和位置
- **边缘混合色**：反走样边缘的像素是水印色与背景色的混合

## 核心算法

### 1. 密度峰值背景估计 (`density_background_estimate`)
文件：`resources/backend/tools/inpaint_tools.py`

```
对遮罩区每个像素在N帧中的观测值:
  在RGB三维空间中统计每个帧的邻居数(密度半径内)
  找邻居最多的帧 = 密度峰值 = 背景簇中心
  取该簇所有帧的平均 = 干净背景
```

比中值体(medoid)更好的原因：50%-50%分裂时medoid落在两簇中间，
密度峰值正确选中背景簇。

### 2. 变形自适应遮罩 (`merge_deformation_mask`)
文件：`resources/backend/tools/inpaint_tools.py`

```
收集所有帧的OCR检测框
计算位置/尺寸的标准差作为变形幅度
遮罩 = 整体范围 + base_expand + deform_factor × 变形幅度
```

### 3. 变形自动检测 (`detect_text_deformation`)
文件：`resources/backend/tools/inpaint_tools.py`

严重变形(位置std>15px或尺寸std>10px)时自动使用整个用户选区。

### 4. 自适应原始保护混合 v2 (`adaptive_orig_blend`)
文件：`resources/backend/tools/inpaint_tools.py`

双通道检测：灰度亮度异常(白色文字) + CIELAB色差(彩色图像水印)。

### 5. 残留亮斑清理 (`remove_bright_residuals`)
文件：`resources/backend/tools/inpaint_tools.py`

检测遮罩区内亮度异常像素(>周围均值+1.8σ)，从附近正常像素采样替代。

### 6. 残留边缘检测 (`detect_residual_text_mask`, `exemplar_fill_residuals`)
文件：`resources/backend/tools/inpaint_tools.py`

Canny边缘检测残留文字笔画，从邻近干净帧复制背景像素。

## 扫除模式完整管道

```
原始帧保存(frames_raw_original)
→ 变形自适应遮罩合并/扩展
→ 强时序中值滤波(15帧)
→ 密度峰值RGB背景聚类(31帧, blend_orig=0.15)
→ 邻近干净帧填充
→ 模型×3次推理(50%+30%+20%加权)
→ 亮色残留压制
→ 残留边缘检测+二次像素填充
→ 自适应原始保护混合(亮度+色差双通道)
→ 锐化羽化+颗粒恢复
```

## 多轮扫除循环

文件：`resources/backend/main.py`

每轮将上一轮清理后的视频作为输入，重新执行完整扫除管道。
- 唯一变化量：`self.video_path` 指向上一轮输出
- 所有配置参数完全一致
- 输出文件名包含轮数标记（如 `_3clean_no_sub.mp4`）

## 配置项

文件：`resources/backend/config.py`

- `sweepModeEnabled` (Bool): 开启/关闭扫除模式
- `sweepIterations` (1-10): 扫除轮数

## UI

文件：`resources/ui/home_interface.py`

- "多循环暴力扫除" 开关按钮
- "扫除次数" SpinBox (1-10)
- 按钮开启后显示当前轮数

## 相关文件

- `resources/backend/main.py` - 主处理循环，多轮扫除逻辑
- `resources/backend/tools/inpaint_tools.py` - 全部核心算法函数
- `resources/backend/config.py` - 配置项定义
- `resources/ui/home_interface.py` - UI控件
