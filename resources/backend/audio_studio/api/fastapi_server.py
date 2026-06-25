"""
FastAPI 接口服务 — 提供 RESTful API 供外部调用
"""
import os
import sys
import uvicorn
import logging
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from ..config import get_config
from ..core.voice_engine import VoxCPM2Engine, VoiceGenerationParams
from ..core.music_engine import AceStepEngine, MusicGenerationParams
from .schemas import (
    TTSRequest, VoiceCloneRequest, VoiceDesignRequest, VoiceConvertRequest,
    TextToMusicRequest, ContinueMusicRequest, RepaintRequest,
    AudioResponse, BatchTTSRequest,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Audio Studio API",
    description="声音自由生成修改大师 — RESTful API",
    version="1.0.0",
)

# 全局引擎实例（懒加载）
_voice_engine: Optional[VoxCPM2Engine] = None
_music_engine: Optional[AceStepEngine] = None


def get_voice_engine() -> VoxCPM2Engine:
    global _voice_engine
    if _voice_engine is None:
        cfg = get_config()
        _voice_engine = VoxCPM2Engine(device=cfg.device, dtype=cfg.dtype)
    return _voice_engine


def get_music_engine() -> AceStepEngine:
    global _music_engine
    if _music_engine is None:
        cfg = get_config()
        _music_engine = AceStepEngine(device=cfg.device, dtype=cfg.dtype)
    return _music_engine


# ═══════════════════════════════════════════
# 健康检查
# ═══════════════════════════════════════════

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "audio-studio"}


# ═══════════════════════════════════════════
# 人声 API
# ═══════════════════════════════════════════

@app.post("/v1/tts", response_model=AudioResponse)
def tts_endpoint(req: TTSRequest):
    """高质量文本转语音"""
    try:
        engine = get_voice_engine()
        params = VoiceGenerationParams(
            text=req.text, speed=req.speed,
            emotion=req.emotion, language=req.language,
        )
        output = engine.tts(req.text, params)
        return AudioResponse(success=True, audio_path=output)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/voice/clone", response_model=AudioResponse)
def voice_clone(req: VoiceCloneRequest):
    """声音克隆"""
    try:
        engine = get_voice_engine()
        output = engine.clone_voice(
            text=req.text, ref_audio=req.ref_audio,
            ref_text=req.ref_text, ultimate=req.ultimate,
        )
        return AudioResponse(success=True, audio_path=output)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/voice/design", response_model=AudioResponse)
def voice_design(req: VoiceDesignRequest):
    """文本设计音色"""
    try:
        engine = get_voice_engine()
        output = engine.design_voice(req.text, req.voice_description)
        return AudioResponse(success=True, audio_path=output)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/voice/convert", response_model=AudioResponse)
def voice_convert(req: VoiceConvertRequest):
    """音色转换"""
    try:
        engine = get_voice_engine()
        output = engine.convert_voice(
            source_audio=req.source_audio,
            ref_audio=req.ref_audio,
            mode=req.mode,
            text=req.text or "voice",
        )
        return AudioResponse(success=True, audio_path=output)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/tts/batch", response_model=dict)
def batch_tts(req: BatchTTSRequest):
    """批量 TTS"""
    try:
        engine = get_voice_engine()
        params = VoiceGenerationParams(speed=req.speed, language=req.language)
        outputs = engine.batch_process(req.texts, params)
        return {"success": True, "outputs": outputs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════
# 音乐 API
# ═══════════════════════════════════════════

@app.post("/v1/music/text2music", response_model=AudioResponse)
def text_to_music(req: TextToMusicRequest):
    """文生音乐"""
    try:
        engine = get_music_engine()
        params = MusicGenerationParams(
            caption=req.caption, lyrics=req.lyrics or "",
            instrumental=req.instrumental, duration=req.duration,
            inference_steps=req.steps,
        )
        result = engine.text_to_music(req.caption, params)
        return AudioResponse(
            success=True, audio_path=result.audio_path,
            duration=result.duration,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/music/continue", response_model=AudioResponse)
def continue_music(req: ContinueMusicRequest):
    """音乐续写"""
    try:
        engine = get_music_engine()
        result = engine.continue_music(req.reference_audio, req.duration)
        return AudioResponse(
            success=True, audio_path=result.audio_path,
            duration=result.duration,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/music/repaint", response_model=AudioResponse)
def repaint_music(req: RepaintRequest):
    """局部重绘"""
    try:
        engine = get_music_engine()
        result = engine.repaint(req.audio_path, req.start_sec, req.end_sec)
        return AudioResponse(
            success=True, audio_path=result.audio_path,
            duration=result.duration,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════
# 音频文件下载
# ═══════════════════════════════════════════

@app.get("/v1/audio/{file_path:path}")
def download_audio(file_path: str):
    """下载生成的音频文件"""
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(file_path, media_type="audio/wav")


# ═══════════════════════════════════════════
# 启动入口
# ═══════════════════════════════════════════

def start_api_server(host: str = "127.0.0.1", port: int = 8000):
    """启动 API 服务"""
    logger.info(f"🚀 Audio Studio API 启动: http://{host}:{port}")
    logger.info(f"📖 API 文档: http://{host}:{port}/docs")
    uvicorn.run(app, host=host, port=port, log_level="info")
