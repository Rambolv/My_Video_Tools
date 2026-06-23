# -*- coding: utf-8 -*-
"""
@desc: RIFE-NCNN-Vulkan 后端 — 调用 rife-ncnn-vulkan.exe 实现硬件加速帧插值
比 Python CUDA 版本快 2-5 倍，模型从 GitHub 仓库直接下载（非 release assets）。
"""
import os
import cv2
import sys
import glob
import time
import shutil
import tempfile
import subprocess
import numpy as np

from backend.config import config
from backend.tools.common_tools import natsorted

_NCNN_DIR = os.path.dirname(os.path.abspath(__file__))  # tools/
_NCNN_EXE = os.path.join(_NCNN_DIR, "rife_ncnn", "rife-ncnn-vulkan.exe")
_NCNN_DLL = os.path.join(_NCNN_DIR, "rife_ncnn", "vcomp140.dll")

# 默认模型将下载到此目录
_NCNN_MODELS_DIR = os.path.join(_NCNN_DIR, "rife_ncnn", "models")

# 模型文件直接从 GitHub 仓库 raw 下载（非 LFS，常规文件）
# 格式: {model_name: [(相对路径, 文件名), ...]}
_NCNN_MODEL_FILES = {
    "rife-v3.1": [
        ("models/rife-v3.1", "contextnet.bin"), ("models/rife-v3.1", "contextnet.param"),
        ("models/rife-v3.1", "flownet.bin"),    ("models/rife-v3.1", "flownet.param"),
        ("models/rife-v3.1", "fusionnet.bin"),  ("models/rife-v3.1", "fusionnet.param"),
    ],
    "rife-v3.0": [
        ("models/rife-v3.0", "contextnet.bin"), ("models/rife-v3.0", "contextnet.param"),
        ("models/rife-v3.0", "flownet.bin"),    ("models/rife-v3.0", "flownet.param"),
        ("models/rife-v3.0", "fusionnet.bin"),  ("models/rife-v3.0", "fusionnet.param"),
    ],
    "rife-v2.4": [
        ("models/rife-v2.4", "contextnet.bin"), ("models/rife-v2.4", "contextnet.param"),
        ("models/rife-v2.4", "flownet.bin"),    ("models/rife-v2.4", "flownet.param"),
        ("models/rife-v2.4", "fusionnet.bin"),  ("models/rife-v2.4", "fusionnet.param"),
    ],
    "rife-anime": [
        ("models/rife-anime", "contextnet.bin"), ("models/rife-anime", "contextnet.param"),
        ("models/rife-anime", "flownet.bin"),    ("models/rife-anime", "flownet.param"),
        ("models/rife-anime", "fusionnet.bin"),  ("models/rife-anime", "fusionnet.param"),
    ],
    "rife-v4.6": [
        ("models/rife-v4.6", "flownet.bin"),
        ("models/rife-v4.6", "flownet.param"),
    ],
}

# GitHub raw 基础 URL（含镜像）
_RAW_BASE_URLS = [
    "https://raw.githubusercontent.com/nihui/rife-ncnn-vulkan/master",
    "https://ghfast.top/https://raw.githubusercontent.com/nihui/rife-ncnn-vulkan/master",
    "https://ghproxy.com/https://raw.githubusercontent.com/nihui/rife-ncnn-vulkan/master",
    "https://mirror.ghproxy.com/https://raw.githubusercontent.com/nihui/rife-ncnn-vulkan/master",
]


def _try_download(url: str, dest: str, timeout: int = 120) -> bool:
    """下载单个文件，验证不是 HTML 错误页"""
    try:
        import requests
        r = requests.get(url, timeout=timeout, stream=True)
        r.raise_for_status()
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in r.iter_content(8192):
                if chunk:
                    f.write(chunk)
        # 验证不是 HTML
        sz = os.path.getsize(dest)
        if sz < 256:
            os.unlink(dest)
            return False
        with open(dest, "rb") as f:
            if b"<!DOCTYPE" in f.read(256):
                os.unlink(dest)
                return False
        return True
    except Exception:
        if os.path.exists(dest):
            try:
                os.unlink(dest)
            except Exception:
                pass
        return False


def is_available() -> bool:
    """检查 rife-ncnn-vulkan 是否可用"""
    return os.path.exists(_NCNN_EXE) and os.path.exists(_NCNN_DLL)


