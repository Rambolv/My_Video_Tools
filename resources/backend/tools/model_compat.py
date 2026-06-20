"""
@desc: 模型/后端兼容性校验 — 自动检测并修正不兼容的模型+后端组合
所有已知的不兼容组合在此集中管理，供各模块和UI调用
"""
from __future__ import annotations
import os
from typing import Dict, List, Optional, Tuple

# ── 后端常量 ──
BACKEND_PYTHON = "python"      # Python CUDA
BACKEND_NCNN = "ncnn"          # ncnn Vulkan
BACKEND_WAIFU2X = "waifu2x"    # waifu2x-ncnn-vulkan（独立）

# ── RIFE 模型兼容性定义 ──
# key=模型名, value=(display_name, [兼容后端列表])
RIFE_MODEL_COMPAT: Dict[str, Tuple[str, List[str]]] = {
    "rife-v3.1":  ("RIFE v3.1",  [BACKEND_PYTHON, BACKEND_NCNN]),
    "rife-v3.0":  ("RIFE v3.0",  [BACKEND_PYTHON]),  # ❌ 不支持 ncnn! 缺少 flownet.param
    "rife-v2.4":  ("RIFE v2.4",  [BACKEND_PYTHON, BACKEND_NCNN]),
    "rife-anime": ("RIFE Anime", [BACKEND_PYTHON, BACKEND_NCNN]),
}

# ── SR 模型兼容性定义 ──
SR_MODEL_COMPAT: Dict[str, Tuple[str, List[str], str]] = {
    # key=(模型名, display_name, [兼容后端], 自动后端)
    "realesr-animevideov3": ("Real-ESRGAN AnimeVideo v3",  [BACKEND_PYTHON, BACKEND_NCNN], BACKEND_NCNN),
    "RealESRGAN_x4plus":    ("Real-ESRGAN x4plus",         [BACKEND_PYTHON, BACKEND_NCNN], BACKEND_NCNN),
    "RealESRGAN_x2plus":    ("Real-ESRGAN x2plus",         [BACKEND_PYTHON, BACKEND_NCNN], BACKEND_NCNN),
    "realesr-general-x4v3": ("Real-ESRGAN General v3",     [BACKEND_PYTHON, BACKEND_NCNN], BACKEND_NCNN),
    "waifu2x-cunet":        ("waifu2x cunet",              [BACKEND_NCNN],                  BACKEND_NCNN),
    "waifu2x-upconv_anime": ("waifu2x upconv_anime",       [BACKEND_NCNN],                  BACKEND_NCNN),
}

# ── 模型文件完整性校验 ──
# 某些 ncnn 模型需要特定的 .param + .bin 文件对
# 如果文件缺失，强行用 ncnn 后端会崩溃

_NCNN_MODEL_REQUIRED_FILES = {
    "flownet.param":  "flownet.bin",
    "contextnet.param": "contextnet.bin",
    "fusionnet.param": "fusionnet.bin",
}


def get_rife_ncnn_model_dir(model_name: str) -> Optional[str]:
    """获取 RIFE ncnn 模型目录路径"""
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "tools", "rife_ncnn", "models", model_name)
    if os.path.isdir(base):
        return base
    return None


def check_rife_ncnn_model_complete(model_name: str) -> Tuple[bool, str]:
    """
    检查 RIFE ncnn 模型文件是否完整
    返回 (ok, message)
    """
    model_dir = get_rife_ncnn_model_dir(model_name)
    if model_dir is None:
        return False, f"模型目录不存在: {model_name}"

    missing = []
    for param_file, bin_file in _NCNN_MODEL_REQUIRED_FILES.items():
        has_param = os.path.isfile(os.path.join(model_dir, param_file))
        has_bin = os.path.isfile(os.path.join(model_dir, bin_file))
        if not has_param:
            missing.append(param_file)
        if not has_bin:
            missing.append(bin_file)

    if missing:
        return False, f"模型 {model_name} 缺少 ncnn 文件: {', '.join(missing)}"
    return True, "OK"


def validate_rife_config(model_name: str, backend: str) -> Tuple[bool, str, str]:
    """
    验证 RIFE 模型+后端组合是否有效，返回 (ok, message, corrected_backend)
    如果无效，自动修正 backend 到第一个可用的后端
    """
    compat_info = RIFE_MODEL_COMPAT.get(model_name)
    if compat_info is None:
        return False, f"未知 RIFE 模型: {model_name}", BACKEND_PYTHON

    display_name, compatible_backends = compat_info

    if backend not in compatible_backends:
        # 自动修正到兼容后端
        corrected = compatible_backends[0]
        reason = _build_incompat_reason(model_name, display_name, backend, corrected)
        return False, reason, corrected

    # 如果是 ncnn 后端，额外检查模型文件完整性
    if backend == BACKEND_NCNN:
        ok, msg = check_rife_ncnn_model_complete(model_name)
        if not ok:
            # 文件不完整，回退到 Python
            corrected = BACKEND_PYTHON
            return False, f"{msg}，已自动切换到 Python CUDA 后端", corrected

    return True, "", backend


def validate_sr_config(model_name: str, backend: str) -> Tuple[bool, str, str]:
    """
    验证 SR 模型+后端组合是否有效，返回 (ok, message, corrected_backend)
    """
    # waifu2x 模型固定走 ncnn，不检查
    if model_name.startswith("waifu2x-"):
        return True, "", BACKEND_NCNN

    compat_info = SR_MODEL_COMPAT.get(model_name)
    if compat_info is None:
        return False, f"未知 SR 模型: {model_name}", BACKEND_PYTHON

    display_name, compatible_backends, _ = compat_info

    if backend not in compatible_backends:
        corrected = compatible_backends[0]
        reason = _build_incompat_reason(model_name, display_name, backend, corrected)
        return False, reason, corrected

    return True, "", backend


def _build_incompat_reason(model_key: str, display_name: str,
                           selected_backend: str, corrected_backend: str) -> str:
    """生成不兼容提示信息"""
    backend_map = {BACKEND_PYTHON: "Python CUDA", BACKEND_NCNN: "ncnn Vulkan"}
    sel = backend_map.get(selected_backend, selected_backend)
    cor = backend_map.get(corrected_backend, corrected_backend)
    return (
        f"⚠️ {display_name} 不支持 {sel} 后端，"
        f"已自动切换到 {cor}"
    )


# ── 便捷查询 ──

def get_rife_compatible_backends(model_name: str) -> List[str]:
    """获取 RIFE 模型兼容的后端列表"""
    info = RIFE_MODEL_COMPAT.get(model_name)
    return info[1] if info else [BACKEND_PYTHON]


def get_sr_compatible_backends(model_name: str) -> List[str]:
    """获取 SR 模型兼容的后端列表"""
    if model_name.startswith("waifu2x-"):
        return [BACKEND_NCNN]
    info = SR_MODEL_COMPAT.get(model_name)
    return info[1] if info else [BACKEND_PYTHON]
