#!/usr/bin/env python3
"""
声音自由生成修改大师 — Gradio WebUI 启动入口

用法:
    python launch_webui.py                    # 默认 127.0.0.1:7865
    python launch_webui.py --port 7866         # 自定义端口
    python launch_webui.py --host 0.0.0.0      # 局域网访问
    python launch_webui.py --share             # 分享链接
"""
import os
import sys
import socket
import argparse

# 确保路径正确
_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_ROOT))  # backend/

from audio_studio.config import get_config, AudioStudioConfig
from audio_studio.webui import launch_gradio


def _find_free_port(start: int, max_attempts: int = 20) -> int:
    """从 start 开始扫描可用端口"""
    for port in range(start, start + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError(f"无法找到可用端口 (范围: {start}-{start + max_attempts - 1})")


def main():
    parser = argparse.ArgumentParser(description="声音自由生成修改大师 WebUI")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    parser.add_argument("--port", type=int, default=7865, help="监听端口")
    parser.add_argument("--share", action="store_true", help="创建分享链接")
    parser.add_argument("--debug", action="store_true", help="调试模式")
    parser.add_argument("--device", default="cuda:0", help="推理设备")
    parser.add_argument("--dtype", default="fp16", choices=["fp16", "fp32"])
    parser.add_argument("--vram-limit", type=float, default=8.0, help="显存上限(GB)")
    args = parser.parse_args()

    # 自动检测可用端口
    try:
        args.port = _find_free_port(args.port)
    except RuntimeError as e:
        print(f"⚠️  {e}")
        sys.exit(1)

    # 更新配置
    cfg = AudioStudioConfig(
        device=args.device,
        dtype=args.dtype,
        vram_limit_gb=args.vram_limit,
        gradio_port=args.port,
    )
    from audio_studio.config import set_config
    set_config(cfg)

    print("=" * 60)
    print("  🔊 声音自由生成修改大师")
    print(f"  📡 http://{args.host}:{args.port}")
    print(f"  🖥  Device: {args.device} | Dtype: {args.dtype}")
    print(f"  📖 REST API: http://{args.host}:8000/docs")
    print("=" * 60)

    launch_gradio(host=args.host, port=args.port,
                  share=args.share, debug=args.debug)


if __name__ == "__main__":
    main()
