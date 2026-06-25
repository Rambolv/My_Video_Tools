"""
FastAPI 请求/响应数据模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List


# ─── 人声 ───

class TTSRequest(BaseModel):
    text: str = Field(..., description="输入文本", max_length=5000)
    speed: float = Field(1.0, ge=0.5, le=2.0)
    emotion: str = Field("neutral", description="情感: neutral/happy/sad/angry")
    language: str = Field("zh", description="语言代码")


class VoiceCloneRequest(BaseModel):
    text: str = Field(..., description="目标文本")
    ref_audio: str = Field(..., description="参考音频路径")
    ref_text: Optional[str] = Field(None, description="参考音频转录文本")
    ultimate: bool = Field(False, description="极致克隆模式")


class VoiceDesignRequest(BaseModel):
    text: str = Field(..., description="目标文本")
    voice_description: str = Field(..., description="音色描述, 如'温柔年轻女声'")


class VoiceConvertRequest(BaseModel):
    source_audio: str = Field(..., description="源音频路径")
    ref_audio: str = Field(..., description="目标音色参考音频")
    mode: str = Field("voice", description="voice=说话声, song=歌声")
    text: str = Field("voice", description="源音频内容文本（必填）")


# ─── 音乐 ───

class TextToMusicRequest(BaseModel):
    caption: str = Field(..., description="音乐描述", max_length=512)
    lyrics: Optional[str] = Field(None, description="歌词")
    instrumental: bool = Field(False, description="纯器乐")
    duration: int = Field(30, ge=10, le=600)
    genre: Optional[str] = Field(None, description="风格")
    steps: int = Field(4, ge=1, le=100)


class ContinueMusicRequest(BaseModel):
    reference_audio: str = Field(..., description="参考音频路径")
    duration: int = Field(120, ge=30, le=600)


class RepaintRequest(BaseModel):
    audio_path: str = Field(..., description="源音频路径")
    start_sec: float = Field(..., description="重绘起始秒")
    end_sec: float = Field(-1, description="重绘结束秒, -1=直到结束")


# ─── 通用 ───

class AudioResponse(BaseModel):
    success: bool
    audio_path: Optional[str] = None
    duration: Optional[float] = None
    message: Optional[str] = None


class BatchTTSRequest(BaseModel):
    texts: List[str] = Field(..., description="文本列表")
    speed: float = Field(1.0)
    language: str = Field("zh")
