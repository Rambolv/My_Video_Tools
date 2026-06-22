# -*- coding: utf-8 -*-
"""
@desc: 视频增强引擎 — 集成 Real-ESRGAN（超分辨率）和 RIFE（帧插值）
所有依赖均为可选，缺失时自动禁用对应功能并打印提示。

Real-ESRGAN: https://github.com/xinntao/Real-ESRGAN (BSD 3-Clause)
RIFE:       https://github.com/hzwer/ECCV2022-RIFE (MIT)
"""
import os
import gc
import cv2
import sys
import shutil
import time
import tempfile
import traceback
import numpy as np
from pathlib import Path
from functools import cached_property

from backend.config import config
from backend.tools.common_tools import get_readable_path
from backend.tools.hardware_accelerator import HardwareAccelerator
from backend.tools.model_compat import (
    validate_rife_config, validate_sr_config,
    BACKEND_NCNN, BACKEND_PYTHON,
)


# ═══════════════════════════════════════════════════════════════
#  1. 超分辨率 (Super-Resolution) — Real-ESRGAN 封装
# ═══════════════════════════════════════════════════════════════

_REALESRGAN_AVAILABLE = False
try:
    from realesrgan import RealESRGANer as _RealESRGANer
    from realesrgan.archs.srvgg_arch import SRVGGNetCompact
    from basicsr.archs.rrdbnet_arch import RRDBNet
    from basicsr.utils.download_util import load_file_from_url
    _REALESRGAN_AVAILABLE = True
except ImportError:
    _REALESRGAN_AVAILABLE = False


# Real-ESRGAN 模型配置
_SR_MODEL_CONFIGS = {
    "realesr-animevideov3": {
        "scale": 4,
        "arch": "srvgg",
        "num_conv": 16,
        "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-animevideov3.pth",
        "desc": "动漫视频 (4x, 轻量)"
    },
    "RealESRGAN_x4plus": {
        "scale": 4,
        "arch": "rrdb",
        "num_block": 23,
        "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
        "desc": "通用图像 (4x)"
    },
    "RealESRGAN_x2plus": {
        "scale": 2,
        "arch": "rrdb",
        "num_block": 23,
        "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth",
        "desc": "通用图像 (2x)"
    },
    "realesr-general-x4v3": {
        "scale": 4,
        "arch": "srvgg",
        "num_conv": 32,
        "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth",
        "desc": "通用图像 (4x, 轻量)"
    },
}

_SR_DEFAULT_MODEL = "realesr-animevideov3"
_SR_WEIGHTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'weights')


