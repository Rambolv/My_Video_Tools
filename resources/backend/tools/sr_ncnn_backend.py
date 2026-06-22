"""
@desc: Real-ESRGAN NCNN Vulkan 后端 — 调用 realesrgan-ncnn-vulkan.exe
比 Python CUDA 版本快 2-5 倍，自动下载二进制，尝试从多镜像源下载模型。
若模型下载失败，框架自动回退到 Python CUDA 后端。
"""
import os, sys, glob, cv2, shutil, tempfile, subprocess, zipfile, io, warnings
from backend.config import config
from backend.tools.common_tools import natsorted

_SR_NCNN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sr_ncnn")
_MODELS_DIR = os.path.join(_SR_NCNN_DIR, "models")

# ── 下载源（含镜像）─────────────────────────────────────────────
# 二进制
_BINARY_URLS = [
    "https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan/releases/download/v0.2.0/realesrgan-ncnn-vulkan-v0.2.0-windows.zip",
    "https://ghproxy.com/https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan/releases/download/v0.2.0/realesrgan-ncnn-vulkan-v0.2.0-windows.zip",
    "https://mirror.ghproxy.com/https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan/releases/download/v0.2.0/realesrgan-ncnn-vulkan-v0.2.0-windows.zip",
]
# ncnn 模型文件（.param + .bin），从 GitHub raw 或镜像下载
# 注意：.bin 文件在 GitHub 上以 git-lfs 存储，raw.githubusercontent.com
# 无法直接提供实际内容，以下为最佳尝试。若全部失败请使用 Python 后端。
_MODEL_FILE_URLS = {
    "realesr-animevideov3-x4": [
        # .param (小文件，非LFS)
        "https://raw.githubusercontent.com/xinntao/Real-ESRGAN-ncnn-vulkan/master/models/realesr-animevideov3-x4/realesr-animevideov3-x4.param",
        "https://ghproxy.com/https://raw.githubusercontent.com/xinntao/Real-ESRGAN-ncnn-vulkan/master/models/realesr-animevideov3-x4/realesr-animevideov3-x4.param",
        "https://mirror.ghproxy.com/https://raw.githubusercontent.com/xinntao/Real-ESRGAN-ncnn-vulkan/master/models/realesr-animevideov3-x4/realesr-animevideov3-x4.param",
        # .bin (LFS，可能不可用)
        "https://ghproxy.com/https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan/raw/master/models/realesr-animevideov3-x4/realesr-animevideov3-x4.bin",
        "https://mirror.ghproxy.com/https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan/raw/master/models/realesr-animevideov3-x4/realesr-animevideov3-x4.bin",
    ],
    "realesrgan-x4plus": [
        "https://raw.githubusercontent.com/xinntao/Real-ESRGAN-ncnn-vulkan/master/models/realesrgan-x4plus.param",
        "https://ghproxy.com/https://raw.githubusercontent.com/xinntao/Real-ESRGAN-ncnn-vulkan/master/models/realesrgan-x4plus.param",
        "https://mirror.ghproxy.com/https://raw.githubusercontent.com/xinntao/Real-ESRGAN-ncnn-vulkan/master/models/realesrgan-x4plus.param",
        "https://ghproxy.com/https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan/raw/master/models/realesrgan-x4plus.bin",
        "https://mirror.ghproxy.com/https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan/raw/master/models/realesrgan-x4plus.bin",
    ],
}


def _try_download(url, dest_path, timeout=120):
    """尝试从单个 URL 下载文件，成功返回 True"""
    try:
        import requests
        r = requests.get(url, timeout=timeout, stream=True)
        r.raise_for_status()
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(8192):
                if chunk:
                    f.write(chunk)
        # 验证：最小有效模型文件应 > 1KB，且不能是 HTML
        sz = os.path.getsize(dest_path)
        if sz < 256:
            os.unlink(dest_path)
            return False
        with open(dest_path, "rb") as f:
            head = f.read(256)
        if b"<!DOCTYPE" in head or b"<html" in head.lower():
            os.unlink(dest_path)
            return False
        return True
    except Exception:
        if os.path.exists(dest_path):
            try:
                os.unlink(dest_path)
            except Exception:
                pass
        return False


