#!/usr/bin/env python3
"""
ACE-Step 1.5 WebUI 启动器 — 使用 VSR 内置 Python，自动设置环境

用法:
    python launch_ace.py                    # 默认 127.0.0.1:7860
    python launch_ace.py --port 7861        # 自定义端口
"""
import os
import sys
import socket
import subprocess
import argparse
import warnings

# ─── 屏蔽第三方库弃用警告 ───
warnings.filterwarnings("ignore", category=FutureWarning,
                       message=".*weight_norm.*")
warnings.filterwarnings("ignore", category=DeprecationWarning,
                       message=".*HTTP_422_UNPROCESSABLE_ENTITY.*")


def _find_free_port(start: int, max_attempts: int = 20) -> int:
    """从 start 开始扫描可用端口"""
    for port in range(start, start + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError(f"无法找到可用端口 (范围: {start}-{start + max_attempts - 1})")


def main():
    parser = argparse.ArgumentParser(description="ACE-Step 1.5 WebUI")
    parser.add_argument("--port", type=int, default=7860, help="监听端口")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    parser.add_argument("--language", default="zh", help="界面语言")
    parser.add_argument("--config_path", default="acestep-v15-turbo",
                       help="模型配置路径")
    args = parser.parse_args()

    # ── 自动检测端口 ──
    try:
        args.port = _find_free_port(args.port)
    except RuntimeError as e:
        print(f"⚠️  {e}")
        sys.exit(1)

    # ACE 源码已内化到 vendor/ai_audio/ace_step
    _AS_DIR = os.path.dirname(os.path.abspath(__file__))
    _ACE_ROOT = os.path.join(_AS_DIR, "..", "..", "..", "vendor", "ai_audio", "ace_step")
    _PIPELINE = os.path.join(_ACE_ROOT, "acestep", "acestep_v15_pipeline.py")

    # ── 本项目内路径（输出/模型） ──
    _PROJECT_OUTPUT   = os.path.join(_AS_DIR, "ace_outputs")      # 生成音频
    _PROJECT_ROOT     = os.path.join(_AS_DIR, "..", "..", "..")   # VSR 项目根
    _PROJECT_CHECKPT  = os.path.join(_AS_DIR, "ace_checkpoints")  # 模型权重

    # 构建命令行参数
    cmd = [
        sys.executable,
        _PIPELINE,
        "--port", str(args.port),
        "--server-name", args.host,
        "--language", args.language,
        "--config_path", args.config_path,
        "--use_flash_attention", "False",
        # 不传 --init_service：让用户在 WebUI 中点击 "Init Service" 手动初始化
        # 避免启动时 GPU 满载导致桌面卡顿
    ]

    # 设置环境变量 — 让 ACE 子进程的所有 I/O 都指向本项目
    env = os.environ.copy()
    env["PYTHONNOUSERSITE"] = "1"
    env["ACE_STEP_SUPPRESS_AUDIO_TOKENS"] = "1"
    env["TOKENIZERS_PARALLELISM"] = "false"
    env["ACE_STEP_OUTPUT_DIR"]      = _PROJECT_OUTPUT   # 生成音频 → ace_outputs
    env["ACESTEP_PROJECT_ROOT"]     = _PROJECT_ROOT     # 项目根目录
    env["ACESTEP_CHECKPOINTS_DIR"]  = os.path.join(_ACE_ROOT, "checkpoints")  # 模型权重
    # 模型缓存内化（共享 AI 音频模型缓存）
    _HF_CACHE = os.path.join(_AS_DIR, "..", "..", "..", "vendor", "ai_audio", "models")
    # 直接赋值确保覆盖父进程继承的环境变量
    env["HF_HOME"] = _HF_CACHE
    env["HUGGINGFACE_HUB_CACHE"] = os.path.join(_HF_CACHE, "hub")

    print(f"""
{'='*60}
  🎵 ACE-Step 1.5 音乐生成 WebUI
{'='*60}
  📡 地址: http://{args.host}:{args.port}
  🖥  Python: {sys.executable}
  📂 模型: {args.config_path}
  📁 输出: {_PROJECT_OUTPUT}
  📁 权重: {_PROJECT_CHECKPT}
  ⚡ 首次启动会自动下载模型 (约 5-10GB)...
  ⚠️  请勿同时提交多个生成任务，否则可能导致 CUDA 错误！
{'='*60}
""")

    # 启动 pipeline 子进程（输出直接透传）
    proc = subprocess.Popen(
        cmd,
        cwd=_ACE_ROOT,
        env=env,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    proc.wait()


if __name__ == "__main__":
    main()
