"""
外部AI项目启动器 — 启动本地已部署的AI项目（ACE-Step、VoxCPM2等）
使用 VSR 自带的 Python 解释器，确保依赖和 CUDA 环境正确
"""
import os
import sys
import subprocess
import threading
from pathlib import Path
from typing import Optional


# ─── 获取 VSR 内置 Python 解释器 ───
_VSR_ROOT = Path(__file__).resolve().parent.parent.parent  # resources/
_BUNDLED_PYTHON = str(_VSR_ROOT.parent / "Python" / "python.exe")
if not os.path.exists(_BUNDLED_PYTHON):
    _BUNDLED_PYTHON = "python"  # fallback


def _build_env(extra_env: dict = None) -> dict:
    """构建环境变量：使用系统 site-packages，禁用用户 site-packages"""
    env = os.environ.copy()
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    if extra_env:
        env.update(extra_env)
    return env


# ─── 已内化的本地项目路径 ───
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_LOCAL_PROJECTS = {
    "ace_step": {
        "path": os.path.join(_THIS_DIR, "..", "..", "..", "vendor", "ai_audio", "ace_step"),
        "name": "ACE-Step 1.5 音乐生成",
        "entry": os.path.join(_THIS_DIR, "..", "audio_studio", "launch_ace.py"),
        "type": "gradio",
        "port": 7860,
        "url": "http://127.0.0.1:7860",
        "use_bundled_python": True,
    },
    "voxcpm2": {
        "path": os.path.join(_THIS_DIR, "..", "..", "..", "vendor", "ai_audio", "voxcpm2"),
        "name": "VoxCPM2 声音克隆",
        "entry": os.path.join(_THIS_DIR, "..", "audio_studio", "launch_voxcpm.py"),
        "type": "gradio",
        "port": 8808,
        "url": "http://127.0.0.1:8808",
        "use_bundled_python": True,
    },
}

_running_processes = {}
_lock = threading.Lock()


def get_project_info(project_key: str) -> Optional[dict]:
    """获取项目信息"""
    return _LOCAL_PROJECTS.get(project_key)


def list_available_projects() -> list:
    """列出所有可用项目及其状态"""
    result = []
    for key, info in _LOCAL_PROJECTS.items():
        entry_path = os.path.join(info["path"], info["entry"])
        available = os.path.exists(entry_path)
        running = key in _running_processes and _running_processes[key].poll() is None
        result.append({
            "key": key,
            "name": info["name"],
            "path": info["path"],
            "entry": info["entry"],
            "available": available,
            "running": running,
            "url": info["url"],
            "type": info["type"],
        })
    return result


def launch_project(project_key: str) -> tuple:
    """
    启动外部AI项目
    
    Args:
        project_key: 项目标识（'ace_step' / 'voxcpm2'）
    
    Returns:
        (success: bool, message: str)
    """
    info = _LOCAL_PROJECTS.get(project_key)
    if not info:
        return False, f"未知项目: {project_key}"

    entry_path = os.path.join(info["path"], info["entry"])
    if not os.path.exists(entry_path):
        return False, f"项目入口不存在: {entry_path}"

    with _lock:
        # 检查是否已在运行
        if project_key in _running_processes:
            proc = _running_processes[project_key]
            if proc.poll() is None:
                return True, f"{info['name']} 已在运行中 (PID: {proc.pid})"

        try:
            print(f"\n{'='*60}")
            print(f"  🚀 启动 {info['name']}")
            print(f"{'='*60}")

            # 决定启动方式
            use_bundled = info.get("use_bundled_python", False)
            if use_bundled and os.path.exists(_BUNDLED_PYTHON):
                cmd = [_BUNDLED_PYTHON, entry_path]
                extra_env = {"PYTHONPATH": info["path"]} if os.path.exists(info["path"]) else None
                print(f"  Python: {_BUNDLED_PYTHON}")
                print(f"  脚本: {entry_path}")
                print(f"  URL: {info['url']}")
                print(f"{'='*60}\n")
                proc = subprocess.Popen(
                    cmd,
                    cwd=info["path"],
                    env=_build_env(extra_env),
                )
            else:
                print(f"  入口: {entry_path}")
                print(f"  URL: {info['url']}")
                print(f"{'='*60}\n")
                proc = subprocess.Popen(
                    [entry_path],
                    cwd=info["path"],
                    shell=True,
                    env=_build_env(),
                )
            _running_processes[project_key] = proc
            return True, f"{info['name']} 已启动 (PID: {proc.pid})，输出信息如上所示"
        except Exception as e:
            return False, f"启动失败: {e}"


def stop_project(project_key: str) -> tuple:
    """
    停止外部AI项目
    
    Args:
        project_key: 项目标识
    """
    with _lock:
        if project_key not in _running_processes:
            return False, f"{project_key} 未在运行"
        proc = _running_processes[project_key]
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        del _running_processes[project_key]
        return True, f"已停止 {project_key}"


def stop_all_projects():
    """停止所有运行中的项目"""
    for key in list(_running_processes.keys()):
        stop_project(key)


def open_project_url(project_key: str) -> Optional[str]:
    """获取项目 Web UI 地址"""
    info = _LOCAL_PROJECTS.get(project_key)
    if info:
        return info["url"]
    return None
