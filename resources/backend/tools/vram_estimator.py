"""
@desc: 模型显存估算器 — 根据模型类型、分辨率、并发数估算显存占用，自动标红超限选项
支持从 vram_records.json（真实工作采集）加载实测值覆盖硬编码基准
"""
from __future__ import annotations
from typing import Dict, Tuple, Optional
from backend.tools.constant import InpaintMode, SubtitleDetectMode, EnhancementMode
from backend.tools.hardware_accelerator import HardwareAccelerator

# ============ 各模型在 1080p 下的基准显存（GB），内置默认值 ============
_MODEL_VRAM_BASELINE_1080P: Dict[str, float] = {
    # --- 修复模型 ---
    InpaintMode.OPENCV.value:     0.3,
    InpaintMode.STTN_AUTO.value:  2.8,
    InpaintMode.STTN_DET.value:   2.5,
    InpaintMode.LAMA.value:       2.2,
    InpaintMode.E2FGVI.value:     48.0,   # 需要 48GB+ 显存
    InpaintMode.PROPAINTER.value: 13.0,
    # --- 检测模型 ---
    SubtitleDetectMode.PP_OCRv4_SERVER.value:  0.8,
    SubtitleDetectMode.PP_OCRv4_MOBILE.value:  0.4,
    SubtitleDetectMode.PP_OCRv5_SERVER.value:  1.0,
    SubtitleDetectMode.PP_OCRv5_MOBILE.value:  0.5,
    SubtitleDetectMode.SAM2_TINY.value:   3.5,
    SubtitleDetectMode.SAM2_SMALL.value:  5.0,
    SubtitleDetectMode.SAM2_BASE.value:   10.0,
    SubtitleDetectMode.SAM2_LARGE.value:  18.0,
    # --- 超分辨率 (Real-ESRGAN) ---
    EnhancementMode.SR_ANIME.value:    2.0,
    EnhancementMode.SR_X4PLUS.value:   3.5,
    EnhancementMode.SR_X2PLUS.value:   2.5,
    EnhancementMode.SR_GENERAL.value:  2.0,
    # --- 帧插值 (RIFE) ---
    EnhancementMode.FI_RIFE.value:     1.8,
}

# 缓存：由 vram_records.json 加载的真实工作峰值
_REAL_VRAM_CACHE: Optional[Dict[str, Dict]] = None


def _load_real_vram_data() -> Optional[Dict[str, Dict]]:
    """从 vram_records.json 加载真实工作采集的显存数据"""
    global _REAL_VRAM_CACHE
    if _REAL_VRAM_CACHE is not None:
        return _REAL_VRAM_CACHE
    try:
        from backend.tools.vram_monitor import get_all_model_peak_vrams
        data = get_all_model_peak_vrams()
        if data:
            _REAL_VRAM_CACHE = data
            return _REAL_VRAM_CACHE
    except Exception:
        pass
    return None


def get_model_vram_baseline(model_key: str) -> float:
    """
    获取模型的显存基准值（优先使用真实工作采集值，无则用内置默认值）
    """
    real = _load_real_vram_data()
    if real and model_key in real:
        peak = real[model_key].get("peak_vram_gb", 0)
        if peak > 0:
            return peak
    return _MODEL_VRAM_BASELINE_1080P.get(model_key, 3.0)


def has_real_data() -> bool:
    """是否有真实工作采集的显存数据"""
    try:
        from backend.tools.vram_monitor import has_real_data
        return has_real_data()
    except Exception:
        return False


def get_model_danger_flags() -> Dict[str, bool]:
    """
    返回各模型是否有过 OOM 记录。
    {model_key: True/False}
    """
    real = _load_real_vram_data()
    if not real:
        return {}
    flags = {}
    for key, rec in real.items():
        flags[key] = rec.get("oom", False)
    return flags

# 处理深度对显存的附加系数（连续值 0-100）
_DEPTH_VRAM_FACTOR_MIN = 0.60   # depth=0 时
_DEPTH_VRAM_FACTOR_MAX = 1.50   # depth=100 时（比原2.0更温和）
# 水印检测在检测模型基础上的额外显存开销（GB，连续值 0-100）
_WATERMARK_OVERHEAD_MIN = 0.0    # depth=0
_WATERMARK_OVERHEAD_MAX = 2.5    # depth=100

# 分辨率缩放系数（以 1080p = 1920×1080 = 2,073,600 像素为基准）
def _resolution_factor(w: int, h: int) -> float:
    """分辨率对显存的缩放比（近似线性于像素数）"""
    ref = 1920 * 1080
    return (w * h) / ref if ref > 0 else 1.0


