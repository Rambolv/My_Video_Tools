import traceback
import importlib.util

import torch

from backend.config import tr

# ── 全局推理优化：启用 cuDNN 自动算法选择 ──
# 对 CNN 密集型模型 (STTN 编码器/解码器) 提速 5-15%
_OPTIMIZE_ATTEMPTED = False

def _ensure_inference_optimized():
    """全局一次性推理优化设置（幂等，多次调用安全）"""
    global _OPTIMIZE_ATTEMPTED
    if _OPTIMIZE_ATTEMPTED:
        return
    _OPTIMIZE_ATTEMPTED = True
    try:
        if torch.cuda.is_available():
            # 让 cuDNN 自动选择最优卷积算法（固定输入尺寸时最优）
            torch.backends.cudnn.benchmark = True
            # 启用 cuDNN 确定性模式（可选，略降性能但结果可复现）—— 推理不需要
            torch.backends.cudnn.deterministic = False
            # 允许 TF32 加速（Ampere+ GPU, 如 RTX 30/40 系列）
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
    except Exception:
        pass


class HardwareAccelerator:

    # 类变量，用于存储单例实例
    _instance = None

    @classmethod
    def instance(cls):
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = HardwareAccelerator()
            cls._instance.initialize()
        return cls._instance

    def __init__(self):
        self.__cuda = False
        self.__dml = False
        self.__mps = False
        self.__onnx_providers = []
        self.__enabled = True
        self.__device = None

    def initialize(self):
        _ensure_inference_optimized()
        self.check_directml_available()
        self.check_cuda_available()
        self.check_mps_available()
        self.load_onnx_providers()

    def check_directml_available(self):
        self.__dml = importlib.util.find_spec("torch_directml")

    def check_cuda_available(self):
        self.__cuda = torch.cuda.is_available()

    def check_mps_available(self):
        self.__mps = torch.backends.mps.is_available() and torch.backends.mps.is_built()

    def load_onnx_providers(self):
        try:
            import onnxruntime as ort
            available_providers = ort.get_available_providers()
            for provider in available_providers:
                if provider in [
                    "CPUExecutionProvider"
                ]:
                    continue
                if provider not in [
                    "DmlExecutionProvider",         # DirectML，适用于 Windows GPU
                    "ROCMExecutionProvider",        # AMD ROCm
                    "MIGraphXExecutionProvider",    # AMD MIGraphX
                    "VitisAIExecutionProvider",     # AMD VitisAI，适用于 RyzenAI & Windows, 实测和DirectML性能似乎差不多
                    "OpenVINOExecutionProvider",    # Intel GPU
                    "MetalExecutionProvider",       # Apple macOS
                    "CoreMLExecutionProvider",      # Apple macOS
                    "CUDAExecutionProvider",        # Nvidia GPU
                ]:
                    print(tr['Main']['OnnxExectionProviderNotSupportedSkipped'].format(provider))
                    continue
                print(tr['Main']['OnnxExecutionProviderDetected'].format(provider))
                self.__onnx_providers.append(provider)
        except ModuleNotFoundError as e:
            print(tr['Main']['OnnxRuntimeNotInstall'])

    def has_accelerator(self):
        if not self.__enabled:
            return False
        return self.__cuda or self.__dml or self.__mps or len(self.__onnx_providers) > 0

    @property
    def accelerator_name(self):
        if not self.__enabled:
            return "CPU"
        if self.__dml:
            return "DirectML"
        if self.__cuda:
            return "GPU"
        if self.__mps:
            return "MPS"
        elif len(self.__onnx_providers) > 0:
            return ", ".join(self.__onnx_providers)
        else:
            return "CPU"

    @property
    def onnx_providers(self):
        if not self.__enabled:
            return ["CPUExecutionProvider"]
        return self.__onnx_providers

    def has_cuda(self):
        if not self.__enabled:
            return False
        return self.__cuda
    
    def has_mps(self):
        if not self.__enabled:
            return False
        return self.__mps

    def get_gpu_vram_gb(self) -> float:
        """获取 GPU 显存总量（GB），CUDA 直接查询，其他返回估算值"""
        try:
            if self.__cuda:
                import torch
                props = torch.cuda.get_device_properties(0)
                return props.total_memory / (1024**3)  # bytes → GB
            if self.__mps:
                try:
                    import subprocess, re
                    result = subprocess.run(
                        ["system_profiler", "SPDisplaysDataType"],
                        capture_output=True, text=True, timeout=10)
                    for line in result.stdout.splitlines():
                        m = re.search(r'VRAM.*?(\d+)\s*GB', line)
                        if m:
                            return float(m.group(1))
                except Exception:
                    pass
                return 8.0  # 默认 M 系列芯片共享内存
            if self.__dml:
                try:
                    import torch_directml
                    return 8.0  # DirectML 无法直接查询，假设 8GB
                except Exception:
                    return 6.0
        except Exception:
            pass
        return 4.0  # CPU/未知 保守估计

    def get_dedicated_vram_gb(self) -> float:
        """获取 GPU 专用显存（GB），通过 nvidia-smi 查询排除共享系统内存。

        Windows WDDM 驱动会将部分系统 RAM 映射为"共享 GPU 内存"，
        torch.cuda 报告的 total_memory 包含此共享部分。
        本方法只返回硬件板载专用显存。
        """
        try:
            if not self.__cuda:
                return self.get_gpu_vram_gb()
            import subprocess, re
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                mb = float(result.stdout.strip().splitlines()[0].strip())
                return mb / 1024.0  # MiB → GiB
        except Exception:
            pass
        return self.get_gpu_vram_gb()

    def lock_dedicated_vram(self, headroom_pct: float = 10.0):
        """锁定 CUDA 进程显存上限为专用显存的 (100-headroom_pct)%。

        调用后 PyTorch 分配显存超过此上限时将直接抛出 OOM 错误，
        而非通过 Windows WDDM 驱动溢出到慢速共享系统内存。

        仅在 CUDA 设备且 config.lockDedicatedVram 开启时生效。

        Returns:
            (locked_gb, total_cuda_gb, fraction) 或 (None, None, None)
        """
        if not self.__cuda:
            return None, None, None
        try:
            from backend.config import config
            if not config.lockDedicatedVram.value:
                return None, None, None

            import torch
            import os

            dedicated = self.get_dedicated_vram_gb()
            total_cuda = self.get_gpu_vram_gb()

            # CUDA 报告的 total 包含共享内存（Windows），分数需用 dedicated/total
            fraction = (dedicated * (1.0 - headroom_pct / 100.0)) / total_cuda
            fraction = max(0.3, min(fraction, 1.0))  # 至少留 30%，最多 100%

            # ── 核心锁定策略 ──
            # 1. 设置 PyTorch 进程级显存上限
            torch.cuda.set_per_process_memory_fraction(fraction, 0)

            # 2. 环境变量：禁用可扩展内存段（防止 CUDA 缓存突破限制）
            os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "")
            current = os.environ.get("PYTORCH_CUDA_ALLOC_CONF", "")
            if "expandable_segments:False" not in current:
                new_conf = "expandable_segments:False"
                if current:
                    new_conf = current + "," + new_conf
                os.environ["PYTORCH_CUDA_ALLOC_CONF"] = new_conf

            locked_gb = dedicated * (1.0 - headroom_pct / 100.0)
            print(f"[VRAM Lock] 专用显存: {dedicated:.1f}GB → 锁定上限: {locked_gb:.1f}GB "
                  f"(fraction={fraction:.2f}, headroom={headroom_pct:.0f}%)")
            return locked_gb, total_cuda, fraction
        except Exception as e:
            print(f"[VRAM Lock] 锁定失败: {e}")
            return None, None, None

    def set_enabled(self, enable):
        self.__enabled = enable

    @property
    def device(self):
        """
        onnxruntime-directml 1.21.1-1.22.0(往上未测试) 和 torch-directml 不能同时初始化, 会相互影响
        提示site-packages/onnxruntime/capi/onnxruntime_inference_collection.py", line 266, in run
                return self._sess.run(output_names, input_feed, run_options)
                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
            UnicodeDecodeError: 'utf-8' codec can't decode byte 0xb2 in position 344: invalid start bn 344: invalid start byte
        onnxruntime-directml 1.21.1 则正常, 但Win10跑不起来, Win11正常
        为了避免冲突以及避免重写一个QPT智能部署流程, 这里采用延迟初始化的方式+继续使用onnxruntime-directml 1.20.1
        当然SubtitleDetect放到一个独立进程去操作也是可以的
        """
        if self.__enabled:
            if self.__dml:
                try:
                    import torch_directml
                    dml_device = torch_directml.device(torch_directml.default_device())
                    self.__dml = True
                    return dml_device
                except Exception:
                    traceback.print_exc()
                    self.__dml = False
            if self.__cuda:
                return torch.device("cuda:0")
            if self.__mps:
                return torch.device("mps")
        return torch.device("cpu")