class VideoSuperResolution:
    """视频超分辨率引擎 — Real-ESRGAN 封装"""

    def __init__(self, model_name: str = None, tile: int = 0, scale: int = None):
        self._upsampler = None
        self._model_name = model_name or config.srModelName.value
        self._tile = tile or config.srTileSize.value
        self._scale = scale or 0
        self._device = None
        self._initialized = False

    @property
    def available(self) -> bool:
        return _REALESRGAN_AVAILABLE

    @property
    def model_name(self) -> str:
        return self._model_name

    @model_name.setter
    def model_name(self, name: str):
        self._model_name = name
        self._initialized = False

    @property
    def upscale_factor(self) -> int:
        """返回实际放大倍数"""
        cfg = _SR_MODEL_CONFIGS.get(self._model_name)
        if cfg:
            return cfg["scale"]
        return 2

    def initialize(self):
        """延迟初始化模型"""
        if self._initialized:
            return
        if not _REALESRGAN_AVAILABLE:
            raise RuntimeError("Real-ESRGAN 未安装，请执行: pip install realesrgan")

        cfg = _SR_MODEL_CONFIGS.get(self._model_name)
        if cfg is None:
            raise ValueError(f"未知的 SR 模型: {self._model_name}")

        accel = HardwareAccelerator.instance()
        device = accel.device
        self._device = device

        # 构建模型
        if cfg["arch"] == "rrdb":
            model = RRDBNet(
                num_in_ch=3, num_out_ch=3, num_feat=64,
                num_block=cfg.get("num_block", 23),
                num_grow_ch=32, scale=cfg["scale"]
            )
        else:  # srvgg
            model = SRVGGNetCompact(
                num_in_ch=3, num_out_ch=3, num_feat=64,
                num_conv=cfg.get("num_conv", 16),
                upscale=cfg["scale"], act_type='prelu'
            )

        netscale = cfg["scale"]

        # 下载 / 加载权重
        model_path = os.path.join(_SR_WEIGHTS_DIR, self._model_name + ".pth")
        if not os.path.isfile(model_path):
            os.makedirs(_SR_WEIGHTS_DIR, exist_ok=True)
            print(f"[SR] 下载模型 {self._model_name}...")
            model_path = load_file_from_url(
                url=cfg["url"],
                model_dir=_SR_WEIGHTS_DIR,
                progress=True,
                file_name=self._model_name + ".pth"
            )

        half = accel.has_cuda() and config.srUseHalf.value
        # 并发任务同时加载同一模型时可能争抢文件，加重试
        max_retries = 5
        for attempt in range(max_retries):
            try:
                self._upsampler = _RealESRGANer(
                    scale=netscale,
                    model_path=model_path,
                    model=model,
                    tile=self._tile,
                    tile_pad=10,
                    pre_pad=0,
                    half=half,
                    device=device,
                )
                break
            except PermissionError as e:
                if attempt < max_retries - 1:
                    import time
                    time.sleep(2 ** attempt)  # 1, 2, 4, 8 秒退避
                else:
                    raise e
        self._initialized = True
        print(f"[SR] {self._model_name} 初始化完成 (device={device})")

    def enhance_frame(self, frame: np.ndarray) -> np.ndarray:
        """增强单帧图像"""
        if not self._initialized:
            self.initialize()
        output, _ = self._upsampler.enhance(frame, outscale=self._scale if self._scale > 0 else None)
        return output

    def enhance_video(
        self,
        input_path: str,
        output_path: str,
        fps: float,
        width: int,
        height: int,
        log_callback=None,
        progress_callback=None,
        audio_source: str = None,
    ) -> str:
        """增强整个视频 — FFmpeg 管道 + 多线程流水线

        采用 3 阶段流水线架构，使解码、GPU 推理、编码并行重叠：
          Reader 线程: FFmpeg → 原始帧队列
          Main  线程: 原始帧 → GPU 超分 → 增强帧队列
          Writer 线程: 增强帧队列 → FFmpeg 编码

        此架构消除了 cv2.VideoCapture/VideoWriter 的串行 I/O 瓶颈，
        GPU 利用率保持持续高位，不再出现忽高忽低。
        """
        if not self._initialized:
            self.initialize()

        import subprocess
        import threading
        import queue as queue_module
        from backend.tools.ffmpeg_cli import FFmpegCLI

        _log = log_callback or (lambda msg: print(f"[SR] {msg}"))
        _prog = progress_callback or (lambda p, f: None)

        out_w = width * self.upscale_factor
        out_h = height * self.upscale_factor
        ff = FFmpegCLI.instance().ffmpeg_path

        # ── 获取总帧数 ──
        cap_probe = cv2.VideoCapture(get_readable_path(input_path))
        total_frames = int(cap_probe.get(cv2.CAP_PROP_FRAME_COUNT))
        cap_probe.release()
        if total_frames <= 0:
            total_frames = 99999  # fallback

        _log(f"SR 流水线启动: {width}x{height} → {out_w}x{out_h}, {total_frames} 帧, {fps}fps")

        # ── 帧尺寸 ──
        frame_size_in = width * height * 3      # RGB24
        frame_size_out = out_w * out_h * 3       # RGB24

        # ── FFmpeg 解码进程 (→ stdout pipe) ──
        decode_cmd = [
            ff, "-y",
            "-i", get_readable_path(input_path),
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-vcodec", "rawvideo",
            "-an", "-sn",           # 跳过音频和字幕
            "-loglevel", "error",
            "-"
        ]
        decoder = subprocess.Popen(
            decode_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )

        # ── FFmpeg 编码进程 (← stdin pipe) ──
        temp_video = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
        temp_path = temp_video.name
        temp_video.close()
        encode_cmd = [
            ff, "-y",
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-s", f"{out_w}x{out_h}",
            "-r", str(fps),
            "-i", "-",
            "-vcodec", "libx264",
            "-crf", "18",
            "-preset", "fast",      # 优先速度（GPU 繁忙时 CPU 编码也快）
            "-pix_fmt", "yuv420p",
            "-loglevel", "error",
            temp_path,
        ]
        encoder = subprocess.Popen(
            encode_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # ── 队列（限制容量避免内存爆炸）──
        Q_SIZE = max(8, min(32, total_frames // 10))  # 自适应队列深度
        frame_queue = queue_module.Queue(maxsize=Q_SIZE)
        result_queue = queue_module.Queue(maxsize=Q_SIZE)
        stop_sentinel = object()
        error_holder = {"error": None}

        # ═════════════════════════════════════════════════════════
        #  Reader 线程: FFmpeg stdout → 原始帧队列
        # ═════════════════════════════════════════════════════════
        def reader_worker():
            try:
                idx = 0
                while True:
                    raw = decoder.stdout.read(frame_size_in)
                    if not raw or len(raw) < frame_size_in:
                        break
                    frame = np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 3)).copy()
                    frame_queue.put((idx, frame), timeout=30)
                    idx += 1
            except Exception as e:
                error_holder["error"] = e
            finally:
                # 发送总数个哨兵，让所有后续阶段知道结束
                frame_queue.put((-1, stop_sentinel))

        reader_thread = threading.Thread(target=reader_worker, daemon=True, name="SR-Reader")
        reader_thread.start()

        # ═════════════════════════════════════════════════════════
        #  Writer 线程: 增强帧队列 → FFmpeg stdin
        # ═════════════════════════════════════════════════════════
        def writer_worker():
            try:
                while True:
                    item = result_queue.get(timeout=30)
                    if item is stop_sentinel:
                        break
                    _, enhanced = item
                    encoder.stdin.write(enhanced.tobytes())
            except Exception as e:
                error_holder["error"] = e
            finally:
                try:
                    encoder.stdin.close()
                except Exception:
                    pass

        writer_thread = threading.Thread(target=writer_worker, daemon=True, name="SR-Writer")
        writer_thread.start()

        # ═════════════════════════════════════════════════════════
        #  Main 线程: 原始帧 → GPU 超分 → 增强帧队列
        # ═════════════════════════════════════════════════════════
        processed = 0
        try:
            while True:
                item = frame_queue.get(timeout=60)
                idx, frame = item
                if frame is stop_sentinel:
                    break

                enhanced = self.enhance_frame(frame)
                result_queue.put((idx, enhanced))
                processed += 1

                if processed % 10 == 0 or processed == 1:
                    pct = int(processed / max(total_frames, 1) * 100)
                    _prog(min(pct, 99), False)
                    q_sz = frame_queue.qsize()
                    r_sz = result_queue.qsize()
                    _log(f"  SR {processed}/{total_frames} ({pct}%) [队列: 入{q_sz} 出{r_sz}]")

            # 发送完成哨兵给 writer
            result_queue.put(stop_sentinel)

            # 等待 writer 线程完成
            writer_thread.join(timeout=120)
            if writer_thread.is_alive():
                _log("  等待编码进程完成…")
            writer_thread.join(timeout=300)

            # 等待 FFmpeg 进程完成
            encoder.wait(timeout=120)
            decoder.wait(timeout=30)

            if error_holder["error"]:
                raise error_holder["error"]

            _prog(100, False)
            _log(f"SR 完成，共处理 {processed} 帧")

            # ── 用 FFmpeg 合并音轨 ──
            final_temp = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
            final_temp_path = final_temp.name
            final_temp.close()
            _audio_src = audio_source if audio_source else input_path
            _audio_src = _audio_src if os.path.exists(_audio_src) else None
            if _audio_src:
                try:
                    merge_cmd = [
                        ff, "-y",
                        "-i", temp_path,
                        "-i", get_readable_path(_audio_src),
                        "-vcodec", "copy",
                        "-acodec", "copy",
                        "-map", "0:v:0", "-map", "1:a:0?",
                        "-loglevel", "error",
                        final_temp_path,
                    ]
                    subprocess.check_output(merge_cmd, stdin=open(os.devnull), shell=False)
                except Exception:
                    _audio_src = None
            if not _audio_src:
                # 无音轨或合并失败 → 直接复制无声视频
                shutil.copy2(temp_path, final_temp_path)
            # atomic rename
            if os.path.exists(final_temp_path):
                shutil.move(final_temp_path, output_path)

        except Exception:
            # 错误时清理
            try:
                # 向队列注入哨兵以释放阻塞的线程
                while not frame_queue.empty():
                    try:
                        frame_queue.get_nowait()
                    except queue_module.Empty:
                        break
                frame_queue.put((-1, stop_sentinel))
                result_queue.put(stop_sentinel)
            except Exception:
                pass
            raise
        finally:
            # 确保子进程终止
            for proc in [decoder, encoder]:
                try:
                    if proc.poll() is None:
                        proc.kill()
                        proc.wait(timeout=5)
                except Exception:
                    pass
            # 清理临时文件
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except Exception:
                pass
            try:
                if 'final_temp_path' in dir() and os.path.exists(final_temp_path):
                    if final_temp_path != output_path:
                        os.unlink(final_temp_path)
            except Exception:
                pass

        return output_path


# ═══════════════════════════════════════════════════════════════
#  2. 帧插值 (Frame Interpolation) — RIFE 封装
# ═══════════════════════════════════════════════════════════════

# RIFE 模型权重 Google Drive ID（flownet.pkl 约 30MB）
_RIFE_GD_ID = "1APIzVeI-4ZZCEuIRE1m6WYfSCaOsi_7_"

# 模型权重所在目录
_RIFE_MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'models', 'rife')


