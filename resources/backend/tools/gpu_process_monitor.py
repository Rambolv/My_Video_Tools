"""
@desc: GPU 进程实时监控器 — 通过 nvidia-smi 轮询获取 GPU 占用进程的实时排名
支持查看所有使用 GPU 的进程（包括隐藏进程），按 GPU 计算负载/显存占用排序
"""
from __future__ import annotations
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class GpuProcessInfo:
    """单个 GPU 进程的信息"""
    pid: int
    process_name: str        # 可执行文件名（短名称）
    process_path: str        # 完整路径
    gpu_type: str            # "C"=Compute, "C+G"=Compute+Graphics, "G"=Graphics
    gpu_sm_pct: float        # GPU 计算核心利用率 (%)
    gpu_mem_pct: float       # GPU 内存控制器利用率 (%)
    gpu_enc_pct: float       # 编码器利用率 (%)
    gpu_dec_pct: float       # 解码器利用率 (%)
    system_mem_mb: float     # 进程占用的系统内存 (MB)


@dataclass
class GpuOverallInfo:
    """GPU 整体信息"""
    index: int
    name: str
    total_vram_mb: int
    used_vram_mb: int
    gpu_util_pct: float      # GPU 整体利用率 (%)
    mem_util_pct: float      # 显存控制器利用率 (%)
    temperature: int         # GPU 温度 (℃)
    processes: List[GpuProcessInfo] = field(default_factory=list)


def _run_nvidia_smi(args: List[str]) -> Optional[str]:
    """运行 nvidia-smi 命令并返回 stdout"""
    try:
        result = subprocess.run(
            ["nvidia-smi"] + args,
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )
        if result.returncode == 0:
            return result.stdout
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def _parse_pmon_output(output: str) -> dict[int, Tuple[float, float, float, float, str]]:
    """
    解析 nvidia-smi pmon -c 1 输出
    返回 {pid: (sm_pct, mem_pct, enc_pct, dec_pct, gpu_type)}
    """
    result: dict[int, Tuple[float, float, float, float, str]] = {}
    if not output:
        return result

    for line in output.splitlines():
        line = line.strip()
        # 跳过注释行和空行
        if not line or line.startswith('#'):
            continue
        parts = line.split()
        if len(parts) < 8:
            continue
        try:
            gpu_idx = int(parts[0])
            pid = int(parts[1])
            gpu_type = parts[2]  # C, C+G, G
            sm = parts[3]
            mem = parts[4]
            enc = parts[5]
            dec = parts[6]
            sm_pct = 0.0 if sm == '-' else float(sm)
            mem_pct = 0.0 if mem == '-' else float(mem)
            enc_pct = 0.0 if enc == '-' else float(enc)
            dec_pct = 0.0 if dec == '-' else float(dec)
            result[pid] = (sm_pct, mem_pct, enc_pct, dec_pct, gpu_type)
        except (ValueError, IndexError):
            continue
    return result


def _parse_compute_apps_output(output: str) -> dict[int, Tuple[str, str]]:
    """
    解析 nvidia-smi --query-compute-apps=... 输出
    返回 {pid: (process_path, used_gpu_memory)}
    used_gpu_memory 可能是 '[N/A]' 字符串（WDDM 驱动下）
    """
    result: dict[int, Tuple[str, str]] = {}
    if not output:
        return result

    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(',', 2)
        if len(parts) < 2:
            continue
        try:
            pid = int(parts[0].strip())
            process_path = parts[1].strip().strip('"')
            used_mem = parts[2].strip() if len(parts) > 2 else '[N/A]'
            result[pid] = (process_path, used_mem)
        except (ValueError, IndexError):
            continue
    return result


def _parse_gpu_query_output(output: str) -> Optional[Tuple[int, str, int, int, float, float, int]]:
    """
    解析 nvidia-smi --query-gpu=... 输出
    返回 (index, name, total_vram_mb, used_vram_mb, gpu_util_pct, mem_util_pct, temperature)
    """
    if not output:
        return None
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(',')]
        if len(parts) < 7:
            continue
        try:
            idx = int(parts[0])
            name = parts[1]
            total_mb = int(parts[2])
            used_mb = int(parts[3])
            gpu_util = float(parts[4])
            mem_util = float(parts[5])
            temp = int(parts[6])
            return (idx, name, total_mb, used_mb, gpu_util, mem_util, temp)
        except (ValueError, IndexError):
            continue
    return None


def _get_process_system_memory(pid: int) -> float:
    """获取指定 PID 的进程系统内存占用 (MB)"""
    try:
        import psutil
        try:
            proc = psutil.Process(pid)
            return proc.memory_info().rss / (1024 * 1024)  # bytes -> MB
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0.0
    except ImportError:
        # 降级：使用 tasklist 命令
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            if result.returncode == 0 and result.stdout:
                lines = result.stdout.strip().splitlines()
                if lines:
                    parts = lines[0].split(',')
                    if len(parts) >= 5:
                        mem_str = parts[4].strip().strip('"').replace(',', '').replace('K', '').strip()
                        if mem_str.isdigit():
                            return float(mem_str) / 1024  # KB -> MB
        except Exception:
            pass
        return 0.0


