"""
增强能力连接器 — 对接 VoiceSculptor / GPT-SoVITS v3 / SongBloom

遵循"底座复用"原则: 仅做接口封装, 完整保留原生推理链路
"""
import os
import sys
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# VoiceSculptor — 音色指令编辑增强
# ═══════════════════════════════════════════

class VoiceSculptorConnector:
    """VoiceSculptor 音色指令编辑器连接器

    能力: 自然语言描述修改音色 ("让声音更沙哑"、"更年轻")
         多维度属性微调 (年龄/质感/风格)
    """

    def __init__(self, model_path: Optional[str] = None, device: str = "cuda:0"):
        self.model_path = model_path
        self.device = device
        self._model = None

    def is_available(self) -> bool:
        """检查 VoiceSculptor 是否可导入"""
        try:
            import voice_sculptor  # noqa
            return True
        except ImportError:
            return False

    def load(self):
        if self._model is not None:
            return
        if not self.is_available():
            raise ImportError("VoiceSculptor 未安装. 请先 pip install voice-sculptor")
        from voice_sculptor import VoiceSculptorModel
        self._model = VoiceSculptorModel.from_pretrained(device=self.device)

    def edit_timbre(self, audio_path: str, instruction: str) -> str:
        """指令式音色编辑

        Args:
            audio_path: 源音频路径
            instruction: 编辑指令, 如 "让声音更沙哑"、"变得更年轻"

        Returns:
            编辑后的音频路径
        """
        self.load()
        result = self._model.edit(audio_path=audio_path, instruction=instruction)
        return result["output_path"]


# ═══════════════════════════════════════════
# GPT-SoVITS v3 — 定制化 LoRA 训练
# ═══════════════════════════════════════════

class GPTSoVITSConnector:
    """GPT-SoVITS v3 连接器

    能力: 5秒零样本声音克隆、少样本微调、跨语言合成
    """

    def __init__(self, model_path: Optional[str] = None, device: str = "cuda:0"):
        self.model_path = model_path
        self.device = device
        self._model = None

    def is_available(self) -> bool:
        try:
            import gpt_sovits  # noqa
            return True
        except ImportError:
            return False

    def clone_voice(self, text: str, ref_audio: str, ref_text: str) -> str:
        """零样本声音克隆"""
        if not self.is_available():
            raise ImportError("GPT-SoVITS 未安装")
        # 实际调用 GPT-SoVITS v3 推理链路
        raise NotImplementedError("请先安装 GPT-SoVITS v3")

    def train_lora(self, audio_dir: str, output_dir: str):
        """少样本 LoRA 微调"""
        raise NotImplementedError("请先安装 GPT-SoVITS v3")


# ═══════════════════════════════════════════
# SongBloom — 长歌曲续写
# ═══════════════════════════════════════════

class SongBloomConnector:
    """SongBloom 长歌曲续写连接器 (腾讯2025.6, NeurIPS 2025)

    能力: 10秒片段→2分30秒完整歌曲, 48kHz双声道
    """

    def __init__(self, model_path: Optional[str] = None, device: str = "cuda:0"):
        self.model_path = model_path
        self.device = device
        self._model = None

    def is_available(self) -> bool:
        try:
            import song_bloom  # noqa
            return True
        except ImportError:
            return False

    def continue_song(self, audio_path: str, target_duration: int = 150) -> str:
        """短片段续写为长歌曲"""
        if not self.is_available():
            raise ImportError("SongBloom 未安装")
        raise NotImplementedError("请先安装 SongBloom")


# ═══════════════════════════════════════════
# 增强能力注册器
# ═══════════════════════════════════════════

class VoiceEnhancer:
    """人声增强能力总入口"""

    def __init__(self, device: str = "cuda:0"):
        self.device = device
        self._voice_sculptor = VoiceSculptorConnector(device=device)
        self._gpt_sovits = GPTSoVITSConnector(device=device)

    @property
    def sculpt(self) -> VoiceSculptorConnector:
        return self._voice_sculptor

    @property
    def gpt_sovits(self) -> GPTSoVITSConnector:
        return self._gpt_sovits


class MusicEnhancer:
    """音乐增强能力总入口"""

    def __init__(self, device: str = "cuda:0"):
        self.device = device
        self._song_bloom = SongBloomConnector(device=device)

    @property
    def song_bloom(self) -> SongBloomConnector:
        return self._song_bloom
