import os
import sys
import ctypes

import cv2
import numpy as np
from fsplit.filesplit import Filesplit

video_extensions = {
    '.mp4', '.m4a', '.m4v', '.f4v', '.f4a', '.m4b', '.m4r', '.f4b', '.mov',
    '.3gp', '.3gp2', '.3g2', '.3gpp', '.3gpp2', '.ogg', '.oga', '.ogv', '.ogx',
    '.wmv', '.wma', '.asf', '.webm', '.flv', '.avi', '.gifv', '.mkv', '.rm',
    '.rmvb', '.vob', '.dvd', '.mpg', '.mpeg', '.mp2', '.mpe', '.mpv', '.mpg',
    '.mpeg', '.m2v', '.svi', '.3gp', '.mxf', '.roq', '.nsv', '.flv', '.f4v',
    '.f4p', '.f4a', '.f4b'
}

image_extensions = {
    '.jpg', '.jpeg', '.jpe', '.jif', '.jfif', '.jfi', '.png', '.gif',
    '.webp', '.tiff', '.tif', '.psd', '.raw', '.arw', '.cr2', '.nrw',
    '.k25', '.bmp', '.dib', '.heif', '.heic', '.ind', '.indd', '.indt',
    '.jp2', '.j2k', '.jpf', '.jpx', '.jpm', '.mj2', '.svg', '.svgz',
    '.ai', '.eps', '.ico'
}


def is_video_file(filename):
    return os.path.splitext(filename)[-1].lower() in video_extensions


def is_image_file(filename):
    return os.path.splitext(filename)[-1].lower() in image_extensions


def is_video_or_image(filename):
    file_extension = os.path.splitext(filename)[-1].lower()
    # 检查扩展名是否在定义的视频或图片文件后缀集合中
    return file_extension in video_extensions or file_extension in image_extensions

def merge_big_file_if_not_exists(dir, file, man_filename = None):
    if file not in os.listdir(dir):
        fs = Filesplit()
        if man_filename is not None:
            fs.man_filename = man_filename
        fs.merge(input_dir=dir)

def get_readable_path(path):
    if sys.platform != 'win32':
        return path
    buf = ctypes.create_unicode_buffer(4096)
    ctypes.windll.kernel32.GetShortPathNameW(path, buf, 4096)
    return buf.value

def read_image(path):
    if os.path.getsize(path) > 100*1024*1024: # 100MB
        print(f"Image {path} is too large, skip")
        return None
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), -1)
    if img is not None and img.shape[-1] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return img


# ═══════════════════════════════════════════════════════════════
#  VSR 输出命名规范 — 干净、显式、可复处理
# ═══════════════════════════════════════════════════════════════
#
# 命名模式: {stem}_VSR{ops}.{ext}
#   movie_VSR.mp4            → 去字幕
#   movie_VSR_SWEEP2.mp4     → 去字幕+扫除2轮
#   movie_VSR_SR4x.mp4       → 去字幕+超分4x
#   movie_VSR_FI2x.mp4       → 去字幕+帧插2x
#   movie_VSR_SR4x_FI2x.mp4  → 去字幕+SR+FI
#
# 优势: _VSR 统一标记易识别、易 glob 匹配、易清理复用

import re as _re
from pathlib import Path as _Path

def vsr_output_path(input_path, ops="", ext=None):
    """生成 VSR 处理产物输出路径。

    Args:
        input_path: 原始输入文件路径
        ops: 操作标签, 如 "SWEEP2", "SR4x", "FI2x", "SR4x_FI2x"
        ext: 输出扩展名 (默认继承输入)

    Returns:
        绝对路径, 如 /path/movie_VSR_SR4x_FI2x.mp4
    """
    p = _Path(input_path)
    stem = p.stem
    # 清理已有的 _VSR* 后缀 (支持复处理)
    stem = _re.sub(r'_VSR.*$', '', stem)
    suffix = f"_VSR" if not ops else f"_VSR_{ops}"
    out_ext = ext if ext else p.suffix
    out_dir = os.path.dirname(os.path.abspath(input_path))
    return os.path.abspath(os.path.join(out_dir, f"{stem}{suffix}{out_ext}"))


def vsr_glob_outputs(input_dir, original_stem):
    """Glob 匹配指定原始文件的所有 VSR 产物, 按修改时间降序。

    Args:
        input_dir: 输出目录
        original_stem: 原始文件名 stem (不含 _VSR 后缀)

    Returns:
        匹配文件路径列表 (最新在前)
    """
    import glob as _glob
    stem = _re.sub(r'_VSR.*$', '', original_stem)
    pattern = os.path.join(input_dir, f"{stem}_VSR*")
    candidates = _glob.glob(pattern + ".*")  # 匹配任意扩展名
    if not candidates:
        candidates = _glob.glob(pattern + ".mp4")
    candidates.sort(key=os.path.getmtime, reverse=True)
    return candidates