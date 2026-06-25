#!/usr/bin/env python3
"""
Audio Studio 模型下载工具
自动下载 VoxCPM2（声音克隆）和 ACE-Step 1.5（音乐生成）所需模型到项目内目录。
支持国内镜像回退（hf-mirror.com / ModelScope）。

用法:
    python download_models.py                        # 下载所有模型
    python download_models.py --voxcpm               # 仅 VoxCPM2
    python download_models.py --ace                  # 仅 ACE-Step
    python download_models.py --mirror huggingface   # 强制指定源
    python download_models.py --mirror modelscope    # 使用 ModelScope
    python download_models.py --force               # 强制重新下载
"""
import os
import sys
import argparse
import hashlib
from pathlib import Path

# ─── 路径计算 ───
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "..", ".."))

VENDOR_AUDIO = os.path.join(PROJECT_ROOT, "vendor", "ai_audio")
VOX_SRC = os.path.join(VENDOR_AUDIO, "voxcpm2")
ACE_SRC = os.path.join(VENDOR_AUDIO, "ace_step")
HF_HUB = os.path.join(VENDOR_AUDIO, "models", "hub")
ACE_CHECKPOINTS = os.path.join(ACE_SRC, "checkpoints")

# ─── 模型清单 ───
MODELS = {
    "voxcpm2": {
        "repo_id": "openbmb/VoxCPM2",
        "modelscope_id": "OpenBMB/VoxCPM2",
        "target_dir": os.path.join(HF_HUB, "models--openbmb--VoxCPM2"),
        "description": "VoxCPM2 声音克隆模型 (~4.5GB)",
        "files": ["model.safetensors", "audiovae.pth", "config.json",
                  "tokenizer.json", "tokenizer_config.json"],
    },
    "ace_dit": {
        "repo_id": "ACE-Step/acestep-v15-turbo",
        "subdir": "acestep-v15-turbo",
        "target_dir": os.path.join(ACE_CHECKPOINTS, "acestep-v15-turbo"),
        "description": "ACE-Step DiT 音乐生成模型 (~4.5GB)",
        "files": ["model.safetensors", "config.json"],
    },
    "ace_lm": {
        "repo_id": "ACE-Step/acestep-5Hz-lm-1.7B",
        "subdir": "acestep-5Hz-lm-1.7B",
        "target_dir": os.path.join(ACE_CHECKPOINTS, "acestep-5Hz-lm-1.7B"),
        "description": "ACE-Step 5Hz LM 语言模型 (~3.5GB)",
        "files": ["model.safetensors", "config.json"],
    },
    "ace_vae": {
        "repo_id": "ACE-Step/Ace-Step1.5",
        "subdir": "vae",
        "target_dir": os.path.join(ACE_CHECKPOINTS, "vae"),
        "description": "ACE-Step VAE 编解码器 (~337MB)",
        "files": ["diffusion_pytorch_model.safetensors"],
    },
    "ace_text_encoder": {
        "repo_id": "ACE-Step/Ace-Step1.5",
        "subdir": "Qwen3-Embedding-0.6B",
        "target_dir": os.path.join(ACE_CHECKPOINTS, "Qwen3-Embedding-0.6B"),
        "description": "ACE-Step 文本编码器 (~1.1GB)",
        "files": ["model.safetensors", "config.json"],
    },
}

# ─── 工具函数 ───

def log(msg: str, level: str = "INFO"):
    icons = {"INFO": "  📦", "OK": "  ✅", "WARN": "  ⚠️ ", "ERR": "  ❌", "STEP": "\n══════"}
    icon = icons.get(level, "  📝")
    print(f"{icon} {msg}")


