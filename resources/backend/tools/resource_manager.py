"""
@desc: 资源管理器 — 统一调控各模型/进程的CPU/GPU/显存资源分配
支持三个等级：性能优先、平衡、最节约资源
核心功能：内部模型参数调优（批大小、线程数、精度）、
         GPU显存管理（GC频率）、未使用功能挂起
不涉及用户可见的并发任务数控制
"""
from __future__ import annotations
import gc
import logging
import multiprocessing
import os
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class ResourceProfile(Enum):
    """资源调配等级"""
    PERFORMANCE = "performance"    # 性能优先：大batch、高线程、FP16、不主动GC
    BALANCED = "balanced"          # 平衡：中等参数（默认）
    POWER_SAVING = "power_saving"  # 节能：小batch、低线程、积极GC


# ── 各等级内部模型/进程运行参数 ──
# 这些参数影响的是「每个模型实例内部」的行为，而非用户并发任务数
_PROFILE_CONFIGS = {
    ResourceProfile.PERFORMANCE: {
        "label": "性能优先",
        "description": "模型使用大batch size、高CPU线程数、FP16推理、缓存保留、不主动GC",
        # ── CPU/OpenCV/NCNN 内部线程 ──
        "cpu_thread_ratio": 1.0,            # 相对物理核心数的比例
        "ncnn_load_threads": 4,             # rife-ncnn load线程
        "ncnn_proc_threads": 8,             # rife-ncnn proc线程
        "ncnn_save_threads": 8,             # rife-ncnn save线程
        # ── 模型推理参数 ──
        "model_batch_scale": 1.0,           # batch size缩放因子（相对默认值）
        "use_fp16": True,                   # 是否使用半精度推理（节省显存）
        "mask_dilation_scale": 1.0,         # mask膨胀缩放
        "reference_frame_scale": 1.0,       # 参考帧数量缩放（STTN等）
        # ── 显存管理 ──
        "gc_interval_seconds": 300,         # 主动GC间隔（秒），300秒=5分钟一次
        "cache_models": True,               # 模型加载后缓存不释放
        "gpu_monitor_interval_ms": 1000,    # GPU监控刷新间隔
        # ── 功能挂起 ──
        "suspend_idle_features": False,     # 不挂起任何功能
    },
    ResourceProfile.BALANCED: {
        "label": "平衡",
        "description": "模型使用适中batch size、正常CPU线程、FP16推理、定期GC",
        "cpu_thread_ratio": 0.5,
        "ncnn_load_threads": 2,
        "ncnn_proc_threads": 4,
        "ncnn_save_threads": 4,
        "model_batch_scale": 0.7,
        "use_fp16": True,
        "mask_dilation_scale": 0.8,
        "reference_frame_scale": 0.8,
        "gc_interval_seconds": 120,
        "cache_models": False,
        "gpu_monitor_interval_ms": 3000,
        "suspend_idle_features": True,
    },
    ResourceProfile.POWER_SAVING: {
        "label": "最节约资源",
        "description": "模型使用小batch size、低CPU线程、必要时FP32、积极GC、挂起后台监控",
        "cpu_thread_ratio": 0.25,
        "ncnn_load_threads": 1,
        "ncnn_proc_threads": 2,
        "ncnn_save_threads": 2,
        "model_batch_scale": 0.4,
        "use_fp16": True,                   # 仍用FP16以降显存
        "mask_dilation_scale": 0.6,
        "reference_frame_scale": 0.6,
        "gc_interval_seconds": 30,          # 每30秒GC一次
        "cache_models": False,
        "gpu_monitor_interval_ms": 10000,
        "suspend_idle_features": True,
    },
}


