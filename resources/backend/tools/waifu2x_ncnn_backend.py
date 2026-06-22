"""
@desc: waifu2x-ncnn-vulkan 后端 — 调用 waifu2x-ncnn-vulkan.exe
MIT License, by nihui (https://github.com/nihui/waifu2x-ncnn-vulkan)
比 Python CUDA 更快，模型直接打包在 release 中，即开即用。
"""
import os, glob, cv2, shutil, tempfile, subprocess
from backend.tools.common_tools import natsorted

_WAIFU2X_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "waifu2x_ncnn")

# 可用模型架构: 架构名 → 目录名
_MODEL_ARCHES = {
    "cunet":          "models-cunet",                    # 最佳质量
    "upconv_anime":   "models-upconv_7_anime_style_art_rgb",  # 轻量动漫
}


def is_available():
    """检查二进制和模型是否就绪"""
    exe = os.path.join(_WAIFU2X_DIR, "waifu2x-ncnn-vulkan.exe")
    if not os.path.exists(exe):
        return False
    # 检查至少有一套模型
    for arch_dir in _MODEL_ARCHES.values():
        if glob.glob(os.path.join(_WAIFU2X_DIR, arch_dir, "*.bin")):
            return True
    return False


def _resolve_model_path(model_arch: str) -> str:
    """根据架构名解析模型目录路径"""
    rel = _MODEL_ARCHES.get(model_arch)
    if not rel:
        # fallback: 找第一个可用模型
        for ad in _MODEL_ARCHES.values():
            p = os.path.join(_WAIFU2X_DIR, ad)
            if os.path.isdir(p):
                return p
        return os.path.join(_WAIFU2X_DIR, "models-cunet")
    return os.path.join(_WAIFU2X_DIR, rel)


def enhance_video_waifu2x(input_path, output_path, scale=2, noise=-1, gpu_id=0,
                           model_arch="cunet", log_cb=None, prog_cb=None):
    """
    使用 waifu2x-ncnn-vulkan 处理视频
    参数:
        scale: 放大倍数 (1/2/4/8/16/32, 默认2)
        noise: 去噪级别 (-1=无/0/1/2/3, 默认-1)
        model_arch: 模型架构 (cunet/upconv_anime/upconv_photo)
    """
    _log = log_cb or (lambda m: None)
    _prog = prog_cb or (lambda p, f: None)

    exe = os.path.join(_WAIFU2X_DIR, "waifu2x-ncnn-vulkan.exe")
    if not os.path.exists(exe):
        raise RuntimeError("waifu2x-ncnn-vulkan 不可用，未找到二进制文件")

    model_path = _resolve_model_path(model_arch)
    if not glob.glob(os.path.join(model_path, "*.bin")):
        raise RuntimeError(f"未找到 waifu2x 模型文件: {model_path}")

    tmp = tempfile.mkdtemp(prefix="waifu2x_")
    frames_in = os.path.join(tmp, "in")
    frames_out = os.path.join(tmp, "out")
    os.makedirs(frames_in)
    os.makedirs(frames_out)

    try:
        # 步骤 1: 提取帧（FFmpeg 直接解码→PNG，比 cv2 循环快 3-5 倍）
        _log("步骤 1/3: 提取视频帧…")
        from backend.tools.ffmpeg_cli import FFmpegCLI
        ff = FFmpegCLI.instance().ffmpeg_path
        cap = cv2.VideoCapture(input_path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        cap.release()
        cmd_extract = [
            ff, "-y", "-i", input_path,
            "-q:v", "1",
            "-loglevel", "error",
            os.path.join(frames_in, "%08d.png")
        ]
        subprocess.check_output(cmd_extract, stdin=open(os.devnull), shell=False)
        idx = len(glob.glob(os.path.join(frames_in, "*.png")))
        _log(f"  提取 {idx} 帧")
        _prog(10, False)

        # 步骤 2: 运行 waifu2x
        _log("步骤 2/3: waifu2x 超分处理…")
        # 如果 scale>2 且模型只支持2x，则分多次处理
        current_scale = scale
        current_in = frames_in
        pass_count = 0
        while current_scale > 1:
            step_scale = min(current_scale, 2)  # waifu2x 单次最多 2x
            out_dir = os.path.join(tmp, f"pass_{pass_count}")
            os.makedirs(out_dir, exist_ok=True)

            cmd = [exe, "-i", current_in, "-o", out_dir,
                   "-s", str(step_scale),
                   "-m", model_path,
                   "-g", str(gpu_id),
                   "-j", "1:2:2",
                   "-f", "png"]
            if noise >= 0:
                cmd.extend(["-n", str(noise)])

            _log(f"  waifu2x 通 {pass_count + 1}: {step_scale}x")
            subprocess.check_output(cmd, stderr=subprocess.DEVNULL)

            current_in = out_dir
            current_scale //= 2
            pass_count += 1

        # 收集最终输出帧
        final_out = current_in
        out_files = natsorted(glob.glob(os.path.join(final_out, "*.png")))
        if not out_files:
            # 如果输出目录没有文件，可能输出到 frames_out
            out_files = natsorted(glob.glob(os.path.join(frames_out, "*.png")))
        if not out_files:
            raise RuntimeError("waifu2x 未生成任何输出文件")

        _prog(80, False)

        # 步骤 3: 组装视频
        _log("步骤 3/3: 组装视频…")
        h, w = cv2.imread(out_files[0]).shape[:2]

        from backend.tools.ffmpeg_cli import FFmpegCLI
        ff = FFmpegCLI.instance().ffmpeg_path
        temp_video = os.path.join(tmp, "out.mp4")
        cmd_enc = [ff, "-y", "-framerate", str(fps),
                   "-i", os.path.join(final_out, "%08d.png"),
                   "-vcodec", "libx264", "-crf", "18",
                   "-pix_fmt", "yuv420p",
                   "-loglevel", "error", temp_video]
        subprocess.check_output(cmd_enc, stdin=open(os.devnull), shell=False)

        # 合并音轨
        try:
            merge = [ff, "-y", "-i", temp_video, "-i", input_path,
                     "-vcodec", "copy", "-acodec", "copy",
                     "-loglevel", "error", output_path]
            subprocess.check_output(merge, stdin=open(os.devnull),
                                    stderr=subprocess.DEVNULL, shell=False)
        except Exception:
            shutil.copy2(temp_video, output_path)

        _prog(100, True)
        _log(f"完成: {fps}fps, {scale}x, 模型={os.path.basename(model_path)}")

    except Exception:
        raise
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
