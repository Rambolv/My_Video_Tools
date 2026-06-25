"""
声音自由生成修改大师 — Audio Studio
人声：VoxCPM2 (四阶段扩散自回归, 48kHz)
音乐：ACE-Step 1.5 (LM规划器+DiT扩散, 4步极速)
"""
__version__ = "1.0.0"
__author__ = "Audio Studio Team"

from .config import AudioStudioConfig, get_config, set_config