class ResourceManager:
    """
    全局资源管理器（单例）
    负责内部模型/进程的CPU/GPU资源调优，不控制用户可见的并发任务数
    通过 enabled 属性控制是否启用，关闭后所有资源使用默认最大值
    """
    _instance: Optional[ResourceManager] = None

    def __init__(self):
        self._profile: ResourceProfile = ResourceProfile.BALANCED
        self._enabled: bool = False  # 默认关闭
        self._physical_cpus = max(1, multiprocessing.cpu_count())
        self._listeners: list[callable] = []
        self._gpu_monitor_ref = None

    @classmethod
    def instance(cls) -> ResourceManager:
        if cls._instance is None:
            cls._instance = ResourceManager()
        return cls._instance

    # ──────────────────────────────────────────
    # 总开关
    # ──────────────────────────────────────────

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        if value == self._enabled:
            return
        self._enabled = value
        if value:
            # 开启：应用当前等级配置
            self._apply_profile()
        else:
            # 关闭：恢复默认（不限制）资源设置
            self._reset_to_default()
        for cb in self._listeners:
            try:
                cb(self._profile, self._profile)
            except Exception:
                logger.exception("ResourceManager listener error")

    # ──────────────────────────────────────────
    # 等级读写
    # ──────────────────────────────────────────

    @property
    def profile(self) -> ResourceProfile:
        return self._profile

    @profile.setter
    def profile(self, value: ResourceProfile):
        if value == self._profile:
            return
        old = self._profile
        self._profile = value
        if self._enabled:
            self._apply_profile()
        for cb in self._listeners:
            try:
                cb(self._profile, old)
            except Exception:
                logger.exception("ResourceManager listener error")

    def set_profile_by_key(self, key: str):
        for p in ResourceProfile:
            if p.value == key:
                self.profile = p
                return
        logger.warning(f"Unknown resource profile key: {key}")

    def register_listener(self, callback: callable):
        if callback not in self._listeners:
            self._listeners.append(callback)

    def unregister_listener(self, callback: callable):
        if callback in self._listeners:
            self._listeners.remove(callback)

    # ──────────────────────────────────────────
    # 参数查询（仅在 enabled=true 时有效，否则返回默认最大值）
    # ──────────────────────────────────────────

    def get_config(self, key: str):
        if not self._enabled:
            return None
        cfg = _PROFILE_CONFIGS.get(self._profile, _PROFILE_CONFIGS[ResourceProfile.BALANCED])
        return cfg.get(key)

    @property
    def cpu_thread_count(self) -> int:
        if not self._enabled:
            return self._physical_cpus  # 关闭时用满所有核心
        ratio = self.get_config("cpu_thread_ratio")
        return max(1, int(self._physical_cpus * ratio))

    @property
    def ncnn_threads(self) -> str:
        if not self._enabled:
            return "4:8:8"  # 关闭时用最大值
        l = self.get_config("ncnn_load_threads")
        p = self.get_config("ncnn_proc_threads")
        s = self.get_config("ncnn_save_threads")
        return f"{l}:{p}:{s}"

    # ── 模型推理参数 ──
    @property
    def model_batch_scale(self) -> float:
        """batch size缩放因子：影响STTN/ProPainter的maxLoadNum等内部批参数"""
        return self.get_config("model_batch_scale")

    @property
    def use_fp16(self) -> bool:
        """是否使用FP16半精度推理"""
        return self.get_config("use_fp16")

    @property
    def mask_dilation_scale(self) -> float:
        """mask膨胀像素数缩放：影响ProPainter/STTN的mask膨胀强度"""
        return self.get_config("mask_dilation_scale")

    @property
    def reference_frame_scale(self) -> float:
        """参考帧数量缩放：影响STTN neighbor_stride, reference_length等"""
        return self.get_config("reference_frame_scale")

    # ── 显存管理 ──
    @property
    def gc_interval_seconds(self) -> int:
        return self.get_config("gc_interval_seconds")

    @property
    def cache_models(self) -> bool:
        return self.get_config("cache_models")

    @property
    def gpu_monitor_interval_ms(self) -> int:
        return self.get_config("gpu_monitor_interval_ms")

    @property
    def suspend_idle_features(self) -> bool:
        return self.get_config("suspend_idle_features")

    # ──────────────────────────────────────────
    # 实用方法：获取各模型缩放后的内部参数
    # ──────────────────────────────────────────

    def scaled_batch_size(self, base_batch_size: int) -> int:
        """根据等级缩放batch size"""
        return max(1, int(base_batch_size * self.model_batch_scale))

    def scaled_mask_dilation(self, base_dilation: int) -> int:
        """根据等级缩放mask膨胀像素"""
        return max(0, int(base_dilation * self.mask_dilation_scale))

    def scaled_reference_frames(self, base_frames: int) -> int:
        """根据等级缩放参考帧数"""
        return max(1, int(base_frames * self.reference_frame_scale))

    # ──────────────────────────────────────────
    # 应用/恢复配置
    # ──────────────────────────────────────────

    def _apply_profile(self):
        """应用当前等级的环境级配置"""
        if not self._enabled:
            return
        cv_threads = self.cpu_thread_count

        try:
            import cv2
            cv2.setNumThreads(cv_threads)
        except ImportError:
            pass

        os.environ["OMP_NUM_THREADS"] = str(cv_threads)
        os.environ["MKL_NUM_THREADS"] = str(cv_threads)
        os.environ["OPENBLAS_NUM_THREADS"] = str(cv_threads)
        os.environ["TORCH_NUM_THREADS"] = str(cv_threads)
        try:
            import torch
            torch.set_num_threads(cv_threads)
        except ImportError:
            pass

        os.environ["RIFE_NCNN_THREADS"] = self.ncnn_threads

        if self._profile in (ResourceProfile.POWER_SAVING, ResourceProfile.BALANCED):
            self.aggressive_gc()

        logger.info(
            f"资源管理已开启, 等级={self._profile.value}, "
            f"CPU线程={cv_threads}, NCNN={self.ncnn_threads}"
        )

    def _reset_to_default(self):
        """关闭资源管理时恢复默认设置（不限制）"""
        max_threads = self._physical_cpus

        try:
            import cv2
            cv2.setNumThreads(max_threads)
        except ImportError:
            pass

        os.environ["OMP_NUM_THREADS"] = str(max_threads)
        os.environ["MKL_NUM_THREADS"] = str(max_threads)
        os.environ["OPENBLAS_NUM_THREADS"] = str(max_threads)
        os.environ["TORCH_NUM_THREADS"] = str(max_threads)
        os.environ.pop("RIFE_NCNN_THREADS", None)  # 删除自定义限制，让rife用自身默认值
        try:
            import torch
            torch.set_num_threads(max_threads)
        except ImportError:
            pass

        logger.info(f"资源管理已关闭, 恢复默认CPU线程={max_threads}")

    @staticmethod
    def aggressive_gc():
        """主动清理 GPU 显存 + CPU 内存"""
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
        except ImportError:
            pass

    # ──────────────────────────────────────────
    # GPU Monitor 绑定
    # ──────────────────────────────────────────

    def bind_gpu_monitor(self, monitor_widget):
        self._gpu_monitor_ref = monitor_widget
        self._sync_gpu_monitor()

    def _sync_gpu_monitor(self):
        if self._gpu_monitor_ref is None:
            return
        try:
            interval = self.gpu_monitor_interval_ms
            self._gpu_monitor_ref.set_refresh_interval(interval)
            if self._profile == ResourceProfile.POWER_SAVING:
                self._gpu_monitor_ref.pause_if_needed()
            elif self._profile == ResourceProfile.PERFORMANCE:
                self._gpu_monitor_ref.resume_if_paused()
        except Exception:
            pass


def get_resource_manager() -> ResourceManager:
    return ResourceManager.instance()
