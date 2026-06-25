#!/usr/bin/env python3
"""
声音自由生成修改大师 — FastAPI 服务启动入口

用法:
    python launch_api.py                    # 默认 127.0.0.1:8000
    python launch_api.py --port 8001         # 自定义端口
"""
import os
import sys
import argparse

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_ROOT))

from audio_studio.api import start_api_server


def main():
    parser = argparse.ArgumentParser(description="Audio Studio API Server")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    parser.add_argument("--port", type=int, default=8000, help="监听端口")
    args = parser.parse_args()

    print("=" * 60)
    print("  🔊 Audio Studio API Server")
    print(f"  📡 http://{args.host}:{args.port}")
    print(f"  📖 Docs: http://{args.host}:{args.port}/docs")
    print("=" * 60)

    start_api_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
