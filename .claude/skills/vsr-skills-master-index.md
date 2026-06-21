---
name: vsr-skills-master-index
description: "VSR项目全部AI SKILL多维度分类评价总索引——按领域/阶段/可复用性/成熟度/风险等级评分"
---

# VSR 魔改版 — AI SKILL 多维分类评价体系

> 本文件是项目所有 SKILL 的总索引，从 6 个维度对每条 SKILL 进行评分和分类。
> 评分标准：⭐=基础 ⭐⭐=有用 ⭐⭐⭐=重要 ⭐⭐⭐⭐=关键 ⭐⭐⭐⭐⭐=基石

## 一、SKILL 总览

| # | SKILL 名称 | 文件 | 主题领域 | 会话数 |
|---|-----------|------|---------|--------|
| 1 | vsr-dev-history | `vsr-dev-history.md` | 项目全景/架构 | 全量 |
| 2 | multi-sweep-watermark-removal | `multi-sweep-watermark-removal.md` | 算法设计 | 1 |
| 3 | vsr-video-enhancement | `vsr-video-enhancement.md` | 功能集成/架构 | 1 |
| 4 | ui-audit-and-perf-optimization | `ui-audit-and-perf-optimization.md` | 质量审计/性能优化 | 1 |

---

## 二、6 维度评分矩阵

### 维度说明

| 维度 | 含义 | 评分标准 |
|------|------|---------|
| **D1-领域覆盖** | 涉及多少功能模块 | 1=单模块, 3=跨模块, 5=全项目 |
| **D2-可复用性** | 方法论能否迁移到其他项目 | 1=仅本项目, 3=同类项目, 5=通用模式 |
| **D3-成熟度** | 经过多少轮迭代验证 | 1=初稿, 3=多次验证, 5=生产验证 |
| **D4-风险等级** | 对项目稳定性的影响 | 1=无风险, 3=中等风险, 5=高风险 |
| **D5-创新程度** | 相比原版的独创性 | 1=常规修改, 3=显著改进, 5=原创方案 |
| **D6-AI协作价值** | 对 AI 辅助开发的指导意义 | 1=参考, 3=重要参考, 5=必读 |

### 评分矩阵

| SKILL | D1 领域覆盖 | D2 可复用性 | D3 成熟度 | D4 风险等级 | D5 创新程度 | D6 AI协作 | **综合** |
|-------|:---------:|:---------:|:--------:|:---------:|:---------:|:--------:|:------:|
| vsr-dev-history | ⭐⭐⭐⭐⭐ 5 | ⭐⭐⭐ 3 | ⭐⭐⭐⭐ 4 | ⭐⭐ 2 | ⭐⭐⭐⭐ 4 | ⭐⭐⭐⭐ 4 | **3.7** |
| multi-sweep | ⭐⭐⭐ 3 | ⭐⭐⭐⭐ 4 | ⭐⭐⭐⭐ 4 | ⭐⭐⭐ 3 | ⭐⭐⭐⭐⭐ 5 | ⭐⭐⭐⭐ 4 | **3.8** |
| vsr-video-enhancement | ⭐⭐⭐⭐ 4 | ⭐⭐⭐⭐ 4 | ⭐⭐⭐ 3 | ⭐⭐⭐ 3 | ⭐⭐⭐⭐ 4 | ⭐⭐⭐⭐ 4 | **3.7** |
| ui-audit-perf | ⭐⭐⭐ 3 | ⭐⭐⭐⭐⭐ 5 | ⭐⭐⭐ 3 | ⭐⭐⭐⭐ 4 | ⭐⭐⭐ 3 | ⭐⭐⭐⭐⭐ 5 | **3.8** |

---

## 三、按开发阶段分类

### 3.1 项目启动阶段 → 应优先加载
- **[vsr-dev-history](vsr-dev-history.md)** — 项目全景地图，新人/新会话必读
  - 覆盖：功能清单 → 文件索引 → 架构概览 → 发布策略

### 3.2 功能开发阶段 → 按需加载
- **[multi-sweep-watermark-removal](multi-sweep-watermark-removal.md)** — 复杂算法设计文档
  - 适用：需要理解/修改扫除算法管道的任何变更
