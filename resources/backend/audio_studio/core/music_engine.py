"""
ACE-Step 1.5 音乐引擎 — 完全复用原生推理链路, 模块化封装

原生架构: LM规划器(CoT生成音乐蓝图) + DiT扩散解码器
支持: 文生音乐 / 歌词生成歌曲 / 音乐编辑 / 续写 / 风格迁移
"""
import os
import sys
import warnings

warnings.filterwarnings("ignore", category=FutureWarning,
                       message=".*weight_norm.*")

import threading
import numpy as np
import torch
import logging
import soundfile as sf
from typing import Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

# ─── 路径注入（内化路径） ───
_ACE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "..", "..", "..", "vendor", "ai_audio", "ace_step")
if _ACE_PATH not in sys.path:
    sys.path.insert(0, _ACE_PATH)


def _get_ace_output_dir() -> str:
    """获取 ACE 输出目录（优先读取用户配置）"""
    try:
        from ..config import get_config
        return get_config().ace_output_dir
    except Exception:
        return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ace_outputs")


class TaskType(str, Enum):
    TEXT2MUSIC = "text2music"
    COVER = "cover"
    REPAINT = "repaint"
    LEGO = "lego"
    EXTRACT = "extract"
    COMPLETE = "complete"


@dataclass
class MusicGenerationParams:
    """音乐生成参数"""
    caption: str = ""                     # 主提示词 < 512 chars
    lyrics: str = ""                      # 歌词, "[Instrumental]"=纯器乐
    instrumental: bool = False
    bpm: Optional[int] = None             # 30~300
    key_scale: str = ""                   # "C Major", "Am"
    time_signature: Optional[int] = None  # 2/3/4/6
    vocal_language: str = "zh"
    duration: int = 30                    # 目标时长(秒)
    inference_steps: int = 4              # 扩散步数 (turbo=4, base=32+)
    guidance_scale: float = 3.0
    seed: int = -1                        # -1=随机
    task_type: str = "text2music"

    # 音乐编辑
    reference_audio: Optional[str] = None  # 参考音频(翻唱/续写)
    src_audio: Optional[str] = None        # 源音频(重绘/分离)
    repaint_start: Optional[float] = None  # 重绘开始秒
    repaint_end: Optional[float] = None    # 重绘结束秒 (-1=直到结束)
    audio_cover_strength: float = 0.5      # 参考音频影响强度

    # LM 推理
    thinking: bool = True                  # 启用 CoT 推理
    lm_temperature: float = 1.0
    lm_cfg_scale: float = 2.0

    # 输出
    output_path: Optional[str] = None


@dataclass
class MusicTaskResult:
    """音乐生成结果"""
    audio_path: str
    duration: float
    metadata: dict = field(default_factory=dict)


