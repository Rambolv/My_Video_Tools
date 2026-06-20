"""
@desc: 被动 VRAM 监控器 — 在真实处理过程中采样 GPU 显存，记录峰值
不单独跑测试流程，而是跟随用户的实际工作自动采集数据
"""
from __future__ import annotations
import json
import os
import threading
import time
from typing import Dict, Optional
from pathlib import Path

import torch

# 配置文件路径
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_RECORDS_FILE = os.path.join(_BACKEND_DIR, 'config', 'vram_records.json')

# 采样间隔（秒）
_SAMPLE_INTERVAL = 0.5


class VramMonitor:
    """后台线程：定期采样 GPU 显存使用量"""

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._peak_mb = 0.0
        self._samples: list[float] = []
        self._lock = threading.Lock()

    @property
    def peak_gb(self) -> float:
        """采样期间的峰值显存（GB）"""
        with self._lock:
            return self._peak_mb / 1024.0

    @property
    def peak_mb(self) -> float:
        with self._lock:
            return self._peak_mb

    def start(self):
        """启动后台采样线程"""
        if not torch.cuda.is_available():
            return
        if self._thread is not None and self._thread.is_alive():
            return  # 已经在运行

        self._stop_event.clear()
        with self._lock:
            self._peak_mb = 0.0
            self._samples = []

        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()

    def stop(self) -> float:
        """停止采样，返回峰值显存（GB）"""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        return self.peak_gb

    def _sample_loop(self):
        """后台采样循环"""
        while not self._stop_event.is_set():
            try:
                if torch.cuda.is_available():
                    torch.cuda.synchronize()
                    allocated = torch.cuda.memory_allocated() / (1024 * 1024)  # MB
                    with self._lock:
                        self._samples.append(allocated)
                        if allocated > self._peak_mb:
                            self._peak_mb = allocated
            except Exception:
                pass
            self._stop_event.wait(_SAMPLE_INTERVAL)


# ==================== 记录管理 ====================

def _make_config_key(
    inpaint_mode: str,
    detect_mode: str,
    processing_depth: int,
    video_width: int,
    video_height: int,
    concurrent_tasks: int,
) -> str:
    """生成配置指纹键"""
    # 分辨率按档位归类，避免轻微差异产生不同键
    w_bucket = (video_width // 160) * 160
    h_bucket = (video_height // 90) * 90
    return f"{inpaint_mode}|{detect_mode}|{processing_depth}|{w_bucket}x{h_bucket}|con{concurrent_tasks}"


def load_records() -> Dict:
    """加载所有历史记录"""
    if not os.path.exists(_RECORDS_FILE):
        return {}
    try:
        with open(_RECORDS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_record(
    inpaint_mode: str,
    detect_mode: str,
    processing_depth: int,
    video_width: int,
    video_height: int,
    concurrent_tasks: int,
    peak_vram_gb: float,
    oom: bool = False,
):
    """
    保存一条实测记录。
    同一配置键的后一次记录会覆盖前一次。
    """
    key = _make_config_key(inpaint_mode, detect_mode, processing_depth,
                           video_width, video_height, concurrent_tasks)

    records = load_records()
    record = {
        "peak_vram_gb": round(peak_vram_gb, 2),
        "oom": oom,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "inpaint": inpaint_mode,
        "detect": detect_mode,
        "depth": processing_depth,
        "width": video_width,
        "height": video_height,
        "concurrent": concurrent_tasks,
    }
    if torch.cuda.is_available():
        try:
            record["gpu_name"] = torch.cuda.get_device_name(0)
            record["gpu_vram_gb"] = round(
                torch.cuda.get_device_properties(0).total_memory / (1024 ** 3), 1)
        except Exception:
            pass

    # 只在新数据或峰值更高时覆盖
    if key in records:
        old_peak = records[key].get("peak_vram_gb", 0)
        if peak_vram_gb <= old_peak and not oom:
            return  # 已有更高记录，不覆盖

    records[key] = record

    os.makedirs(os.path.dirname(_RECORDS_FILE), exist_ok=True)
    with open(_RECORDS_FILE, 'w', encoding='utf-8') as f:
        json.dump(records, f, indent=2, ensure_ascii=False)


def get_record_for_config(
    inpaint_mode: str,
    detect_mode: str,
    processing_depth: int,
    video_width: int = 1920,
    video_height: int = 1080,
    concurrent_tasks: int = 1,
) -> Optional[Dict]:
    """查询某配置是否已有实测记录"""
    key = _make_config_key(inpaint_mode, detect_mode, processing_depth,
                           video_width, video_height, concurrent_tasks)
    records = load_records()
    return records.get(key)


def get_all_model_peak_vrams() -> Dict[str, Dict]:
    """
    从历史记录中提取各模型组合在最宽泛条件下的峰值。
    用于更新 VRAM 参考表。
    返回 {model_key: {"peak_vram_gb": float, "oom": bool, ...}}
    """
    from backend.tools.constant import InpaintMode, SubtitleDetectMode

    records = load_records()
    model_peaks: Dict[str, Dict] = {}

    for key, rec in records.items():
        parts = key.split("|")
        if len(parts) < 2:
            continue
        inpaint_key = parts[0]
        detect_key = parts[1]

        # 更新修复模型侧峰值
        if inpaint_key not in model_peaks or rec["peak_vram_gb"] > model_peaks[inpaint_key].get("peak_vram_gb", 0):
            model_peaks[inpaint_key] = rec

        # 更新检测模型侧峰值
        if detect_key not in model_peaks or rec["peak_vram_gb"] > model_peaks[detect_key].get("peak_vram_gb", 0):
            model_peaks[detect_key] = rec

    return model_peaks


def has_real_data() -> bool:
    """是否有至少一条实测记录"""
    return bool(load_records())


def get_records_file_path() -> str:
    return _RECORDS_FILE
