"""
VoxCPM2 人声引擎 — 完全复用原生推理链路, 模块化封装

原生架构: AudioVAE V2 + LocEnc → TSLM → RALM → LocDiT 四阶段扩散自回归
正确 API: VoxCPM.from_pretrained() → model.generate(text=..., ...)
"""
import os
import sys
import warnings

# ─── 屏蔽第三方库弃用警告 ───
warnings.filterwarnings("ignore", category=FutureWarning,
                       message=".*weight_norm.*")

os.environ.setdefault("PYTHONNOUSERSITE", "1")

# ─── 模型缓存内化到本项目（共享 AI 音频模型缓存） ───
_HF_CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "..", "..", "..", "..", "vendor", "ai_audio", "models")
os.environ["HF_HOME"] = _HF_CACHE
os.environ["HUGGINGFACE_HUB_CACHE"] = os.path.join(_HF_CACHE, "hub")

import threading
import numpy as np
import torch
import logging
import soundfile as sf
from typing import Optional, List
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_VOXCPM2_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "..", "..", "..", "vendor", "ai_audio", "voxcpm2")
if _VOXCPM2_SRC not in sys.path:
    sys.path.insert(0, _VOXCPM2_SRC)

# 模型加载辅助 — 优先用本地缓存，不存在则回退到 HuggingFace ID
def _resolve_model_cache_dir() -> str:
    """返回 VoxCPM2 模型快照目录（可能不存在）"""
    _root = os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),        # core/
        "..", "..", "..", "..", ".."                       # → 项目根
    ))
    return os.path.join(_root, "vendor", "ai_audio", "models", "hub",
                        "models--openbmb--VoxCPM2", "snapshots")


def _resolve_model_path() -> str:
    """解析 VoxCPM2 模型路径：本地缓存 → HF Hub ID 回退"""
    cache_dir = _resolve_model_cache_dir()
    if os.path.isdir(cache_dir):
        snapshots = sorted(os.listdir(cache_dir), reverse=True)
        if snapshots:
            path = os.path.join(cache_dir, snapshots[0])
            logger.info(f"📦 VoxCPM2 本地缓存: {path}")
            return path

    logger.warning("⚠️ VoxCPM2 本地缓存未找到，将尝试在线下载")
    logger.warning(f"   预期缓存路径: {cache_dir}")
    logger.warning("   （如果网络受限，可用 hf-mirror.com 或 ModelScope 镜像）")
    return "openbmb/VoxCPM2"

_DEFAULT_MODEL_PATH = _resolve_model_path()


@dataclass
class VoiceGenerationParams:
    """人声生成参数"""
    text: str = ""
    speed: float = 1.0
    emotion: str = "neutral"
    language: str = "zh"
    ref_audio: Optional[str] = None
    ref_text: Optional[str] = None
    voice_description: Optional[str] = None
    source_audio: Optional[str] = None
    convert_mode: str = "voice"
    output_path: Optional[str] = None


