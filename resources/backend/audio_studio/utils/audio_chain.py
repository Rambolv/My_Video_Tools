"""
通用音频工具链 — 降噪、人声分离、格式转换、音量归一化
"""
import os
import tempfile
import subprocess
import numpy as np
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class AudioToolChain:
    """音频预处理/后处理工具链"""

    @staticmethod
    def resample(input_path: str, sr: int = 48000, output_path: Optional[str] = None) -> str:
        """重采样到目标采样率 (ffmpeg)"""
        if output_path is None:
            suffix = os.path.splitext(input_path)[1] or ".wav"
            output_path = tempfile.NamedTemporaryFile(suffix=suffix, delete=False).name
        cmd = ["ffmpeg", "-y", "-i", input_path,
               "-ar", str(sr), "-ac", "1",
               "-sample_fmt", "s16", output_path]
        subprocess.run(cmd, capture_output=True, check=False)
        return output_path

    @staticmethod
    def convert_format(input_path: str, fmt: str = "wav", output_path: Optional[str] = None) -> str:
        """格式转换"""
        if output_path is None:
            output_path = tempfile.NamedTemporaryFile(suffix=f".{fmt}", delete=False).name
        cmd = ["ffmpeg", "-y", "-i", input_path, output_path]
        subprocess.run(cmd, capture_output=True, check=False)
        return output_path

    @staticmethod
    def normalize(input_path: str, target_db: float = -1.0, output_path: Optional[str] = None) -> str:
        """音量归一化 (peak normalization)"""
        if output_path is None:
            suffix = os.path.splitext(input_path)[1] or ".wav"
            output_path = tempfile.NamedTemporaryFile(suffix=suffix, delete=False).name
        cmd = ["ffmpeg", "-y", "-i", input_path,
               "-af", f"volume={target_db}dB",
               output_path]
        subprocess.run(cmd, capture_output=True, check=False)
        return output_path

    @staticmethod
    def denoise(input_path: str, output_path: Optional[str] = None) -> str:
        """降噪 (ffmpeg anlmdn)"""
        if output_path is None:
            suffix = os.path.splitext(input_path)[1] or ".wav"
            output_path = tempfile.NamedTemporaryFile(suffix=suffix, delete=False).name
        cmd = ["ffmpeg", "-y", "-i", input_path,
               "-af", "anlmdn=s=7:p=0.5:o=2",
               output_path]
        subprocess.run(cmd, capture_output=True, check=False)
        return output_path

    @staticmethod
    def separate_vocals(input_path: str, output_dir: Optional[str] = None) -> Tuple[str, str]:
        """人声/伴奏分离 (Demucs 轻量调用)"""
        if output_dir is None:
            output_dir = tempfile.mkdtemp()
        try:
            cmd = ["python", "-m", "demucs", "--two-stems=vocals",
                   "-o", output_dir, input_path]
            subprocess.run(cmd, capture_output=True, check=False, timeout=120)
            base = os.path.splitext(os.path.basename(input_path))[0]
            vocals = os.path.join(output_dir, "htdemucs", base, "vocals.wav")
            no_vocals = os.path.join(output_dir, "htdemucs", base, "no_vocals.wav")
            if os.path.exists(vocals) and os.path.exists(no_vocals):
                return vocals, no_vocals
        except Exception as e:
            logger.warning(f"Demucs分离失败: {e}")
        return "", ""

    @staticmethod
    def get_duration(input_path: str) -> float:
        """获取音频时长(秒)"""
        try:
            import soundfile as sf
            info = sf.info(input_path)
            return info.duration
        except Exception:
            try:
                cmd = ["ffprobe", "-v", "error", "-show_entries",
                       "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
                       input_path]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                return float(result.stdout.strip())
            except Exception:
                return 0.0
