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