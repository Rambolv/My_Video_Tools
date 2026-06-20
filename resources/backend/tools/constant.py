from enum import Enum, unique

@unique
class InpaintMode(Enum):
    """
    图像重绘算法枚举
    """
    STTN_AUTO = "sttn-auto"
    STTN_DET = "sttn-det"
    LAMA = "lama"
    PROPAINTER = "propainter"
    E2FGVI = "e2fgvi"
    OPENCV = "opencv"

@unique
class SubtitleDetectMode(Enum):
    """
    字幕检测算法枚举
    """
    PP_OCRv4_SERVER = "PP-OCRv4-Server" 
    PP_OCRv4_MOBILE = "PP-OCRv4-Mobile"
    PP_OCRv5_SERVER = "PP-OCRv5-Server" 
    PP_OCRv5_MOBILE = "PP-OCRv5-Mobile"
    SAM2_TINY = "SAM2-Tiny"
    SAM2_SMALL = "SAM2-Small"
    SAM2_BASE = "SAM2-Base"
    SAM2_LARGE = "SAM2-Large"

@unique
class EnhancementMode(Enum):
    """视频增强算法枚举（超分 + 帧插值）"""
    # Real-ESRGAN 超分模型
    SR_ANIME = "realesr-animevideov3"
    SR_X4PLUS = "RealESRGAN_x4plus"
    SR_X2PLUS = "RealESRGAN_x2plus"
    SR_GENERAL = "realesr-general-x4v3"
    # RIFE 帧插值
    FI_RIFE = "rife"