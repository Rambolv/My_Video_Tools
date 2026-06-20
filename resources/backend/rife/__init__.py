"""
RIFE 帧插值引擎 — 自包含推理模块
"""
import os, sys
_pkg = os.path.dirname(os.path.abspath(__file__))
_model = os.path.join(_pkg, 'model')
for p in [_pkg, _model, os.path.dirname(_pkg)]:
    if p not in sys.path:
        sys.path.insert(0, p)