def _auto_setup_rife():
    """自动下载并设置 RIFE 模型（首次使用时调用）
    优先从国内可访问的 HuggingFace 镜像下载，
    失败时回退到 Google Drive。
    """
    os.makedirs(_RIFE_MODEL_DIR, exist_ok=True)
    pkl_path = os.path.join(_RIFE_MODEL_DIR, 'flownet.pkl')

    if os.path.exists(pkl_path):
        size_mb = os.path.getsize(pkl_path) / (1024 * 1024)
        if size_mb >= 5:
            return True

    print("[RIFE] 正在下载预训练模型权重 (~24MB)...")

    # 源列表：优先国内可访问，依次尝试
    _download_urls = [
        # 1. HuggingFace 国内镜像 (hf-mirror.com)
        "https://hf-mirror.com/gpanaretou/practical-rife-interpolation/resolve/main/train_log/flownet.pkl",
        # 2. HuggingFace 官方
        "https://huggingface.co/gpanaretou/practical-rife-interpolation/resolve/main/train_log/flownet.pkl",
        # 3. Google Drive (原始来源)
        f"https://drive.google.com/uc?id={_RIFE_GD_ID}",
    ]

    downloaded = False
    for url in _download_urls:
        try:
            print(f"  尝试: {url[:60]}...")
            import requests
            r = requests.get(url, timeout=120, stream=True)
            if r.status_code != 200:
                print(f"  -> HTTP {r.status_code}, 跳过")
                continue
            total = int(r.headers.get('content-length', 0))
            with open(pkl_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            actual_mb = os.path.getsize(pkl_path) / (1024 * 1024)
            if actual_mb >= 5:
                print(f"  ✅ 下载成功! {actual_mb:.1f} MB")
                downloaded = True
                break
            else:
                print(f"  ⚠️ 文件过小 ({actual_mb:.1f}MB)，尝试下一个源")
                os.unlink(pkl_path)
        except Exception as e:
            print(f"  -> 失败: {type(e).__name__}")
            try:
                os.unlink(pkl_path)
            except Exception:
                pass

    if not downloaded:
        print("[RIFE] 自动下载失败，请手动下载模型放入: " + _RIFE_MODEL_DIR)
        print("[RIFE] 下载地址: https://hf-mirror.com/gpanaretou/practical-rife-interpolation")
        return False
    return True


_RIFE_SETUP_DONE = False
_RIFE_SETUP_OK = False


def _ensure_rife():
    """确保 RIFE 可用，导入内置模块"""
    global _RIFE_SETUP_DONE, _RIFE_SETUP_OK
    if _RIFE_SETUP_DONE:
        return _RIFE_SETUP_OK
    _RIFE_SETUP_DONE = True

    # 添加 RIFE 模块到 sys.path
    _rife_root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'rife')
    if _rife_root not in sys.path:
        sys.path.insert(0, os.path.dirname(_rife_root))  # 使 from rife.RIFE_HDv3 import Model 可用
        sys.path.insert(0, _rife_root)                    # 使 from RIFE_HDv3 import Model 可用

    try:
        from rife.RIFE_HDv3 import Model as _RifeModel
        global _RifeModelClass
        _RifeModelClass = _RifeModel
        # 自动下载模型
        _auto_setup_rife()
        _RIFE_SETUP_OK = True
        return True
    except ImportError as e:
        print(f"[RIFE] 内置模块导入失败: {e}")
        _RIFE_SETUP_OK = False
        return False


