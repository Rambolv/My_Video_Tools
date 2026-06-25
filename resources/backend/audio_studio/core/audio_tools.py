"""
通用音频工具 — 底层音频读写/处理, 不依赖外部模型
"""
import numpy as np
import soundfile as sf
import tempfile
import os
from typing import Optional, Tuple


class AudioToolKit:
    """轻量音频工具 (无需ffmpeg)"""

    SAMPLE_RATE = 48000

    @staticmethod
    def load(path: str, sr: Optional[int] = None) -> Tuple[np.ndarray, int]:
        """加载音频, 自动重采样"""
        data, orig_sr = sf.read(path)
        if sr is not None and sr != orig_sr:
            from scipy import signal
            ratio = sr / orig_sr
            new_len = int(len(data) * ratio)
            data = signal.resample(data, new_len)
            return data, sr
        return data, orig_sr

    @staticmethod
    def save(path: str, data: np.ndarray, sr: int = 48000):
        """保存音频"""
        sf.write(path, data, sr)

    @staticmethod
    def to_mono(data: np.ndarray) -> np.ndarray:
        if len(data.shape) > 1:
            return data.mean(axis=1)
        return data

    @staticmethod
    def normalize_peak(data: np.ndarray, target_db: float = -1.0) -> np.ndarray:
        """峰值归一化"""
        peak = np.max(np.abs(data))
        if peak == 0:
            return data
        target_amp = 10 ** (target_db / 20)
        return data * (target_amp / peak)

    @staticmethod
    def trim_silence(data: np.ndarray, threshold: float = 0.005, sr: int = 48000) -> np.ndarray:
        """首尾静音切除"""
        indices = np.where(np.abs(data) > threshold)[0]
        if len(indices) == 0:
            return data
        return data[indices[0]:indices[-1] + 1]

    @staticmethod
    def get_temp_path(suffix: str = ".wav") -> str:
        return tempfile.NamedTemporaryFile(suffix=suffix, delete=False).name
