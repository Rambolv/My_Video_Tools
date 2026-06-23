---
name: python-import-compat
description: '修复 QPT 打包环境下 Python 包内绝对导入失败的问题。当从外部复制代码（如 Flowframes）到项目子包中时，须将 from model.xxx 等绝对导入改为 from .model.xxx 相对导入，否则 QPT 运行时因 sys.path 不含子包路径而报 ModuleNotFoundError。'
user-invocable: false
---

# Python 导入兼容性 — QPT 打包环境

## 问题现象

```
[RIFE] 导入失败: No module named 'model.RIFE_HDv3'
```

但命令行下直接运行正常。

## 根因

**绝对导入 vs 相对导入的差异**：

| 环境 | `sys.path` | 能否找到 `model` 顶级包 |
|------|-----------|----------------------|
| CLI 命令行 | 包含当前目录 + 项目根 | ✅ 能找到 `rife/model/` |
| QPT 运行时 | 只加 `resources/backend/`，不加子包路径 | ❌ `model` 不是顶层包 |

- `from model.RIFE_HDv3 import Model` 是**绝对导入**，Python 在 `sys.path` 中搜索 `model` 作为顶层包
- `model/` 实际上是 `rife/` 的子包（即 `rife/model/`），不是顶层目录

## 修复方法

将**绝对导入改为相对导入**：

```python
# 错误
from model.RIFE_HDv3 import Model

# 正确
from .model.RIFE_HDv3 import Model
```

相对导入使用 `.` 表示「当前包内」，不依赖 `sys.path`。

## 适用范围

从外部复制代码包时，**包内所有跨文件导入都必须检查**：

| 文件 | 导入语句 | 应改为 |
|------|----------|--------|
| `rife/RIFE_HDv3.py` | `from model.RIFE_HDv3 import Model` | `from .model.RIFE_HDv3 import Model` |
| `rife/model/__init__.py` | `from warplayer import warp` | `from .warplayer import warp` |
| `rife/model/IFNet_HDv3.py` | 类似 | 加 `.` 前缀 |

## 诊断方法

在失败处添加 `sys.path` 打印和诊断文件输出：

```python
import sys
print("[DIAG] sys.path:", sys.path)
# 写入诊断文件（防止子进程 stdout 丢失）
with open('rife_diag.log', 'a') as f:
    f.write(f"PID={os.getpid()} sys.path={sys.path}\n")
```

对比 CLI 和 QPT 下的 `sys.path` 差异即可定位。

## 当前状态 (2026-06-23)

- **CLI 命令行**: ✅ RIFE 导入正常，SR+FI 管道完整通过（75帧 4x超分+2x插帧 183s）
- **QPT 子进程**: ✅ 已修复 — 改用 `importlib.util.spec_from_file_location` 直接加载模块，绕过 `sys.path` 依赖
- **修复措施**: 
  - `from model.RIFE_HDv3` → `from .model.RIFE_HDv3`（相对导入）
  - 改用 `importlib` 加载：`spec_from_file_location` + `exec_module`，不依赖 `sys.path`
  - 保留诊断文件 `rife_diag.log` 以应对未来异常
- **验证结果**: `multiprocessing.spawn` 子进程中 `_ensure_rife()=True`, `FI available=True`

## 类似项目参考

- Flowframes → VSR 项目：RIFE_HDv3.py 的导入链
- Real-ESRGAN → Python 包内导入（已用 pip 安装，不受影响）
- 任何从 GitHub 复制到 `resources/backend/` 下的自定义算法包

## 预防

- 从外部项目复制代码后，用 `grep '^from \w'` 检查所有顶级绝对导入
- 包内引用一律使用相对导入（`from .xxx`）
- 打包前在纯净环境测试导入