def _download_and_extract(url, dest_dir):
    """下载 zip 并解压到目标目录"""
    os.makedirs(dest_dir, exist_ok=True)
    zip_path = os.path.join(dest_dir, "tmp.zip")
    if _try_download(url, zip_path):
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(dest_dir)
        os.unlink(zip_path)
        return True
    return False


def _download_model_files(model_key):
    """尝试从多个镜像下载 ncnn 模型文件"""
    urls = _MODEL_FILE_URLS.get(model_key)
    if not urls:
        return False

    # 确定模型目录
    if "-x" in model_key:
        # 如 realesr-animevideov3-x4 → models/realesr-animevideov3-x4/
        model_dir = os.path.join(_MODELS_DIR, model_key)
    else:
        model_dir = _MODELS_DIR
    os.makedirs(model_dir, exist_ok=True)

    downloaded = 0
    for url in urls:
        fname = os.path.basename(url.split("?")[0])
        if not fname:
            continue
        dest = os.path.join(model_dir, fname)
        if os.path.exists(dest) and os.path.getsize(dest) > 1024:
            # 已存在，验证不是 HTML
            with open(dest, "rb") as f:
                if b"<!DOCTYPE" not in f.read(256):
                    downloaded += 1
                    continue
        if _try_download(url, dest):
            downloaded += 1
    # 需要同时有 .param 和 .bin
    has_param = bool(glob.glob(os.path.join(model_dir, "*.param")))
    has_bin = bool(glob.glob(os.path.join(model_dir, "*.bin")))
    return has_param and has_bin


def is_available():
    """检查二进制和模型是否都就绪"""
    exe = os.path.join(_SR_NCNN_DIR, "realesrgan-ncnn-vulkan.exe")
    if not os.path.exists(exe):
        return False
    # 检查是否有可用模型
    model_name = config.srModelName.value if hasattr(config, 'srModelName') else "realesr-animevideov3"
    # 映射模型名到目录名
    if model_name == "realesr-animevideov3":
        model_dir = os.path.join(_MODELS_DIR, "realesr-animevideov3-x4")
    elif model_name == "realesrgan-x4plus":
        model_dir = _MODELS_DIR
    else:
        model_dir = _MODELS_DIR
    return bool(glob.glob(os.path.join(model_dir, "*.bin")))


def initialize():
    """确保二进制和模型就绪，若模型无法下载不抛异常（由上层回退）"""
    exe = os.path.join(_SR_NCNN_DIR, "realesrgan-ncnn-vulkan.exe")
    if not os.path.exists(exe):
        print("[SR-NCNN] 下载 realesrgan-ncnn-vulkan 二进制...")
        ok = False
        for url in _BINARY_URLS:
            if _download_and_extract(url, _SR_NCNN_DIR):
                ok = True
                break
        if ok:
            # 移动可能存在的子目录中的文件到根目录
            for item in os.listdir(_SR_NCNN_DIR):
                sub = os.path.join(_SR_NCNN_DIR, item)
                if os.path.isdir(sub) and item.startswith("realesrgan"):
                    for f in os.listdir(sub):
                        shutil.move(os.path.join(sub, f), os.path.join(_SR_NCNN_DIR, f))
                    shutil.rmtree(sub, ignore_errors=True)
            exe_path = os.path.join(_SR_NCNN_DIR, "realesrgan-ncnn-vulkan.exe")
            if os.path.exists(exe_path):
                try:
                    os.chmod(exe_path, 0o755)
                except Exception:
                    pass
            print("[SR-NCNN] ✅ 二进制就绪")
        else:
            print("[SR-NCNN] ❌ 无法下载二进制，将使用 Python 后端")
            return

    # 下载模型
    model_name = config.srModelName.value if hasattr(config, 'srModelName') else "realesr-animevideov3"
    # 映射模型名到 _MODEL_FILE_URLS 的 key
    model_key_map = {
        "realesr-animevideov3": "realesr-animevideov3-x4",
        "realesrgan-x4plus": "realesrgan-x4plus",
    }
    model_key = model_key_map.get(model_name, model_name)
    model_dir = os.path.join(_MODELS_DIR, model_key) if "-x" in model_key else _MODELS_DIR

    if not glob.glob(os.path.join(model_dir, "*.bin")):
        print(f"[SR-NCNN] 下载模型 {model_name}...")
        if _download_model_files(model_key):
            print("[SR-NCNN] ✅ 模型就绪")
        else:
            print(f"[SR-NCNN] ⚠️ 无法下载 {model_name} ncnn 模型文件，将回退到 Python CUDA 后端")
            print(f"[SR-NCNN]    (可手动将 ncnn .param/.bin 文件放入 {_MODELS_DIR})")