def _get_short_process_name(path: str) -> str:
    """从完整路径提取简短进程名称"""
    if not path:
        return "Unknown"
    # 处理 nvidia-smi 截断的路径（以 ... 开头）
    name = os.path.basename(path.replace('\\', '/'))
    if not name:
        # 如果路径是截断的，尝试从路径末尾提取
        name = path.split('\\')[-1] if '\\' in path else path
    return name


def get_gpu_info() -> Optional[GpuOverallInfo]:
    """
    获取 GPU 整体信息及所有进程的实时数据。
    返回 GpuOverallInfo 对象，包含 GPU 信息和按 GPU 计算负载降序排列的进程列表。
    """
    # 1. 获取 GPU 整体信息
    gpu_query = _run_nvidia_smi([
        "--query-gpu=index,name,memory.total,memory.used,utilization.gpu,utilization.memory,temperature.gpu",
        "--format=csv,noheader,nounits"
    ])
    gpu_data = _parse_gpu_query_output(gpu_query)
    if gpu_data is None:
        return None

    idx, name, total_mb, used_mb, gpu_util, mem_util, temp = gpu_data

    # 2. 获取所有 GPU 进程列表（compute-apps 包含所有使用 GPU 的进程）
    compute_apps = _run_nvidia_smi([
        "--query-compute-apps=pid,process_name,used_gpu_memory",
        "--format=csv,noheader"
    ])
    process_paths = _parse_compute_apps_output(compute_apps)

    # 3. 获取 per-process GPU 利用率
    pmon_out = _run_nvidia_smi(["pmon", "-c", "1"])
    pmon_data = _parse_pmon_output(pmon_out) if pmon_out else {}

    # 4. 合并数据
    processes: List[GpuProcessInfo] = []
    seen_pids = set()

    for pid, (sm_pct, mem_pct, enc_pct, dec_pct, gpu_type) in pmon_data.items():
        process_path = process_paths.get(pid, ("", ""))[0] if pid in process_paths else ""
        short_name = _get_short_process_name(process_path) if process_path else f"PID:{pid}"
        sys_mem = _get_process_system_memory(pid)
        processes.append(GpuProcessInfo(
            pid=pid,
            process_name=short_name,
            process_path=process_path,
            gpu_type=gpu_type,
            gpu_sm_pct=sm_pct,
            gpu_mem_pct=mem_pct,
            gpu_enc_pct=enc_pct,
            gpu_dec_pct=dec_pct,
            system_mem_mb=round(sys_mem, 1),
        ))
        seen_pids.add(pid)

    # 5. 处理在 compute-apps 中但不在 pmon 中的进程（如有）
    for pid, (proc_path, _used_mem) in process_paths.items():
        if pid not in seen_pids:
            short_name = _get_short_process_name(proc_path) if proc_path else f"PID:{pid}"
            sys_mem = _get_process_system_memory(pid)
            processes.append(GpuProcessInfo(
                pid=pid,
                process_name=short_name,
                process_path=proc_path,
                gpu_type="C",
                gpu_sm_pct=0.0,
                gpu_mem_pct=0.0,
                gpu_enc_pct=0.0,
                gpu_dec_pct=0.0,
                system_mem_mb=round(sys_mem, 1),
            ))

    # 6. 按 GPU 计算负载降序排列
    processes.sort(key=lambda p: p.gpu_sm_pct, reverse=True)

    return GpuOverallInfo(
        index=idx,
        name=name,
        total_vram_mb=total_mb,
        used_vram_mb=used_mb,
        gpu_util_pct=gpu_util,
        mem_util_pct=mem_util,
        temperature=temp,
        processes=processes,
    )


def format_gpu_info_text(info: GpuOverallInfo) -> str:
    """将 GPU 信息格式化为可读文本"""
    lines = []
    lines.append(f"╔══ GPU {info.index}: {info.name} ══╗")
    lines.append(f"  显存: {info.used_vram_mb} MiB / {info.total_vram_mb} MiB"
                 f" ({info.used_vram_mb/info.total_vram_mb*100:.1f}%)")
    lines.append(f"  GPU 利用率: {info.gpu_util_pct}%  |  显存控制器: {info.mem_util_pct}%  |  温度: {info.temperature}℃")
    lines.append(f"  进程数: {len(info.processes)}")
    lines.append("")
    lines.append(f"{'PID':>7} {'GPU%':>5} {'MEM%':>5} {'ENC':>4} {'DEC':>4} {'类型':>4} {'系统内存':>9}  进程名")
    lines.append("-" * 80)
    for p in info.processes:
        sys_mem_str = f"{p.system_mem_mb:.0f}MB" if p.system_mem_mb > 0 else "N/A"
        lines.append(
            f"{p.pid:>7} {p.gpu_sm_pct:>4.0f}% {p.gpu_mem_pct:>4.0f}% "
            f"{p.gpu_enc_pct:>3.0f}% {p.gpu_dec_pct:>3.0f}% "
            f"{p.gpu_type:>4} {sys_mem_str:>9} {p.process_name}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    # 测试
    info = get_gpu_info()
    if info:
        print(format_gpu_info_text(info))
    else:
        print("无法获取 GPU 信息（nvidia-smi 不可用或无 NVIDIA GPU）")