class AceStepEngine:
    """
    ACE-Step 1.5 音乐引擎封装

    使用方法:
        engine = AceStepEngine()
        # 文生音乐
        result = engine.text_to_music("流行情歌, 女声, 120bpm")
        # 歌词生成歌曲
        result = engine.lyrics_to_song("你的歌词...", genre="pop")
        # 续写
        result = engine.continue_music("input.wav", duration=60)
        # 局部重绘
        result = engine.repaint("input.wav", start=10, end=20)
    """

    def __init__(self, device: str = "cuda:0", dtype: str = "fp16"):
        self.device = device if torch.cuda.is_available() and "cuda" in device else "cpu"
        self.dtype = torch.float16 if dtype == "fp16" and self.device != "cpu" else torch.float32
        self._handler = None
        self._loaded = False
        self._gen_lock = threading.Lock()  # 串行化生成，避免并发 CUDA 错误

    # ─── 模型生命周期 ───

    def load(self):
        """加载 ACE-Step 模型"""
        if self._loaded:
            return
        logger.info("🔄 加载 ACE-Step 1.5 模型...")
        try:
            # 使用 ACE-Step 的 handler
            from acestep.handler import AceStepHandler
            self._handler = AceStepHandler(
                device=self.device,
                dtype=self.dtype,
            )
            self._loaded = True
            logger.info("✅ ACE-Step 1.5 模型加载完成 (4步极速推理)")
        except ImportError as e:
            logger.error(f"❌ 无法导入 ACE-Step: {e}")
            logger.error(f"   请确认 ACE-Step 已安装在: {_ACE_PATH}")
            raise
        except Exception as e:
            logger.error(f"❌ ACE-Step 加载失败: {e}")
            raise

    def unload(self):
        """卸载模型"""
        if self._handler is not None:
            del self._handler
            self._handler = None
            self._loaded = False
            import gc
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.info("🔄 ACE-Step 模型已卸载")

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    # ─── 文生音乐 ───

    def text_to_music(self, caption: str,
                      params: Optional[MusicGenerationParams] = None) -> MusicTaskResult:
        """自然语言描述生成完整歌曲"""
        self.load()
        with self._gen_lock:
            p = params or MusicGenerationParams()
            p.caption = caption
            p.task_type = TaskType.TEXT2MUSIC

            result = self._handler.generate_music(
                prompt=p.caption,
                duration=p.duration,
                lyrics=p.lyrics or None,
                genre=None,
                steps=p.inference_steps,
                cfg=p.guidance_scale,
                seed=p.seed,
                thinking=p.thinking,
            )
            return self._save_result(result, p)

    # ─── 歌词生成歌曲 ───

    def lyrics_to_song(self, lyrics: str, genre: str = "pop",
                       params: Optional[MusicGenerationParams] = None) -> MusicTaskResult:
        """输入歌词自动匹配旋律+编曲+人声"""
        self.load()
        with self._gen_lock:
            p = params or MusicGenerationParams()
            p.lyrics = lyrics
            p.task_type = TaskType.TEXT2MUSIC

            result = self._handler.generate_music(
                prompt=f"A {genre} song with the following lyrics",
                duration=p.duration,
                lyrics=lyrics,
                genre=genre,
                steps=p.inference_steps,
                cfg=p.guidance_scale,
                seed=p.seed,
            )
            return self._save_result(result, p)

    # ─── 音乐续写 ───

    def continue_music(self, reference_audio: str, duration: int = 120,
                       params: Optional[MusicGenerationParams] = None) -> MusicTaskResult:
        """短片段续唱扩写"""
        self.load()
        with self._gen_lock:
            p = params or MusicGenerationParams()
            p.reference_audio = reference_audio
            p.duration = duration
            p.task_type = TaskType.COMPLETE

            result = self._handler.generate_complete(
                reference_audio=reference_audio,
                duration=duration,
                steps=p.inference_steps,
            )
            return self._save_result(result, p)

    # ─── 局部重绘 ───

    def repaint(self, audio_path: str, start_sec: float, end_sec: float,
                params: Optional[MusicGenerationParams] = None) -> MusicTaskResult:
        """局部重绘: 指定时间段重新生成"""
        self.load()
        with self._gen_lock:
            p = params or MusicGenerationParams()
            p.src_audio = audio_path
            p.repaint_start = start_sec
            p.repaint_end = end_sec
            p.task_type = TaskType.REPAINT

            result = self._handler.generate_repaint(
                src_audio=audio_path,
                start=start_sec,
                end=end_sec,
                steps=p.inference_steps,
            )
            return self._save_result(result, p)

    # ─── 翻唱生成 ───

    def cover_song(self, reference_audio: str, style_prompt: str = "",
                   params: Optional[MusicGenerationParams] = None) -> MusicTaskResult:
        """翻唱生成: 给定歌曲以新风格重新演绎"""
        self.load()
        with self._gen_lock:
            p = params or MusicGenerationParams()
            p.reference_audio = reference_audio
            p.task_type = TaskType.COVER

            result = self._handler.generate_cover(
                reference_audio=reference_audio,
                style_prompt=style_prompt,
                strength=p.audio_cover_strength,
                steps=p.inference_steps,
            )
            return self._save_result(result, p)

    # ─── 人声伴奏分离 ───

    def separate(self, audio_path: str, output_dir: Optional[str] = None) -> Tuple[str, str]:
        """人声/伴奏分离"""
        import tempfile
        with self._gen_lock:
            out_dir = output_dir or tempfile.mkdtemp()
            try:
                from acestep.third_parts.demucs import DemucsSeparator
                sep = DemucsSeparator(device=self.device)
                vocals, no_vocals = sep.separate(audio_path, out_dir)
                return vocals, no_vocals
            except ImportError:
                logger.warning("Demucs 未安装, 跳过分离")
                return "", ""

    # ─── LoRA 微调 ───

    def train_lora(self, audio_files: List[str], style_name: str,
                   output_dir: Optional[str] = None, steps: int = 500):
        """训练专属音乐风格 LoRA"""
        self.load()
        with self._gen_lock:
            out = output_dir or os.path.join(os.path.expanduser("~"), "ace_step_lora")
            os.makedirs(out, exist_ok=True)
            self._handler.train_lora(
                audio_files=audio_files,
                style_name=style_name,
                output_dir=out,
                steps=steps,
            )
            logger.info(f"✅ 音乐 LoRA 训练完成: {out}")
            return out

    # ─── 内部工具 ───

    def _save_result(self, raw_result, params: MusicGenerationParams) -> MusicTaskResult:
        """保存生成结果"""
        if isinstance(raw_result, dict):
            audios = raw_result.get("audios", [])
            audio_data = audios[0] if audios else None
            sr = raw_result.get("sample_rate", 44100)
        else:
            audio_data = raw_result
            sr = 44100

        output = params.output_path or self._temp_path()
        if audio_data is not None and isinstance(audio_data, np.ndarray):
            sf.write(output, audio_data, sr)
            duration = len(audio_data) / sr
        else:
            duration = 0

        metadata = {
            "caption": params.caption,
            "duration": duration,
            "sample_rate": sr,
            "task_type": params.task_type,
        }
        return MusicTaskResult(audio_path=output, duration=duration, metadata=metadata)

    def _temp_path(self, suffix: str = ".wav") -> str:
        import uuid
        out_dir = _get_ace_output_dir()
        os.makedirs(out_dir, exist_ok=True)
        return os.path.join(out_dir, f"ace_{uuid.uuid4().hex}{suffix}")

    def __enter__(self):
        self.load()
        return self

    def __exit__(self, *args):
        self.unload()
