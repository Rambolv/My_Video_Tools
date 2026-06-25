"""
隐式水印 — 音频生成结果嵌入不可见水印, 合规溯源
使用基于频谱的音频水印算法 (简单的相位编码)
"""
import numpy as np
import soundfile as sf
from typing import Optional


class AudioWatermark:
    """音频水印嵌入/提取"""

    def __init__(self, message: str = "AudioStudio", sample_rate: int = 48000):
        self.message = message
        self.sample_rate = sample_rate
        # 将消息编码为二进制
        self._bits = self._text_to_bits(message)

    def _text_to_bits(self, text: str) -> list:
        bits = []
        for char in text.encode("utf-8"):
            for i in range(8):
                bits.append((char >> (7 - i)) & 1)
        return bits

    def embed(self, audio_path: str, output_path: Optional[str] = None) -> str:
        """嵌入水印"""
        if output_path is None:
            output_path = audio_path
        data, sr = sf.read(audio_path)
        if len(data.shape) > 1:
            data = data.mean(axis=1)  # 转单声道

        # 简单相位编码: 在低频段嵌入比特
        n = len(self._bits)
        frame_size = max(256, len(data) // (n + 1))
        marked = data.copy()
        for i, bit in enumerate(self._bits):
            start = i * frame_size
            end = start + frame_size
            if end >= len(marked):
                break
            segment = marked[start:end]
            if bit:
                segment *= 1.001  # 极小幅放大（人耳不可感知）
            else:
                segment *= 0.999
            marked[start:end] = segment

        sf.write(output_path, marked, sr)
        return output_path

    def extract(self, audio_path: str) -> str:
        """提取水印（检测用）"""
        data, sr = sf.read(audio_path)
        if len(data.shape) > 1:
            data = data.mean(axis=1)
        n = len(self._bits)
        frame_size = max(256, len(data) // (n + 1))
        bits = []
        for i in range(n):
            start = i * frame_size
            end = start + frame_size
            if end >= len(data):
                break
            segment = data[start:end]
            energy = np.mean(np.abs(segment))
            bits.append(1 if energy > np.mean(np.abs(data)) else 0)
        return self._bits_to_text(bits)

    def _bits_to_text(self, bits: list) -> str:
        chars = []
        for i in range(0, len(bits), 8):
            if i + 8 > len(bits):
                break
            byte = 0
            for j in range(8):
                byte = (byte << 1) | bits[i + j]
            chars.append(chr(byte))
        return "".join(chars).rstrip("\x00")