def _resolve_mirror_endpoint(mirror: str = "auto") -> str:
    """解析下载源地址"""
    if mirror == "huggingface":
        return "https://huggingface.co"
    elif mirror == "modelscope":
        return "https://modelscope.cn"  # ModelScope
    elif mirror == "hf-mirror":
        return "https://hf-mirror.com"
    else:  # auto: 尝试探测网络
        import socket
        try:
            socket.create_connection(("www.google.com", 443), timeout=2)
            return "https://huggingface.co"  # 能连外网 → 官方源
        except OSError:
            return "https://hf-mirror.com"  # 不能 → HF 镜像


def _check_file_size(filepath: str, min_mb: float = 1) -> bool:
    """验证文件是否完整（大小达标）"""
    if not os.path.isfile(filepath):
        return False
    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    return size_mb >= min_mb


def _sha256(filepath: str) -> str:
    """计算文件 SHA256"""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


# ─── VoxCPM2 下载 ───

def _download_voxcpm(mirror: str, force: bool):
    """下载 VoxCPM2 模型到 HF 缓存目录"""
    info = MODELS["voxcpm2"]
    target = info["target_dir"]
    snapshots_dir = os.path.join(target, "snapshots")
    refs_dir = os.path.join(target, "refs")
    os.makedirs(snapshots_dir, exist_ok=True)
    os.makedirs(refs_dir, exist_ok=True)

    # 检查是否已存在
    existing = list(Path(snapshots_dir).iterdir()) if os.path.isdir(snapshots_dir) else []
    if existing and not force:
        log(f"VoxCPM2 已存在 ({len(existing)} 个快照), 跳过", "OK")
        log(f"  路径: {target}", "INFO")
        return True

    log(f"下载 VoxCPM2 模型 (~4.5GB)...", "STEP")
    log(f"  目标: {target}", "INFO")

    endpoint = _resolve_mirror_endpoint(mirror)

    if "modelscope" in endpoint:
        # ModelScope 方式下载
        return _download_from_modelscope(info["modelscope_id"], target, info["files"])
    else:
        # HuggingFace 方式下载（含镜像回退）
        return _download_from_huggingface(info["repo_id"], target, info["files"],
                                          endpoint, mirror == "auto")


def _download_from_huggingface(repo_id: str, target_dir: str,
                                required_files: list, endpoint: str,
                                try_mirror_fallback: bool = True) -> bool:
    """从 HuggingFace Hub（或镜像）下载模型"""
    from huggingface_hub import snapshot_download

    # 保存原 endpoint 并在失败时恢复
    old_endpoint = os.environ.get("HF_ENDPOINT")
    if endpoint:
        os.environ["HF_ENDPOINT"] = endpoint
    # 清除 cached constants
    import huggingface_hub.constants as hf_const
    hf_const.HF_ENDPOINT = endpoint

    try:
        log(f"  源: {endpoint}/{repo_id}")
        path = snapshot_download(
            repo_id=repo_id,
            local_dir=target_dir,
            local_dir_use_symlinks=False,
            resume_download=True,
            ignore_patterns=["*.h5", "*.ot", "*.msgpack"],  # 跳过非必要文件
        )
        log(f"  下载完成: {path}", "OK")
        # 验证文件完整性
        missing = [f for f in required_files
                   if not _check_file_exists(os.path.join(target_dir, f))]
        if missing:
            log(f"  缺少文件: {missing}", "WARN")
            return False
        return True
    except Exception as e:
        err_str = str(e)
        log(f"  失败: {type(e).__name__}", "WARN")
        if try_mirror_fallback and ("SSL" in err_str or "connect" in err_str.lower()):
            mirror = "https://hf-mirror.com" if "hf-mirror" not in endpoint else "https://huggingface.co"
            log(f"  尝试镜像: {mirror}", "INFO")
            return _download_from_huggingface(repo_id, target_dir, required_files,
                                              mirror, try_mirror_fallback=False)
        return False
    finally:
        # 恢复环境变量
        if old_endpoint:
            os.environ["HF_ENDPOINT"] = old_endpoint
        else:
            os.environ.pop("HF_ENDPOINT", None)