_RifeModelClass = None


class VideoFrameInterpolation:
    """视频帧插值引擎 — RIFE 封装"""

    def __init__(self, model_dir: str = None, multiplier: int = 2):
        self._model = None
        self._model_dir = model_dir or config.fiModelDir.value or _RIFE_MODEL_DIR
        self._multiplier = multiplier or config.fiMultiplier.value
        self._initialized = False
        self._device = None

    @property
    def available(self) -> bool:
        return _ensure_rife()

    @property
    def multiplier(self) -> int:
        return self._multiplier

    @multiplier.setter
    def multiplier(self, value: int):
        self._multiplier = value

    def initialize(self):
        """延迟初始化 RIFE 模型"""
        if self._initialized:
            return
        if not _ensure_rife():
            raise RuntimeError(
                "RIFE 模块不可用。请尝试以下方法:\n"
                "1. 检查网络后重新启动程序，自动下载\n"
                "2. 手动下载模型放入: " + _RIFE_MODEL_DIR + "\n"
                "   下载地址: https://drive.google.com/file/d/" + _RIFE_GD_ID
            )

        # 确保模型权重存在
        _auto_setup_rife()

        accel = HardwareAccelerator.instance()
        self._device = accel.device
        self._model = _RifeModelClass()
        self._model.load_model(self._model_dir, -1)
        self._model.eval()
        self._model.device()
        self._initialized = True
        print(f"[FI] RIFE 初始化完成 (multiplier={self._multiplier}x, device={self._device})")

    def interpolate_batch(self, frame1: np.ndarray, frame2: np.ndarray, timesteps: int = 1):
        """在 frame1 和 frame2 之间生成插值帧"""
        if not self._initialized:
            self.initialize()
        if not _ensure_rife():
            return []

        import torch
        h, w = frame1.shape[:2]
        # 确保尺寸是 32 的倍数
        pad_h = (32 - h % 32) % 32
        pad_w = (32 - w % 32) % 32
        if pad_h > 0 or pad_w > 0:
            frame1 = cv2.copyMakeBorder(frame1, 0, pad_h, 0, pad_w, cv2.BORDER_REFLECT)
            frame2 = cv2.copyMakeBorder(frame2, 0, pad_h, 0, pad_w, cv2.BORDER_REFLECT)

        i1 = torch.from_numpy(frame1.transpose(2, 0, 1)).float().unsqueeze(0).to(self._device) / 255.0
        i2 = torch.from_numpy(frame2.transpose(2, 0, 1)).float().unsqueeze(0).to(self._device) / 255.0

        results = []
        with torch.no_grad():
            if timesteps == 1:
                mid = self._model.inference(i1, i2, timestep=0.5, scale=1.0)
                mid = mid.squeeze(0).cpu().numpy().transpose(1, 2, 0)
                mid = np.clip(mid * 255, 0, 255).astype(np.uint8)
                if pad_h > 0 or pad_w > 0:
                    mid = mid[:h, :w]
                results.append(mid)
            else:
                for step in range(1, timesteps + 1):
                    t = step / (timesteps + 1)
                    mid = self._model.inference(i1, i2, timestep=t)
                    mid = mid.squeeze(0).cpu().numpy().transpose(1, 2, 0)
                    mid = np.clip(mid * 255, 0, 255).astype(np.uint8)
                    if pad_h > 0 or pad_w > 0:
                        mid = mid[:h, :w]
                    results.append(mid)

        return results

    def interpolate_video(
        self,
        input_path: str,
        output_path: str,
        orig_fps: float,
        log_callback=None,
        progress_callback=None,
        audio_source: str = None,
    ) -> str:
        """对整个视频做帧插值 — FFmpeg 管道 + 多线程流水线

        与超分一样采用 3 阶段流水线：解码→插值→编码并行重叠，
        消除 cv2.VideoCapture/VideoWriter 的串行 I/O 瓶颈。
        """
        if not self._initialized:
            self.initialize()

        import subprocess
        import threading
        import queue as queue_module
        from backend.tools.ffmpeg_cli import FFmpegCLI

        _log = log_callback or (lambda msg: print(f"[FI] {msg}"))
        _prog = progress_callback or (lambda p, f: None)

        target_fps = orig_fps * self._multiplier
        timesteps = self._multiplier - 1

        # ── 探测尺寸 ──
        cap_probe = cv2.VideoCapture(get_readable_path(input_path))
        if not cap_probe.isOpened():
            raise IOError(f"无法打开视频: {input_path}")
        total_frames = int(cap_probe.get(cv2.CAP_PROP_FRAME_COUNT))
        w = int(cap_probe.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap_probe.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap_probe.release()
        if total_frames <= 0:
            total_frames = 99999

        ff = FFmpegCLI.instance().ffmpeg_path
        frame_size = w * h * 3

        _log(f"FI 流水线启动: {w}x{h}, {total_frames} 帧, {orig_fps}fps → {target_fps}fps")

        # ── FFmpeg 解码进程 (→ stdout) ──
        decode_cmd = [
            ff, "-y",
            "-i", get_readable_path(input_path),
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-vcodec", "rawvideo",
            "-an", "-sn",
            "-loglevel", "error",
            "-"
        ]
        decoder = subprocess.Popen(
            decode_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )

        # ── FFmpeg 编码进程 (← stdin) ──
        temp_video = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
        temp_path = temp_video.name
        temp_video.close()
        encode_cmd = [
            ff, "-y",
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-s", f"{w}x{h}",
            "-r", str(target_fps),
            "-i", "-",
            "-vcodec", "libx264",
            "-crf", "18",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-loglevel", "error",
            temp_path,
        ]
        encoder = subprocess.Popen(
            encode_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # ── 队列 ──
        Q_SIZE = max(8, min(32, total_frames * self._multiplier // 10))
        frame_queue = queue_module.Queue(maxsize=Q_SIZE)
        result_queue = queue_module.Queue(maxsize=Q_SIZE)
        stop_sentinel = object()
        error_holder = {"error": None}

        # ═════════════════════════════════════════════════════════
        #  Reader 线程: FFmpeg stdout → 原始帧队列
        # ═════════════════════════════════════════════════════════
        def reader_worker():
            try:
                idx = 0
                while True:
                    raw = decoder.stdout.read(frame_size)
                    if not raw or len(raw) < frame_size:
                        break
                    frame = np.frombuffer(raw, dtype=np.uint8).reshape((h, w, 3)).copy()
                    frame_queue.put((idx, frame), timeout=30)
                    idx += 1
            except Exception as e:
                error_holder["error"] = e
            finally:
                frame_queue.put((-1, stop_sentinel))

        reader_thread = threading.Thread(target=reader_worker, daemon=True, name="FI-Reader")
        reader_thread.start()

        # ═════════════════════════════════════════════════════════
        #  Writer 线程: 增强帧队列 → FFmpeg stdin
        # ═════════════════════════════════════════════════════════
        def writer_worker():
            try:
                while True:
                    item = result_queue.get(timeout=30)
                    if item is stop_sentinel:
                        break
                    encoder.stdin.write(item.tobytes())
            except Exception as e:
                error_holder["error"] = e
            finally:
                try:
                    encoder.stdin.close()
                except Exception:
                    pass

        writer_thread = threading.Thread(target=writer_worker, daemon=True, name="FI-Writer")
        writer_thread.start()

        # ═════════════════════════════════════════════════════════
        #  Main 线程: 帧对 → GPU 插值 → 增强帧队列
        # ═════════════════════════════════════════════════════════
        processed_pairs = 0
        try:
            # 读取首帧
            item0 = frame_queue.get(timeout=60)
            _, prev_frame = item0
            if prev_frame is stop_sentinel:
                raise IOError("视频无帧可处理")
            result_queue.put(prev_frame)  # 首帧直接写出
            processed_pairs += 1

            while True:
                item = frame_queue.get(timeout=60)
                _, curr_frame = item
                if curr_frame is stop_sentinel:
                    break

                # GPU 插值（这是耗时步骤）
                mid_frames = self.interpolate_batch(prev_frame, curr_frame, timesteps)
                for mf in mid_frames:
                    result_queue.put(mf)
                result_queue.put(curr_frame)

                prev_frame = curr_frame
                processed_pairs += 1

                if processed_pairs % 10 == 0 or processed_pairs <= 2:
                    out_total = total_frames * self._multiplier
                    pct = int((processed_pairs) / max(total_frames, 1) * 100)
                    _prog(min(pct, 99), False)
                    q_sz = frame_queue.qsize()
                    r_sz = result_queue.qsize()
                    _log(f"  FI {processed_pairs}/{total_frames} ({pct}%) [队列: 入{q_sz} 出{r_sz}]")

            result_queue.put(stop_sentinel)

            # 等待 writer 完成
            writer_thread.join(timeout=120)
            encoder.wait(timeout=120)
            decoder.wait(timeout=30)

            if error_holder["error"]:
                raise error_holder["error"]

            _prog(100, False)
            _log(f"FI 完成: {orig_fps}fps → {target_fps}fps")

            # ── 合并音轨 ──
            final_temp = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
            final_temp_path = final_temp.name
            final_temp.close()

            def _build_atempo(t):
                if t >= 0.5:
                    return f"atempo={t}"
                filters = []
                while t < 0.5:
                    filters.append("atempo=0.5")
                    t *= 2
                if abs(t - 1.0) > 0.001:
                    filters.append(f"atempo={t}")
                return ",".join(filters)

            tempo = 1.0 / self._multiplier
            tempo_filter = _build_atempo(tempo)
            _audio_src = audio_source if audio_source else input_path
            merge_cmd = [
                ff, "-y", "-i", temp_path, "-i", get_readable_path(_audio_src),
                "-vcodec", "copy",
                "-map", "0:v:0",
                "-filter_complex", f"[1:a]{tempo_filter}[a]",
                "-map", "[a]",
                "-loglevel", "error",
                final_temp_path,
            ]
            try:
                subprocess.check_output(merge_cmd, stdin=open(os.devnull),
                                        stderr=subprocess.DEVNULL, shell=False)
            except Exception:
                no_audio_cmd = [
                    ff, "-y", "-i", temp_path,
                    "-vcodec", "copy",
                    "-loglevel", "error", final_temp_path,
                ]
                subprocess.check_output(no_audio_cmd, stdin=open(os.devnull), shell=False)
                _log("  (源视频无音轨，输出无音频)")

            if os.path.exists(final_temp_path):
                shutil.move(final_temp_path, output_path)

        except Exception:
            try:
                while not frame_queue.empty():
                    try:
                        frame_queue.get_nowait()
                    except queue_module.Empty:
                        break
                frame_queue.put((-1, stop_sentinel))
                result_queue.put(stop_sentinel)
            except Exception:
                pass
            raise
        finally:
            for proc in [decoder, encoder]:
                try:
                    if proc.poll() is None:
                        proc.kill()
                        proc.wait(timeout=5)
                except Exception:
                    pass
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except Exception:
                pass
            try:
                if 'final_temp_path' in dir() and os.path.exists(final_temp_path):
                    if final_temp_path != output_path:
                        os.unlink(final_temp_path)
            except Exception:
                pass

        return output_path


# ═══════════════════════════════════════════════════════════════
#  3. 综合增强管线
# ═══════════════════════════════════════════════════════════════

def enhance_video_pipeline(
    input_path: str,
    output_path: str,
    enable_sr: bool = None,
    enable_fi: bool = None,
    log_callback=None,
    progress_callback=None,
) -> str:
    """
    综合视频增强管线：超分辨率 → 帧插值

    Args:
        input_path: 输入视频路径
        output_path: 输出视频路径
        enable_sr: 是否启用超分辨率 (None = 使用配置)
        enable_fi: 是否启用帧插值 (None = 使用配置)
        log_callback: 日志回调
        progress_callback: 进度回调 (percent, isFinished)

    Returns:
        最终输出路径
    """
    _log = log_callback or (lambda msg: print(f"[Enhance] {msg}"))
    _prog = progress_callback or (lambda p, f: None)

    enable_sr = config.enableSuperResolution.value if enable_sr is None else enable_sr
    enable_fi = config.enableFrameInterpolation.value if enable_fi is None else enable_fi

    if not enable_sr and not enable_fi:
        _log("视频增强未启用，跳过")
        import shutil
        shutil.copy2(input_path, output_path)
        return output_path

    current_input = input_path
    audio_source = input_path  # 始终指向有音轨的原始输入
    temp_files = []
    sr_first = config.enhanceSrFirst.value
    _out_dir = os.path.dirname(os.path.abspath(output_path))

    # =========================================================
    # 内部函数：超分辨率处理步骤
    # =========================================================
    def _run_sr_step():
        nonlocal current_input
        sr_path = output_path + ".sr_tmp.mp4"
        temp_files.append(sr_path)
        _log("=" * 50)
        _log(f"步骤 {'1/2' if (enable_sr and enable_fi) else '1/1'}: 超分辨率处理…")
        model_name = config.srModelName.value
        if model_name.startswith("waifu2x-"):
            _log("  算法: waifu2x-ncnn-vulkan (Vulkan)")
            from .waifu2x_ncnn_backend import is_available as w2x_avail
            from .waifu2x_ncnn_backend import enhance_video_waifu2x
            if w2x_avail():
                w2x_arch = model_name.replace("waifu2x-", "")
                enhance_video_waifu2x(current_input, sr_path, scale=2, model_arch=w2x_arch,
                    log_cb=_log, prog_cb=lambda p, f: _prog(int(p * (50 if (enable_sr and enable_fi) else 100) / 100), f))
                current_input = sr_path
                _log("超分辨率完成 (waifu2x)")
            else:
                _log("⚠️ waifu2x-ncnn-vulkan 不可用")
        else:
            backend = config.srBackend.value
            _sr_ok, _sr_msg, _sr_corrected = validate_sr_config(model_name, backend)
            if not _sr_ok:
                _log(f"  {_sr_msg}")
                backend = _sr_corrected
                config.set(config.srBackend, _sr_corrected, save=False)
            if backend == "ncnn":
                _log("  后端: realesrgan-ncnn-vulkan (Vulkan)")
                from .sr_ncnn_backend import is_available as sr_ncnn_avail
                from .sr_ncnn_backend import enhance_video_ncnn
                if sr_ncnn_avail():
                    enhance_video_ncnn(current_input, sr_path,
                        log_cb=_log, prog_cb=lambda p, f: _prog(int(p * (50 if (enable_sr and enable_fi) else 100) / 100), f))
                    current_input = sr_path
                    _log("超分辨率完成 (ncnn)")
                else:
                    _log("⚠️ realesrgan-ncnn-vulkan 不可用，回退到 Python")
            if current_input != sr_path:
                _log("  后端: Python CUDA")
                sr = VideoSuperResolution()
                if not sr.available:
                    _log("⚠️ Real-ESRGAN 未安装，超分功能不可用")
                else:
                    cap_tmp = cv2.VideoCapture(get_readable_path(current_input))
                    fps = cap_tmp.get(cv2.CAP_PROP_FPS)
                    w = int(cap_tmp.get(cv2.CAP_PROP_FRAME_WIDTH))
                    h = int(cap_tmp.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    cap_tmp.release()
                    sr.enhance_video(current_input, sr_path, fps, w, h,
                        log_callback=_log, progress_callback=lambda p, f: _prog(int(p * (50 if (enable_sr and enable_fi) else 100) / 100), f),
                        audio_source=audio_source)
                    current_input = sr_path
                    _log("超分辨率完成")

    # =========================================================
    # 内部函数：帧插值处理步骤
    # =========================================================
    def _run_fi_step():
        nonlocal current_input
        fi_path = output_path + ".fi_tmp.mp4"
        temp_files.append(fi_path)
        _log("=" * 50)
        _log(f"步骤 {'2/2' if (enable_sr and enable_fi) else '1/1'}: 帧插值处理…")
        cap_tmp2 = cv2.VideoCapture(get_readable_path(current_input))
        fps2 = cap_tmp2.get(cv2.CAP_PROP_FPS)
        cap_tmp2.release()
        backend = config.fiBackend.value
        _fi_model = config.fiModelName.value
        _fi_ok, _fi_msg, _fi_corrected = validate_rife_config(_fi_model, backend)
        if not _fi_ok:
            _log(f"  {_fi_msg}")
            backend = _fi_corrected
            config.set(config.fiBackend, _fi_corrected, save=False)
        if backend == "ncnn":
            _log("  后端: rife-ncnn-vulkan (Vulkan)")
            from .rife_ncnn_backend import is_available as ncnn_avail
            from .rife_ncnn_backend import interpolate_video_ncnn
            if ncnn_avail():
                interpolate_video_ncnn(current_input, fi_path,
                    multiplier=config.fiMultiplier.value, model_name=config.fiModelName.value,
                    log_callback=_log, progress_callback=lambda p, f: _prog(
                        50 + int(p * (50 if (enable_sr and enable_fi) else 100) / 100) if enable_sr else int(p * 100 / 100), f))
                current_input = fi_path
                _log("帧插值完成 (ncnn)")
                return
            else:
                _log("⚠️ rife-ncnn-vulkan 不可用，回退到 Python CUDA")
        _log("  后端: Python CUDA")
        fi = VideoFrameInterpolation(multiplier=config.fiMultiplier.value)
        if not fi.available:
            _log("⚠️ RIFE 未安装，帧插值功能不可用")
        else:
            fi.interpolate_video(current_input, fi_path, fps2,
                log_callback=_log, progress_callback=lambda p, f: _prog(
                    50 + int(p * (50 if (enable_sr and enable_fi) else 100) / 100) if enable_sr else int(p * 100 / 100), f),
                audio_source=audio_source)
            current_input = fi_path
            _log("帧插值完成")

    # =========================================================
    # 按设定的顺序执行
    # =========================================================
    try:
        if sr_first:
            if enable_sr: _run_sr_step()
            if enable_fi: _run_fi_step()
        else:
            if enable_fi: _run_fi_step()
            if enable_sr: _run_sr_step()
        if current_input != output_path:
            import shutil
            shutil.copy2(current_input, output_path)
        _log(f"视频增强完成: {output_path}")
        _prog(100, True)
    except Exception:
        traceback.print_exc()
        _log(f"❌ 视频增强失败")
        raise
    finally:
        # 清理已知中间文件
        for tf in temp_files:
            try:
                if os.path.exists(tf):
                    os.unlink(tf)
            except Exception:
                pass
        # 清理遗留中间产物 (fi_tmp / sr_tmp / 无扩展名残留)
        try:
            import glob as _g
            _patterns = [
                os.path.join(_out_dir, "*.fi_tmp.mp4"),
                os.path.join(_out_dir, "*.sr_tmp.mp4"),
                os.path.join(_out_dir, "*_VSR"),        # 无扩展名残留
                os.path.join(_out_dir, "*_VSR.tmp*"),   # 临时文件
            ]
            for _pat in _patterns:
                for _f in _g.glob(_pat):
                    try:
                        os.unlink(_f)
                    except Exception:
                        pass
        except Exception:
            pass
    return output_path


# ═══════════════════════════════════════════════════════════════
#  工具：检查依赖
# ═══════════════════════════════════════════════════════════════

def check_enhancement_availability() -> dict:
    """返回各增强功能的可用状态"""
    return {
        "super_resolution": {
            "available": _REALESRGAN_AVAILABLE,
            "models": list(_SR_MODEL_CONFIGS.keys()),
            "install": "pip install realesrgan",
        },
        "frame_interpolation": {
            "available": _RIFE_AVAILABLE,
            "install": "参考 https://github.com/hzwer/ECCV2022-RIFE",
        },
    }