class VoxCPM2Engine:
    """
    VoxCPM2 引擎 — 封装原生 VoxCPM API

    用法:
        engine = VoxCPM2Engine()
        engine.tts("你好世界")              # 文字转语音
        engine.clone_voice("你好", ref)     # 声音克隆
        engine.design_voice("你好", "描述")  # 音色设计
        engine.convert_voice(src, ref)      # 音色转换
    """

    def __init__(self, device: str = "cuda:0"):
        self.device = device if torch.cuda.is_available() and "cuda" in device else "cpu"
        self._voxcpm = None
        self._sample_rate = 48000
        self._gen_lock = threading.Lock()

    # ─── 模型加载/卸载 ───

    @staticmethod
    def _download_with_fallback(model_id: str, **kwargs):
        """带国内镜像回退的模型下载"""
        from voxcpm import VoxCPM
        import huggingface_hub as hf_hub

        # 第一次尝试：直接下载
        try:
            return VoxCPM.from_pretrained(hf_model_id=model_id, **kwargs)
        except Exception as e:
            err_str = str(e)
            # 只有 SSL/连接类错误才尝试镜像
            if "SSL" not in err_str and "connect" not in err_str.lower() and "timeout" not in err_str.lower():
                raise  # 非网络错误直接抛出

        # 第二次尝试：HF 镜像（国内加速）
        mirror_url = os.environ.get("HF_ENDPOINT") or "https://hf-mirror.com"
        old_endpoint = os.environ.get("HF_ENDPOINT")
        os.environ["HF_ENDPOINT"] = mirror_url
        # 清除 huggingface_hub 的缓存 endpoint
        if hasattr(hf_hub, "constants"):
            hf_hub.constants.HF_ENDPOINT = mirror_url
        logger.warning(f"⚠️ HuggingFace 直连失败，尝试镜像: {mirror_url}")
        try:
            return VoxCPM.from_pretrained(hf_model_id=model_id, **kwargs)
        except Exception as e2:
            logger.warning(f"❌ 镜像下载也失败: {e2}")
            logger.warning("💡 请尝试手动下载模型:")
            logger.warning(f"   1. 访问 https://hf-mirror.com/{model_id}")
            logger.warning(f"   2. 下载到 {_resolve_model_cache_dir()}")
            raise
        finally:
            if old_endpoint:
                os.environ["HF_ENDPOINT"] = old_endpoint
            else:
                os.environ.pop("HF_ENDPOINT", None)

    def load(self):
        if self._voxcpm is not None:
            return
        logger.info("🔄 加载 VoxCPM2 模型...")
        from voxcpm import VoxCPM
        model_id = _DEFAULT_MODEL_PATH

        # 有本地缓存 → 直接加载
        if os.path.isdir(model_id):
            logger.info(f"  📂 本地模型: {model_id}")
            try:
                self._voxcpm = VoxCPM.from_pretrained(
                    hf_model_id=model_id,
                    device=self.device,
                    optimize=torch.cuda.is_available(),
                    load_denoiser=False,
                )
            except Exception as e:
                logger.error(f"❌ 本地模型加载失败: {e}")
                raise
        else:
            # 无本地缓存 → 在线下载（含镜像回退）
            logger.info(f"  🌐 在线下载: {model_id}")
            try:
                self._voxcpm = self._download_with_fallback(
                    model_id,
                    device=self.device,
                    optimize=torch.cuda.is_available(),
                    load_denoiser=False,
                )
            except Exception as e:
                logger.error(f"❌ VoxCPM2 加载失败: {e}")
                raise

        if hasattr(self._voxcpm.tts_model, "sample_rate"):
            self._sample_rate = self._voxcpm.tts_model.sample_rate
        logger.info(f"✅ VoxCPM2 加载完成 (采样率: {self._sample_rate}Hz)")

    def unload(self):
        if self._voxcpm is not None:
            del self._voxcpm
            self._voxcpm = None
            import gc
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.info("🔄 VoxCPM2 已卸载")

    @property
    def is_loaded(self) -> bool:
        return self._voxcpm is not None

    # ─── TTS ───

    def tts(self, text: str, params: Optional[VoiceGenerationParams] = None) -> str:
        """文字转语音"""
        self.load()
        with self._gen_lock:
            p = params or VoiceGenerationParams()
            texts = self._split_text(text)
            chunks = []

            for seg in texts:
                audio = self._voxcpm.generate(
                    text=seg,
                    cfg_value=2.0,
                    inference_timesteps=10,
                    normalize=True,
                    denoise=True,
                )
                chunks.append(audio)

            audio = np.concatenate(chunks) if len(chunks) > 1 else chunks[0]
            out = p.output_path or self._tmp_path()
            sf.write(out, audio, self._sample_rate)
            return out

    # ─── 声音克隆 ───

    def clone_voice(self, text: str, ref_audio: str,
                    ref_text: Optional[str] = None,
                    ultimate: bool = False,
                    params: Optional[VoiceGenerationParams] = None) -> str:
        """声音克隆: ref_audio 为参考音频, ref_text 为转录文本(极致克隆需要)"""
        self.load()
        with self._gen_lock:
            p = params or VoiceGenerationParams()
            audio = self._voxcpm.generate(
                text=text,
                prompt_wav_path=ref_audio,
                prompt_text=ref_text,
                cfg_value=2.0,
                inference_timesteps=10,
                normalize=True,
                denoise=True,
            )
            out = p.output_path or self._tmp_path()
            sf.write(out, audio, self._sample_rate)
            return out

    # ─── 声音设计 ───

    def design_voice(self, text: str, voice_description: str,
                     params: Optional[VoiceGenerationParams] = None) -> str:
        """文本设计音色: 用 control text 描述音色特征"""
        self.load()
        with self._gen_lock:
            p = params or VoiceGenerationParams()
            final_text = f"({voice_description}){text}" if voice_description else text
            audio = self._voxcpm.generate(
                text=final_text,
                cfg_value=2.0,
                inference_timesteps=10,
                normalize=True,
                denoise=True,
            )
            out = p.output_path or self._tmp_path()
            sf.write(out, audio, self._sample_rate)
            return out

    # ─── 音色转换 ───

    def convert_voice(self, source_audio: str, ref_audio: str,
                      mode: str = "voice",
                      text: str = "",
                      params: Optional[VoiceGenerationParams] = None) -> str:
        """音色转换: 用 reference_audio 作为目标音色，text 为源音频内容文本
        注意：VoxCPM2 的 prompt_wav_path 必须配套 prompt_text 使用，此处仅用
        reference_wav_path（音色参考）+ text（内容文本）实现换声。
        """
        self.load()
        with self._gen_lock:
            p = params or VoiceGenerationParams()
            final_text = text.strip() or "voice"
            audio = self._voxcpm.generate(
                text=final_text,
                reference_wav_path=ref_audio,
                # 不传 prompt_wav_path —— 它需要配套 prompt_text，
                # 此处由 reference_wav_path 单独提供音色参考
                cfg_value=2.0,
                inference_timesteps=10,
                normalize=True,
                denoise=True,
            )
            out = p.output_path or self._tmp_path()
            sf.write(out, audio, self._sample_rate)
            return out

    # ─── 工具方法 ───

    def _split_text(self, text: str, max_len: int = 500) -> List[str]:
        if len(text) <= max_len:
            return [text]
        import re
        parts = re.split(r'([。！？.!?])', text)
        chunks, cur = [], ""
        for part in parts:
            if len(cur) + len(part) > max_len and cur:
                chunks.append(cur.strip())
                cur = part
            else:
                cur += part
        if cur.strip():
            chunks.append(cur.strip())
        return chunks or [text]

    def _tmp_path(self, suffix=".wav") -> str:
        import uuid
        try:
            from ..config import get_config
            out_dir = get_config().ace_output_dir
        except Exception:
            out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ace_outputs")
        os.makedirs(out_dir, exist_ok=True)
        return os.path.join(out_dir, f"voice_{uuid.uuid4().hex}{suffix}")

    def __enter__(self):
        self.load()
        return self

    def __exit__(self, *args):
        self.unload()
