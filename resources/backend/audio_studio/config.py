"""
音频工作室配置 — 集中管理路径、设备、模型参数
"""
import os
import sys
import torch
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AudioStudioConfig:
    """全局配置"""

    # ─── 路径配置（内化路径） ───
    voxcpm2_path: str = ""   # 自动填充为 vendor/ai_audio/voxcpm2
    ace_step_path: str = ""  # 自动填充为 vendor/ai_audio/ace_step
    ace_output_dir: str = ""   # ACE 输出目录（自动填充为本项目）
    ace_checkpoints_dir: str = ""  # ACE 模型存放目录（自动填充为本项目）
    models_dir: str = ""  # 自动填充

    # ─── 设备配置 ───
    device: str = "cuda:0" if torch.cuda.is_available() else "cpu"
    dtype: str = "fp16"
    vram_limit_gb: float = 8.0  # 显存上限, 超出自动卸载

    # ─── 人声推理参数 ───
    voice_default_lang: str = "zh"
    voice_default_speed: float = 1.0
    voice_default_emotion: str = "neutral"
    voice_max_text_length: int = 5000

    # ─── 音乐推理参数 ───
    music_default_duration: int = 30
    music_max_duration: int = 600
    music_default_steps: int = 4  # ACE-Step turbo步数
    music_default_cfg: float = 3.0

    # ─── 服务端口 ───
    gradio_port: int = 7865
    api_port: int = 8000
    api_host: str = "127.0.0.1"

    # ─── 水印配置 ───
    enable_watermark: bool = True
    watermark_message: str = "AudioStudio"

    def __post_init__(self):
        root = os.path.dirname(os.path.abspath(__file__))
        _vendor_audio = os.path.join(root, "..", "..", "..", "vendor", "ai_audio")
        if not self.voxcpm2_path:
            self.voxcpm2_path = os.path.join(_vendor_audio, "voxcpm2")
        if not self.ace_step_path:
            self.ace_step_path = os.path.join(_vendor_audio, "ace_step")
        if not self.models_dir:
            self.models_dir = os.path.join(root, "models")
        if not self.ace_output_dir:
            self.ace_output_dir = os.path.join(root, "ace_outputs")
        if not self.ace_checkpoints_dir:
            self.ace_checkpoints_dir = os.path.join(root, "ace_checkpoints")
        for d in [self.models_dir, self.ace_output_dir, self.ace_checkpoints_dir]:
            os.makedirs(d, exist_ok=True)
        # 内化 HuggingFace 模型缓存
        _hf_cache = os.path.join(_vendor_audio, "models")
        # 注意：launch 脚本中的直接赋值优先级更高
        os.environ.setdefault("HF_HOME", _hf_cache)
        os.environ.setdefault("HUGGINGFACE_HUB_CACHE", os.path.join(_hf_cache, "hub"))
        os.makedirs(_hf_cache, exist_ok=True)

    def get_torch_dtype(self):
        return torch.float16 if self.dtype == "fp16" else torch.float32


_config: Optional[AudioStudioConfig] = None
_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_config.json")


def get_config() -> AudioStudioConfig:
    global _config
    if _config is None:
        _config = AudioStudioConfig()
        # 尝试从文件加载用户自定义路径
        _load_user_config(_config)
    return _config


def set_config(cfg: AudioStudioConfig):
    global _config
    _config = cfg


def save_config():
    """将当前配置写入 user_config.json（持久化）"""
    global _config
    if _config is None:
        return
    data = {
        "ace_output_dir": _config.ace_output_dir,
        "ace_checkpoints_dir": _config.ace_checkpoints_dir,
        "models_dir": _config.models_dir,
    }
    try:
        import json
        with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[config] 保存配置失败: {e}")


def _load_user_config(cfg: AudioStudioConfig):
    """从 user_config.json 加载用户自定义路径"""
    import json
    if not os.path.exists(_CONFIG_FILE):
        return
    try:
        with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key in ("ace_output_dir", "ace_checkpoints_dir", "models_dir"):
            val = data.get(key)
            if val and os.path.isabs(val):
                setattr(cfg, key, val)
    except Exception as e:
        print(f"[config] 加载配置失败: {e}")