- **[vsr-video-enhancement](vsr-video-enhancement.md)** — 视频增强模块架构文档
  - 适用：超分/帧插值功能的添加/修改/后端扩展

### 3.3 质量保障阶段 → 定期执行
- **[ui-audit-and-perf-optimization](ui-audit-and-perf-optimization.md)** — 审计与优化方法论
  - 适用：代码审查、性能诊断、举一反三式 BUG 排查

---

## 四、按可复用性分层

### Layer 1: 项目专用（VSR 特有）
```
vsr-dev-history: 项目功能列表、文件索引、发布流程
```
### Layer 2: 领域通用（视频处理 AI 项目）
```
multi-sweep-watermark-removal: 多轮渐进式修复算法模式
vsr-video-enhancement:  多后端 AI 推理 + 视频 I/O 架构模式
```
### Layer 3: 完全通用（任何软件项目）
```
ui-audit-and-perf-optimization:
  - UI控件死链审计方法论 → 任何 GUI 项目
  - GPU管线性能诊断清单 → 任何 GPU 推理项目
  - FFmpeg管道+线程流水线模式 → 任何视频处理项目
```

---

## 五、按角色推荐

| 角色 | 必读 SKILL | 选读 SKILL |
|------|-----------|-----------|
| **项目新人** | vsr-dev-history | — |
| **功能开发者** | vsr-dev-history → 对应模块 SKILL | — |
| **代码审查者** | ui-audit-and-perf-optimization | vsr-dev-history |
| **架构师** | vsr-dev-history + vsr-video-enhancement | multi-sweep |
| **运维/发布** | vsr-dev-history (发布策略章节) | — |

---

## 六、SKILL 间交叉引用图

```
┌──────────────────────────────────────────────────────────────┐
│                   vsr-dev-history (项目全景)                   │
│   ├── 索引 multi-sweep-watermark-removal (扫除算法)            │
│   ├── 索引 vsr-video-enhancement (视频增强)                    │
│   └── 索引 ui-audit-and-perf-optimization (审计优化)           │
└──────────────────────────────────────────────────────────────┘
        │                    │                    │
        ▼                    ▼                    ▼
┌──────────────┐  ┌──────────────────┐  ┌──────────────────────┐
│ multi-sweep  │  │ vsr-video-       │  │ ui-audit-perf        │
│ (算法设计)    │  │ enhancement      │  │ (审计+性能)           │
│              │  │ (功能架构)        │  │                      │
│ 关联:        │  │                  │  │ 关联:                 │
│ inpaint_tools│  │ 关联:            │  │ home_interface.py     │
│ main.py      │  │ video_enhancer   │  │ watermark_template   │
│ config.py    │  │ sr/rife/waifu2x  │  │ video_enhancer.py    │
│ home_intf    │  │ 后端 ×3          │  │ sr/rife/waifu2x 后端  │
│              │  │                  │  │ gui.py               │
└──────────────┘  └──────────────────┘  └──────────────────────┘
```

---

## 七、SKILL 演进时间线

```
2026-06-18  vsr-dev-history           项目全量开发历程汇总
2026-06-19  multi-sweep-watermark     多循环暴力扫除算法文档化
2026-06-20  vsr-video-enhancement     视频增强模块（SR+FI）架构文档化
2026-06-22  ui-audit-and-perf          UI死链审计+GPU管线性能优化方法论
            vsr-skills-master-index    本文件：多维度评价体系建立
```

---

## 八、未来 SKILL 规划

| 优先级 | 候选 SKILL | 触发条件 |
|--------|-----------|---------|
| 高 | `config-system-design` | 配置项 > 100 个时的管理策略 |
| 高 | `multi-gpu-scheduling` | 多 GPU 并发任务调度 |
| 中 | `subtitle-extract-pipeline` | 字幕提取功能重大重构 |
| 中 | `cross-platform-porting` | Linux/Mac 移植 |
| 低 | `model-download-resilience` | 模型下载容错机制完善 |
| 低 | `i18n-workflow` | 多语言翻译工作流优化 |
