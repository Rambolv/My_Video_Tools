"""
模型管理器 — 懒加载 + 自动显存回收 + FP16/INT8量化
"""
import os
import sys
import gc
import torch
import logging
from typing import Optional, Callable
from threading import Lock

logger = logging.getLogger(__name__)


class ModelManager:
    """统一模型生命周期管理"""

    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._loaded = {}
                cls._instance._vram_limit = 8.0  # GB
            return cls._instance

    def register(self, name: str, loader: Callable, weight: float = 2.0):
        """注册模型加载器

        Args:
            name: 模型唯一标识
            loader: 返回模型的回调
            weight: 模型预估显存占用(GB), 用于调度
        """
        self._loaded[name] = {
            "loader": loader,
            "weight": weight,
            "instance": None,
            "in_use": False,
        }

    def get(self, name: str):
        """获取模型实例（懒加载）"""
        info = self._loaded.get(name)
        if info is None:
            raise KeyError(f"模型未注册: {name}")
        if info["instance"] is None:
            logger.info(f"🔄 加载模型: {name} (预估 {info['weight']}GB)")
            info["instance"] = info["loader"]()
            info["in_use"] = True
        else:
            info["in_use"] = True
        return info["instance"]

    def unload(self, name: str):
        """卸载指定模型"""
        info = self._loaded.get(name)
        if info and info["instance"] is not None:
            logger.info(f"🔄 卸载模型: {name}")
            del info["instance"]
            info["instance"] = None
            info["in_use"] = False
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    def unload_all(self):
        """卸载所有模型"""
        for name in list(self._loaded.keys()):
            self.unload(name)

    def get_vram_usage_gb(self) -> float:
        """获取当前 CUDA 显存占用 (GB)"""
        if torch.cuda.is_available():
            return torch.cuda.memory_allocated() / 1024**3
        return 0.0

    def set_vram_limit(self, gb: float):
        self._vram_limit = gb

    def auto_offload(self, exclude: Optional[str] = None):
        """自动卸载未使用的模型以释放显存"""
        current = self.get_vram_usage_gb()
        if current <= self._vram_limit:
            return
        logger.info(f"⚠️ 显存 {current:.1f}GB > 阈值 {self._vram_limit}GB, 自动卸载")
        for name, info in self._loaded.items():
            if name == exclude:
                continue
            if not info["in_use"] and info["instance"] is not None:
                self.unload(name)
                current = self.get_vram_usage_gb()
                if current <= self._vram_limit:
                    break