def _ncnn_threads() -> str:
    """获取 ncnn 线程参数 (load:proc:save)，可用户配置"""
    try:
        val = config.fiNcnnThreads.value
        if val and ":" in val:
            return val
    except Exception:
        pass
    return "1:2:2"


def _ensure_model(model_name: str) -> str:
    """确保指定模型已下载，返回模型路径"""
    model_dir = os.path.join(_NCNN_MODELS_DIR, model_name)
    if os.path.isdir(model_dir) and glob.glob(os.path.join(model_dir, "*.bin")):
        return model_dir

    # 获取模型文件列表
    model_files = _NCNN_MODEL_FILES.get(model_name)
    if not model_files:
        raise FileNotFoundError(f"未知的 ncnn 模型: {model_name}，可用: {list(_NCNN_MODEL_FILES.keys())}")

    print(f"[RIFE-NCNN] 下载模型 {model_name}...")
    os.makedirs(model_dir, exist_ok=True)

    success = True
    for rel_dir, fname in model_files:
        dest = os.path.join(model_dir, fname)
        if os.path.exists(dest) and os.path.getsize(dest) > 1024:
            continue  # 已存在

        downloaded = False
        for base_url in _RAW_BASE_URLS:
            url = f"{base_url}/{rel_dir}/{fname}"
            if _try_download(url, dest):
                downloaded = True
                break

        if not downloaded:
            print(f"[RIFE-NCNN] ❌ 无法下载 {fname}")
            success = False

    if success and glob.glob(os.path.join(model_dir, "*.bin")):
        sz = sum(os.path.getsize(os.path.join(model_dir, f)) for f in os.listdir(model_dir) if f.endswith('.bin'))
        print(f"[RIFE-NCNN] ✅ 模型 {model_name} 就绪 ({sz // 1048576} MB)")
        return model_dir

    # 部分成功也可用
    if glob.glob(os.path.join(model_dir, "*.bin")):
        return model_dir

    raise FileNotFoundError(f"模型 {model_name} 下载失败，请检查网络或使用 Python 后端")


def _extract_frames(video_path: str, out_dir: str, log_cb=None) -> float:
    """用 FFmpeg 直接提取视频所有帧到目录（比 cv2 循环快 3-5 倍）"""
    _log = log_cb or (lambda m: None)
    import subprocess as _sp
    import glob as _glob
    from backend.tools.ffmpeg_cli import FFmpegCLI
    from backend.tools.common_tools import get_readable_path

    # 探测 fps (使用短路径避免Unicode问题)
    cap = cv2.VideoCapture(get_readable_path(video_path))
    if not cap.isOpened():
        raise IOError(f"无法打开: {video_path}")
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0  # fallback: OpenCV读取失败时使用默认值
    cap.release()

    _log(f"  源: {total}帧, {fps}fps")

    os.makedirs(out_dir, exist_ok=True)
    ff = FFmpegCLI.instance().ffmpeg_path
    cmd = [
        ff, "-y", "-i", video_path,
        "-q:v", "1",
        "-loglevel", "error",
        os.path.join(out_dir, "%08d.png"),
    ]
    _sp.check_output(cmd, stdin=open(os.devnull), shell=False)
    extracted = len(_glob.glob(os.path.join(out_dir, "*.png")))
    if extracted != total and total > 0:
        _log(f"  ⚠️ 帧数不匹配: 预期{total}, 实际提取{extracted}")
    _log(f"  提取完成: {extracted} 帧")
    return fps


def _reassemble_video(
    frames_dir: str, output_path: str, fps: float,
    orig_video: str, multiplier: int, log_cb=None
):
    """将插值后的帧重新组装为视频"""
    _log = log_cb or (lambda m: None)
    temp_out = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    temp_path = temp_out.name
    temp_out.close()

    frame_files = natsorted(glob.glob(os.path.join(frames_dir, "*.png")))
    if not frame_files:
        raise RuntimeError("没有插值帧可组装")
    h, w = cv2.imread(frame_files[0]).shape[:2]
    target_fps = fps * multiplier

    writer = cv2.VideoWriter(temp_path, cv2.VideoWriter_fourcc(*"mp4v"),
                             target_fps, (w, h))
    for f in frame_files:
        writer.write(cv2.imread(f))
    writer.release()
    _log(f"  视频组装: {len(frame_files)} 帧, {target_fps}fps")

    # 合并音轨
    try:
        ff = _find_ffmpeg()
        tempo = 1.0 / multiplier
        # 使用本地 _build_atempo 函数
        ac = _build_atempo(tempo)
        cmd = [ff, "-y", "-i", temp_path, "-i", orig_video,
               "-vcodec", "libx264", "-crf", "18",
               "-map", "0:v:0",
               "-filter_complex", f"[1:a]{ac}[a]",
               "-map", "[a]", "-loglevel", "error", output_path]
        subprocess.check_output(cmd, stdin=open(os.devnull),
                                stderr=subprocess.DEVNULL, shell=False)
    except Exception:
        cmd = [ff, "-y", "-i", temp_path,
               "-vcodec", "libx264", "-crf", "18",
               "-loglevel", "error", output_path]
        subprocess.check_output(cmd, stdin=open(os.devnull), shell=False)
    finally:
        try:
            os.unlink(temp_path)
        except Exception:
            pass


