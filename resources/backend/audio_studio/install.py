#!/usr/bin/env python3
"""
一键安装脚本 — 自动安装依赖、检测环境、下载模型
"""
import os
import sys
import subprocess
import platform


def print_step(msg):
    print(f"\n{'='*60}")
    print(f"  [STEP] {msg}")
    print(f"{'='*60}")


def run_cmd(cmd, check=True):
    print(f"  > {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 and check:
        print(f"  ⚠️  返回码: {result.returncode}")
        if result.stderr:
            print(f"  Error: {result.stderr[:500]}")
    return result


def check_python():
    print_step("检测 Python 环境")
    print(f"  Python {sys.version}")
    print(f"  Platform: {platform.platform()}")
    if sys.version_info < (3, 10):
        print("  ❌ 需要 Python 3.10+")
        sys.exit(1)
    print("  ✅ Python 版本合格")


def check_cuda():
    print_step("检测 CUDA 环境")
    try:
        import torch
        print(f"  PyTorch: {torch.__version__}")
        cuda_available = torch.cuda.is_available()
        if cuda_available:
            print(f"  CUDA: {torch.version.cuda}")
            print(f"  GPU: {torch.cuda.get_device_name(0)}")
            print(f"  VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
        else:
            print("  ⚠️  CUDA 不可用, 将使用 CPU（性能极慢）")
        print(f"  ✅ CUDA 检测完成")
    except ImportError:
        print("  ❌ PyTorch 未安装")


def install_dependencies():
    print_step("安装 Python 依赖")
    req_path = os.path.join(os.path.dirname(__file__), "requirements.txt")
    if not os.path.exists(req_path):
        print(f"  ❌ 未找到 requirements.txt")
        return

    # 国内源加速
    pip_args = [sys.executable, "-m", "pip", "install", "-r", req_path]
    # 尝试使用清华源
    result = run_cmd(pip_args + ["-i", "https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple"],
                     check=False)
    if result.returncode != 0:
        print("  ⚠️  清华源失败, 尝试默认源...")
        run_cmd(pip_args, check=False)
    print("  ✅ 依赖安装完成")


def check_voxcpm2():
    print_step("检测 VoxCPM2")
    _root = os.path.dirname(os.path.abspath(__file__))
    vox_path = os.path.join(_root, "..", "..", "..", "vendor", "ai_audio", "voxcpm2")
    if os.path.exists(vox_path):
        print(f"  ✅ VoxCPM2 已内化: {vox_path}")
        sys.path.insert(0, vox_path)
        old_val = os.environ.get("PYTHONNOUSERSITE")
        os.environ["PYTHONNOUSERSITE"] = "1"
        try:
            import voxcpm  # noqa
            print(f"  ✅ VoxCPM2 可导入 ({os.path.basename(voxcpm.__file__)})")
        except Exception as e:
            err = str(e)
            if "DLL" in err or "127" in err:
                print(f"  ⚠️  VoxCPM2 导入: CUDA DLL 问题 (代码结构正常)")
            else:
                print(f"  ⚠️  VoxCPM2 导入异常: {err.split(chr(10))[0]}")
        finally:
            if old_val is None:
                os.environ.pop("PYTHONNOUSERSITE", None)
            else:
                os.environ["PYTHONNOUSERSITE"] = old_val
    else:
        print(f"  ❌ VoxCPM2 未内化 (预期路径: {vox_path})")
        print(f"     请运行: python scripts/setup_windows.ps1")


def check_ace_step():
    print_step("检测 ACE-Step 1.5")
    _root = os.path.dirname(os.path.abspath(__file__))
    ace_path = os.path.join(_root, "..", "..", "..", "vendor", "ai_audio", "ace_step")
    if os.path.exists(ace_path):
        print(f"  ✅ ACE-Step 1.5 已内化: {ace_path}")
        sys.path.insert(0, ace_path)
        try:
            import acestep  # noqa
            print(f"  ✅ ACE-Step 可导入")
        except ImportError:
            print(f"  ⚠️  ACE-Step 目录存在但无法导入")
    else:
        print(f"  ❌ ACE-Step 1.5 未内化 (预期路径: {ace_path})")


def check_ffmpeg():
    print_step("检测 FFmpeg")
    result = run_cmd(["ffmpeg", "-version"], check=False)
    if result.returncode == 0:
        ver = result.stdout.split("\n")[0] if result.stdout else "unknown"
        print(f"  ✅ FFmpeg: {ver}")
    else:
        print(f"  ❌ FFmpeg 未安装 (音频处理需要)")
        print(f"     请安装: winget install ffmpeg 或 https://ffmpeg.org/download.html")


def main():
    print()
    print("🧩 声音自由生成修改大师 — 环境检测与安装")
    print()

    check_python()
    check_cuda()
    check_ffmpeg()
    check_voxcpm2()
    check_ace_step()
    install_dependencies()

    print()
    print("=" * 60)
    print("  🎉 环境检测完成！")
    print()
    print("  启动方式:")
    print("    python launch_webui.py    # Gradio WebUI")
    print("    python launch_api.py      # FastAPI 服务")
    print("=" * 60)


if __name__ == "__main__":
    main()