def estimate_model_vram(
    inpaint_mode: str,
    detect_mode: str,
    video_width: int = 1920,
    video_height: int = 1080,
    concurrent_tasks: int = 1,
    processing_depth: int = 50,
    sr_mode: str = "",
    fi_enabled: bool = False,
) -> Dict[str, float]:
    """
    估算指定配置的总显存占用（含超分辨率 + 帧插值）。
    返回:
        {
            "inpaint_gb": 修复模型显存,
            "detect_gb": 检测模型显存,
            "enhance_gb": 增强模型显存（超分+插帧）,
            "total_gb": 总计,
            "gpu_vram_gb": GPU 物理显存,
            "over_limit": 是否超出,
        }
    """
    accel = HardwareAccelerator.instance()
    gpu_vram = accel.get_gpu_vram_gb()

    res_factor = _resolution_factor(video_width, video_height)
    d_norm = processing_depth / 100.0 if isinstance(processing_depth, (int, float)) else 0.5
    depth_factor = _DEPTH_VRAM_FACTOR_MIN + (_DEPTH_VRAM_FACTOR_MAX - _DEPTH_VRAM_FACTOR_MIN) * d_norm
    watermark_overhead = _WATERMARK_OVERHEAD_MIN + (_WATERMARK_OVERHEAD_MAX - _WATERMARK_OVERHEAD_MIN) * d_norm

    base_inpaint = get_model_vram_baseline(inpaint_mode)
    base_detect = get_model_vram_baseline(detect_mode)

    model_inpaint = base_inpaint * res_factor * depth_factor
    model_detect = base_detect * res_factor + watermark_overhead * res_factor

    # ---- 增强模型显存 ----
    model_enhance = 0.0
    if sr_mode:
        # 检查是 Real-ESRGAN 还是 waifu2x
        if sr_mode.startswith("waifu2x-"):
            model_enhance += 1.0 * res_factor  # waifu2x-Vulkan，几乎不耗显存
        elif sr_mode in _MODEL_VRAM_BASELINE_1080P:
            sr_base = get_model_vram_baseline(sr_mode)
            model_enhance += sr_base * res_factor
    if fi_enabled:
        fi_base = get_model_vram_baseline(EnhancementMode.FI_RIFE.value)
        model_enhance += fi_base * res_factor

    # ---- 综合估算 ----
    # 注意: 主流程(修复+检测)和增强(超分+插帧)是串行的，不叠加
    # 主流程峰值取修复和检测中较大者 + 并发附加
    main_peak = max(model_inpaint, model_detect)
    if concurrent_tasks <= 1:
        total = main_peak * 1.10
    else:
        # 多任务时，峰值任务全占，从任务共享部分显存
        total = main_peak + main_peak * (concurrent_tasks - 1) * 0.25
    # 增强模型串行执行，只加一次（不乘并发数）
    total += model_enhance

    return {
        "inpaint_gb": round(model_inpaint, 1),
        "detect_gb": round(model_detect, 1),
        "enhance_gb": round(model_enhance, 1),
        "total_gb": round(total, 1),
        "gpu_vram_gb": round(gpu_vram, 1),
        "over_limit": total > gpu_vram * 0.95,
        "usage_pct": round(total / gpu_vram * 100, 0) if gpu_vram > 0 else 999,
    }


def get_all_model_vram_list() -> Dict[str, Dict[str, float]]:
    """
    返回所有模型在标准深度、1080p、单任务时的显存估算表（优先使用实测值）。
    key 为模型名，value 包含 vram_gb、category（修复/检测/增强）
    """
    result = {}
    inpaint_values = {m.value for m in InpaintMode}
    detect_values = {m.value for m in SubtitleDetectMode}
    for mode in _MODEL_VRAM_BASELINE_1080P:
        vram_gb = get_model_vram_baseline(mode)
        if mode in inpaint_values:
            cat = "修复"
        elif mode in detect_values:
            cat = "检测"
        else:
            cat = "增强"
        result[mode] = {"vram_gb": vram_gb, "category": cat}
    return result


def get_vram_status_color(usage_pct: float) -> str:
    """根据显存占用百分比返回状态颜色，供 GUI 使用"""
    if usage_pct >= 95:
        return "#e81123"   # 红色 - 极危险
    if usage_pct >= 85:
        return "#ff8c00"   # 橙色 - 警告
    if usage_pct >= 70:
        return "#ffd700"   # 黄色 - 注意
    return "#16ab39"        # 绿色 - 安全