def _find_ffmpeg():
    """获取 FFmpeg 路径"""
    from backend.tools.ffmpeg_cli import FFmpegCLI
    return FFmpegCLI.instance().ffmpeg_path


def _build_atempo(t):
    """构建 atempo 滤镜链（与 video_enhancer 中一致）"""
    if t >= 0.5:
        return f"atempo={t}"
    filters = []
    while t < 0.5:
        filters.append("atempo=0.5")
        t *= 2
    if abs(t - 1.0) > 0.001:
        filters.append(f"atempo={t}")
    return ",".join(filters)


def interpolate_video_ncnn(
    input_path: str,
    output_path: str,
    multiplier: int = 2,
    model_name: str = "rife-v3.1",
    gpu_id: int = 0,
    tta: bool = False,
    log_callback=None,
    progress_callback=None,
) -> str:
    """
    使用 rife-ncnn-vulkan 对视频做帧插值。

    Args:
        input_path: 输入视频路径
        output_path: 输出视频路径
        multiplier: 插值倍率 (2~8)
        model_name: ncnn 模型名称
        gpu_id: GPU 设备 ID (-1=CPU)
        tta: 启用 TTA 模式（精度更高但更慢）
        log_callback: 日志回调
        progress_callback: 进度回调
    """
    _log = log_callback or (lambda m: print(f"[RIFE-NCNN] {m}"))
    _prog = progress_callback or (lambda p, f: None)

    if not is_available():
        raise RuntimeError("rife-ncnn-vulkan 不可用，请检查文件完整性")

    # 确保模型存在
    model_dir = _ensure_model(model_name)

    # 模型兼容性检查：部分模型缺少 ncnn 所需的 .param 文件
    try:
        from backend.tools.model_compat import check_rife_ncnn_model_complete
        _ok, _msg = check_rife_ncnn_model_complete(model_name)
        if not _ok:
            raise RuntimeError(
                f"{_msg}。请切换模型（如 rife-v3.1）或改用 Python CUDA 后端"
            )
    except ImportError:
        pass

    # 创建临时目录
    tmp_root = tempfile.mkdtemp(prefix="rife_ncnn_")
    frames_in = os.path.join(tmp_root, "input")
    frames_out = os.path.join(tmp_root, "output")

    try:
        # 1. 提取帧
        _log("步骤 1/3: 提取视频帧…")
        fps = _extract_frames(input_path, frames_in, _log)
        _prog(10, False)

        frame_files = natsorted(glob.glob(os.path.join(frames_in, "*.png")))
        total_pairs = len(frame_files) - 1

        # 2. 目录模式批量插值（一次启动 exe，不反复加载模型）
        _log(f"步骤 2/3: 运行 ncnn 插值 (multiplier={multiplier}x)…")
        os.makedirs(frames_out, exist_ok=True)

        if multiplier == 2:
            # 目录模式: 交错合并 原帧→插值帧 (参考Flowframes)
            cmd = [_NCNN_EXE, "-v", "-i", frames_in, "-o", frames_out,
                   "-m", model_dir, "-g", str(gpu_id),
                   "-j", _ncnn_threads()]
            if tta:
                cmd.append("-x")
            _log("  目录模式 2x 插值…")
            subprocess.check_output(cmd, stderr=subprocess.DEVNULL)

            interp_files = natsorted(glob.glob(os.path.join(frames_out, "*.png")))
            merged = os.path.join(tmp_root, "merged")
            os.makedirs(merged, exist_ok=True)
            out_idx = 0
            for i in range(len(frame_files) - 1):
                shutil.copy2(frame_files[i], os.path.join(merged, f"{out_idx:08d}.png"))
                out_idx += 1
                if i < len(interp_files):
                    shutil.copy2(interp_files[i], os.path.join(merged, f"{out_idx:08d}.png"))
                    out_idx += 1
            shutil.copy2(frame_files[-1], os.path.join(merged, f"{out_idx:08d}.png"))
            out_idx += 1

            shutil.rmtree(frames_out, ignore_errors=True)
            os.rename(merged, frames_out)
            _log(f"  生成 {out_idx} 帧 (原 {len(frame_files)} 帧 × {multiplier}x)")

        else:
            # 高倍率：多级 2x 插值
            # level 1: 用目录模式生成 2x 帧到 work
            work = frames_in
            n_levels = int(np.ceil(np.log2(multiplier)))
            for level in range(n_levels):
                level_out = os.path.join(tmp_root, f"level_{level}")
                os.makedirs(level_out, exist_ok=True)
                cmd = [_NCNN_EXE, "-v", "-i", work, "-o", level_out,
                       "-m", model_dir, "-g", str(gpu_id),
                       "-j", _ncnn_threads()]
                if tta:
                    cmd.append("-x")
                _log(f"  第 {level+1} 级 2x 插值…")
                subprocess.check_output(cmd, stderr=subprocess.DEVNULL)

                orig = natsorted(glob.glob(os.path.join(work, "*.png")))
                interp = natsorted(glob.glob(os.path.join(level_out, "*.png")))
                merged = os.path.join(tmp_root, f"merged_{level}")
                os.makedirs(merged, exist_ok=True)
                out_idx = 0
                for i in range(len(orig) - 1):
                    shutil.copy2(orig[i], os.path.join(merged, f"{out_idx:08d}.png"))
                    out_idx += 1
                    if i < len(interp):
                        shutil.copy2(interp[i], os.path.join(merged, f"{out_idx:08d}.png"))
                        out_idx += 1
                shutil.copy2(orig[-1], os.path.join(merged, f"{out_idx:08d}.png"))
                out_idx += 1

                shutil.rmtree(level_out, ignore_errors=True)
                if work != frames_in:
                    shutil.rmtree(work, ignore_errors=True)
                work = merged

            # 如果倍率不是2的幂，取前 multiplier 倍帧
            if multiplier != 2 ** n_levels:
                all_f = natsorted(glob.glob(os.path.join(work, "*.png")))
                target = len(frame_files) * multiplier
                work = os.path.join(tmp_root, "trimmed")
                os.makedirs(work, exist_ok=True)
                for i in range(min(target, len(all_f))):
                    shutil.copy2(all_f[i], os.path.join(work, f"{i:08d}.png"))

            # work → frames_out
            if work != frames_out:
                if os.path.exists(frames_out):
                    shutil.rmtree(frames_out, ignore_errors=True)
                os.rename(work, frames_out)

        total_out = len(glob.glob(os.path.join(frames_out, "*.png")))
        _prog(90, False)

        # 3. 组装视频
        _log("步骤 3/3: 组装视频…")
        ff = _find_ffmpeg()
        target_fps = fps * multiplier
        _first_files = natsorted(glob.glob(os.path.join(frames_out, "*.png")))
        if not _first_files:
            raise RuntimeError("插值后无输出帧")
        h, w = cv2.imread(_first_files[0]).shape[:2]

        temp_video = os.path.join(tmp_root, "temp_no_audio.mp4")
        cmd = [ff, "-y", "-framerate", str(target_fps),
               "-i", os.path.join(frames_out, "%08d.png"),
               "-r", str(target_fps),
               "-vcodec", "libx264", "-crf", "18",
               "-pix_fmt", "yuv420p",
               "-loglevel", "error", temp_video]
        subprocess.check_output(cmd, stdin=open(os.devnull), shell=False)

        # 合并音轨
        try:
            tempo = 1.0 / multiplier
            ac = _build_atempo(tempo)
            merge_cmd = [ff, "-y", "-i", temp_video, "-i", input_path,
                         "-map", "0:v:0",
                         "-filter_complex", f"[1:a]{ac}[a]",
                         "-map", "[a]", "-loglevel", "error", output_path]
            subprocess.check_output(merge_cmd, stdin=open(os.devnull),
                                    stderr=subprocess.DEVNULL, shell=False)
        except Exception:
            shutil.copy2(temp_video, output_path)

        _prog(100, True)
        _log(f"完成: {fps}fps → {target_fps}fps")

    except Exception:
        import traceback
        traceback.print_exc()
        raise
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    return output_path