def enhance_video_ncnn(input_path, output_path, scale=4, gpu_id=0, log_cb=None, prog_cb=None):
    """使用 realesrgan-ncnn-vulkan 处理视频"""
    _log = log_cb or (lambda m: None)
    _prog = prog_cb or (lambda p, f: None)
    initialize()

    exe = os.path.join(_SR_NCNN_DIR, "realesrgan-ncnn-vulkan.exe")
    if not os.path.exists(exe):
        raise RuntimeError("realesrgan-ncnn-vulkan 不可用")

    tmp = tempfile.mkdtemp(prefix="sr_ncnn_")
    frames_in = os.path.join(tmp, "in")
    frames_out = os.path.join(tmp, "out")
    os.makedirs(frames_in)
    os.makedirs(frames_out)

    try:
        # 提取帧（FFmpeg 直接解码→PNG，比 cv2 循环快 3-5 倍）
        _log("步骤 1/3: 提取视频帧…")
        from backend.tools.ffmpeg_cli import FFmpegCLI
        ff = FFmpegCLI.instance().ffmpeg_path
        cap = cv2.VideoCapture(input_path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        cap.release()
        cmd_extract = [
            ff, "-y", "-i", input_path,
            "-q:v", "1",                     # 高质量 PNG
            "-loglevel", "error",
            os.path.join(frames_in, "%08d.png")
        ]
        subprocess.check_output(cmd_extract, stdin=open(os.devnull), shell=False)
        idx = len(glob.glob(os.path.join(frames_in, "*.png")))
        _log(f"  提取 {idx} 帧")
        _prog(10, False)

        # 运行 ncnn 超分
        _log("步骤 2/3: 超分处理…")
        model_name = config.srModelName.value
        # 查找模型目录
        model_dirs = glob.glob(os.path.join(_SR_NCNN_DIR, "models", "*"))
        model_path = None
        for md in model_dirs:
            if os.path.isdir(md) and glob.glob(os.path.join(md, "*.bin")):
                model_path = md
                break
        if not model_path:
            raise FileNotFoundError("未找到超分模型文件")

        cmd = [exe, "-i", frames_in, "-o", frames_out,
               "-m", model_path, "-s", str(scale),
               "-g", str(gpu_id), "-j", "1:2:2",
               "-f", "png"]
        subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
        _prog(80, False)

        # 组装视频
        _log("步骤 3/3: 组装视频…")
        out_w, out_h = 0, 0
        out_files = natsorted(glob.glob(os.path.join(frames_out, "*.png")))
        if out_files:
            h, w = cv2.imread(out_files[0]).shape[:2]
            out_w, out_h = w, h

        from backend.tools.ffmpeg_cli import FFmpegCLI
        ff = FFmpegCLI.instance().ffmpeg_path
        temp_video = os.path.join(tmp, "out.mp4")
        cmd = [ff, "-y", "-framerate", str(fps),
               "-i", os.path.join(frames_out, "%08d.png"),
               "-r", str(fps),  # 显式输出帧率
               "-vcodec", "libx264", "-crf", "18",
               "-pix_fmt", "yuv420p",
               "-loglevel", "error", temp_video]
        subprocess.check_output(cmd, stdin=open(os.devnull), shell=False)

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
        _log(f"完成: {fps}fps, {scale}x 超分")

    except Exception:
        raise
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
