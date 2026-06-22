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
    if not path or not os.path.exists(path):
        return path  # 保持原路径, 文件不存在时短路径无意义
    buf = ctypes.create_unicode_buffer(4096)
    ret = ctypes.windll.kernel32.GetShortPathNameW(path, buf, 4096)
    if ret > 0 and buf.value:
        return buf.value
    return path  # fallback: API 失败时返回原路径

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


def natsort_key(filepath: str):
    """自然排序键: 提取文件名中的数字用于正确排序。

    解决 sorted() 的字典序问题:
      字典序: 0.png, 1.png, 10.png, 2.png  (错误!)
      自然序: 0.png, 1.png, 2.png, 10.png  (正确)
    """
    name = os.path.basename(filepath)
    # 提取第一段连续数字作为主排序键
    m = _re.search(r'(\d+)', name)
    if m:
        return int(m.group(1))
    return 0


def natsorted(file_list):
    """自然排序文件列表 (按文件名中数字升序)。"""
    return sorted(file_list, key=natsort_key)

def vsr_clean_stem(stem: str) -> str:
    """清理文件名 stem 中的所有 VSR 后缀 (新旧兼容)。"""
    stem = _re.sub(r'_VSR.*$', '', stem)             # 新规范 _VSR*
    stem = _re.sub(r'_\d+clean_no_sub$', '', stem)    # 旧扫除 _Nclean_no_sub
    stem = _re.sub(r'_no_sub$', '', stem)             # 旧去字幕 _no_sub
    stem = _re.sub(r'_enhanced$', '', stem)           # 旧增强 _enhanced
    return stem


def vsr_output_path(input_path, ops="", ext=None):
    """生成 VSR 处理产物输出路径 (新旧命名兼容)。

    自动清理旧版 _no_sub/_Nclean_no_sub/_enhanced 后缀。
    """
    p = _Path(input_path)
    stem = vsr_clean_stem(p.stem)
    suffix = f"_VSR" if not ops else f"_VSR_{ops}"
    out_ext = ext if ext else p.suffix
    out_dir = os.path.dirname(os.path.abspath(input_path))
    return os.path.abspath(os.path.join(out_dir, f"{stem}{suffix}{out_ext}"))


def vsr_glob_outputs(input_dir, original_stem):
    """Glob 匹配 VSR 产物 (新旧命名兼容), 按修改时间降序。"""
    import glob as _glob
    stem = vsr_clean_stem(original_stem)
    pattern = os.path.join(input_dir, f"{stem}_VSR*")
    candidates = _glob.glob(pattern + ".*")
    if not candidates:
        candidates = _glob.glob(pattern + ".mp4")
    candidates.sort(key=os.path.getmtime, reverse=True)
    return candidates