def _download_from_modelscope(model_id: str, target_dir: str,
                               required_files: list) -> bool:
    """从 ModelScope 下载模型"""
    try:
        from modelscope import snapshot_download as ms_download
        log(f"  源: ModelScope/{model_id}")
        path = ms_download(
            model_id=model_id,
            local_dir=target_dir,
        )
        log(f"  下载完成: {path}", "OK")
        return True
    except ImportError:
        log(f"  modelscope 未安装，跳过", "WARN")
        return False
    except Exception as e:
        log(f"  ModelScope 下载失败: {e}", "ERR")
        return False


def _check_file_exists(path: str) -> bool:
    """检查文件是否存在且非空"""
    return os.path.isfile(path) and os.path.getsize(path) > 0


# ─── ACE-Step 下载 ───

def _download_ace_models(mirror: str, force: bool):
    """下载 ACE-Step 所有子模型到 checkpoints 目录"""
    ace_keys = ["ace_dit", "ace_lm", "ace_vae", "ace_text_encoder"]

    for key in ace_keys:
        info = MODELS[key]
        target = info["target_dir"]
        subdir = info.get("subdir", "")

        # 检查是否已存在
        existing_files = [f for f in info["files"]
                         if _check_file_exists(os.path.join(target, f))]
        if len(existing_files) == len(info["files"]) and not force:
            log(f"{info['description']} 已存在", "OK")
            continue

        log(f"下载 {info['description']}...", "STEP")
        os.makedirs(target, exist_ok=True)

        # 确定下载源
        endpoint = _resolve_mirror_endpoint(mirror)

        if "modelscope" in endpoint:
            # ACE 在 ModelScope 上可以用主仓库 ID
            success = _download_from_modelscope(
                info.get("modelscope_id", info["repo_id"]),
                target, info["files"]
            )
        else:
            # 从主仓库下载子目录
            success = _download_from_huggingface(
                info["repo_id"], target, info["files"],
                endpoint, mirror == "auto"
            )

        if not success:
            log(f"  {info['description']} 下载失败", "ERR")
            log(f"  手动下载: https://huggingface.co/{info['repo_id']}", "INFO")
            log(f"  放置到: {target}", "INFO")


# ─── 主入口 ───

def main():
    parser = argparse.ArgumentParser(
        description="Audio Studio 模型下载工具 — 支持国内镜像回退"
    )
    parser.add_argument("--voxcpm", action="store_true", help="仅下载 VoxCPM2")
    parser.add_argument("--ace", action="store_true", help="仅下载 ACE-Step")
    parser.add_argument("--mirror", choices=["auto", "huggingface", "hf-mirror", "modelscope"],
                       default="auto", help="下载源 (auto=自动检测)")
    parser.add_argument("--force", action="store_true", help="强制重新下载")
    args = parser.parse_args()

    print("=" * 60)
    print("  Audio Studio 模型下载工具")
    print(f"  项目根: {PROJECT_ROOT}")
    print(f"  目标目录:")
    print(f"    VoxCPM2:    {HF_HUB}/models--openbmb--VoxCPM2/")
    print(f"    ACE-Step:   {ACE_CHECKPOINTS}/")
    print("=" * 60)

    # 选择下载源
    mirror = args.mirror
    if mirror == "auto":
        mirror = _resolve_mirror_endpoint("auto")
        log(f"  自动选择源: {mirror}", "INFO")

    success = True

    # 下载 VoxCPM2
    if not args.ace or args.voxcpm:
        if not _download_voxcpm(mirror, args.force):
            log("VoxCPM2 下载未完成", "WARN")
            success = False

    # 下载 ACE-Step
    if not args.voxcpm or args.ace:
        _download_ace_models(mirror, args.force)

    print("\n" + "=" * 60)
    if success:
        log("全部模型下载完成！", "OK")
    else:
        log("部分模型下载未完成，请检查网络后重试", "WARN")
        log("或手动下载放置到对应目录", "INFO")
    print("=" * 60)


if __name__ == "__main__":
    main()
