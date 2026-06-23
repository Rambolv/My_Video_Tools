"""
E2FGVI 视频修复模型包装器

E2FGVI (CVPR 2022) - Towards An End-to-End Framework for Flow-Guided Video Inpainting
https://github.com/MCG-NKU/E2FGVI

优势：
- 比流式方法快15倍（Titan XP上0.12s/帧）
- 支持任意分辨率（HQ版本）
- 对动态水印/移动物体去除效果优异
- 显存占用适中，4090及以下显卡可用

模型下载：  # LVBOBO_markdown_BUG - 合规清理：移除百度网盘链接
E2FGVI-HQ: https://drive.google.com/file/d/10wGdKSUOie0XmCr8SQ2A2FeDe-mfn5w3

下载后放置到: backend/E2FGVI/release_model/E2FGVI-HQ-CVPR22.pth
"""

import os
import sys

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

# 使用 importlib 直接加载 E2FGVI 模型模块（避免子进程 sys.path 问题）
_E2FGVI_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'E2FGVI')

def _get_inpaint_generator():
    """惰性加载 InpaintGenerator，仅在首次用到时加载"""
    import importlib.util
    _model_init = os.path.join(_E2FGVI_DIR, 'model', '__init__.py')
    _e2fgvi_py = os.path.join(_E2FGVI_DIR, 'model', 'e2fgvi.py')

    # 确保 E2FGVI 目录在 sys.path 中
    if _E2FGVI_DIR not in sys.path:
        sys.path.insert(0, _E2FGVI_DIR)

    # 使用 importlib 加载 model 包（无 __init__.py 的命名空间包）
    if 'model' not in sys.modules:
        if os.path.exists(_model_init):
            _s = importlib.util.spec_from_file_location('model', _model_init,
                submodule_search_locations=[os.path.join(_E2FGVI_DIR, 'model')])
        else:
            # 命名空间包
            from importlib.machinery import PathFinder
            _s = PathFinder.find_spec('model', [os.path.join(_E2FGVI_DIR, 'model')])
        if _s:
            _m = importlib.util.module_from_spec(_s)
            sys.modules['model'] = _m
            _s.loader.exec_module(_m)

    # 加载 model.e2fgvi
    if 'model.e2fgvi' not in sys.modules:
        _s2 = importlib.util.spec_from_file_location('model.e2fgvi', _e2fgvi_py)
        _m2 = importlib.util.module_from_spec(_s2)
        sys.modules['model.e2fgvi'] = _m2
        _s2.loader.exec_module(_m2)

    return sys.modules['model.e2fgvi'].InpaintGenerator


InpaintGenerator = _get_inpaint_generator()


class E2FGVIInpaint:
    """E2FGVI 视频修复器"""

    def __init__(self, device=None, model_path=None, neighbor_stride=5, max_load_num=None):
        """
        Args:
            device: torch device
            model_path: 预训练模型路径
            neighbor_stride: 参考帧步长
            max_load_num: 最大同时加载帧数（None则自动调整）
        """
        # 默认设备
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = device

        # 模型路径
        if model_path is None:
            model_path = os.path.join(_E2FGVI_DIR, 'release_model', 'E2FGVI-HQ-CVPR22.pth')
        
        if not os.path.exists(model_path):
            # 尝试备用路径
            alt_path = os.path.join(_E2FGVI_DIR, 'release_model', 'E2FGVI-CVPR22.pth')
            if os.path.exists(alt_path):
                model_path = alt_path
            else:
                raise FileNotFoundError(
                    f"E2FGVI 模型未找到！请下载预训练模型到：\n"
                    f"  {model_path}\n"
                    f"下载地址：https://drive.google.com/file/d/10wGdKSUOie0XmCr8SQ2A2FeDe-mfn5w3"
                )

        self.neighbor_stride = neighbor_stride
        self.max_load_num = max_load_num

        # 加载模型
        print(f"[E2FGVI] Loading model from {model_path}")
        self.model = InpaintGenerator().to(self.device)
        checkpoint = torch.load(model_path, map_location=self.device, weights_only=True)
        missing, unexpected = self.model.load_state_dict(checkpoint, strict=False)
        if missing:
            print(f"[E2FGVI] Missing keys (OK): {missing[:3]}...")
        if unexpected:
            print(f"[E2FGVI] Unexpected keys (OK): {unexpected[:3]}...")

        # 开启半精度推理：FP16 显存减半
        if self.device.type == 'cuda':
            self.use_half = True
            try:
                self.model = self.model.half()
                self.dtype = torch.float16
                print(f"[E2FGVI] Using FP16 (half precision)")
            except Exception:
                self.use_half = False
                self.dtype = torch.float32
        else:
            self.use_half = False
            self.dtype = torch.float32

        self.model.eval()
        print(f"[E2FGVI] Model loaded on {self.device}")

    def __call__(self, frames, mask):
        """
        对一组帧进行视频修复

        Args:
            frames: List[np.ndarray], BGR格式帧列表
            mask: np.ndarray, 二值mask (H, W), 0=保留, 255=修复

        Returns:
            List[np.ndarray]: 修复后的帧列表 (BGR)
        """
        # 清理缓存
        if self.device.type == 'cuda':
            torch.cuda.empty_cache()

        if len(frames) < 2:
            # 单帧：复制一份作为临时上下文
            dummy_frames = [frames[0].copy(), frames[0].copy()]
            result = self.__call__(dummy_frames, mask)
            return [result[0]]

        h, w = frames[0].shape[:2]

        # E2FGVI 要求输入为 240×432（transformer 硬编码 output_size=(60,108)）
        # 缩放到此固定分辨率处理，然后输出缩放回原始尺寸
        need_scale = (h != 240 or w != 432)
        if need_scale:
            frames_scaled = [cv2.resize(f, (432, 240), interpolation=cv2.INTER_LINEAR) for f in frames]
        else:
            frames_scaled = frames

        # 自动适配批量大小
        num_frames = len(frames_scaled)
        max_frames = min(num_frames, self.max_load_num or num_frames)
        frames_scaled = frames_scaled[:max_frames]

        # mask也缩放到 240×432
        if need_scale:
            mask_scaled = cv2.resize(mask, (432, 240), interpolation=cv2.INTER_NEAREST)
        else:
            mask_scaled = mask

        # 转换格式
        video_frames = []
        for frame in frames_scaled:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            video_frames.append(rgb)

        # mask: (H, W) → (1, 1, H, W) tensor, 1=修复区域
        if mask_scaled.ndim == 2:
            mask_tensor = torch.from_numpy(mask_scaled.astype(np.float32) / 255.0).unsqueeze(0).unsqueeze(0)
        elif mask_scaled.ndim == 3 and mask_scaled.shape[2] == 1:
            mask_tensor = torch.from_numpy(mask_scaled.astype(np.float32) / 255.0).permute(2, 0, 1).unsqueeze(0)
        else:
            mask_gray = cv2.cvtColor(mask_scaled, cv2.COLOR_BGR2GRAY) if mask_scaled.ndim == 3 else mask_scaled
            mask_tensor = torch.from_numpy(mask_gray.astype(np.float32) / 255.0).unsqueeze(0).unsqueeze(0)

        # 视频帧: numpy [T, H, W, 3] → tensor (1, T, 3, H, W), 归一化到 [-1, 1]
        frames_np = np.stack(video_frames, axis=0)  # (T, H, W, 3)
        frames_np = frames_np.transpose(0, 3, 1, 2)  # (T, 3, H, W)
        video_tensor = torch.from_numpy(frames_np.astype(np.float32))  # (T, 3, H, W)
        video_tensor = (video_tensor / 127.5) - 1.0  # [0,255] → [-1,1]
        video_tensor = video_tensor.unsqueeze(0)  # (1, T, 3, H, W)

        # 移动到设备并转为半精度
        video_tensor = video_tensor.to(self.device, dtype=self.dtype)
        mask_tensor = mask_tensor.to(self.device, dtype=self.dtype)

        # 单批次推理
        with torch.no_grad():
            output = self._inpaint_batch(video_tensor, mask_tensor)

        # 后处理：[-1,1] → [0,255] RGB → BGR
        # output shape: (T, 3, H, W)
        output_t = output.clamp(-1, 1).float()
        output_np = ((output_t.permute(0, 2, 3, 1).cpu().numpy() + 1) * 127.5).clip(0, 255).astype(np.uint8)
        inpainted_frames = []
        for i in range(output_np.shape[0]):
            bgr = output_np[i][:, :, ::-1]  # RGB → BGR
            # 如果缩放过，缩放回原始分辨率
            if need_scale:
                bgr = cv2.resize(bgr, (w, h), interpolation=cv2.INTER_LINEAR)
            inpainted_frames.append(bgr)

        return inpainted_frames

    def _inpaint_batch(self, video, mask):
        """
        单批次推理

        Args:
            video: (1, T, 3, H, W)  RGB, 归一化到 [-1, 1]
            mask:  (1, 1, H, W)  二值mask, [0, 1]

        Returns:
            (1, T, 3, H, W)
        """
        B, T, C, H, W = video.size()
        assert C == 3, f"Expected 3-channel video, got {C}"

        # 确保尺寸是8的倍数
        pad_h = (8 - H % 8) % 8
        pad_w = (8 - W % 8) % 8
        if pad_h > 0 or pad_w > 0:
            video = F.pad(video, (0, pad_w, 0, pad_h))
            mask = F.pad(mask, (0, pad_w, 0, pad_h))

        # 应用mask：将待修复区域在RGB帧中设为 -1（对应归一化后的"空"值）
        # mask: (1, 1, H', W') → (1, T, 3, H', W')
        mask_expanded = mask.expand(B, T, 3, *video.shape[3:])
        masked_frames = video.clone()
        # 在mask为1（=修复）的区域，将像素设为 -1
        masked_frames = torch.where(mask_expanded > 0.5, 
                                     torch.full_like(masked_frames, -1.0, dtype=self.dtype), 
                                     masked_frames)

        # E2FGVI模型输入: (B, T, 3, H', W') + num_local_frames (int)
        output = self.model(masked_frames, T)[0]  # [0] = inpainted frames, [1] = pred_flows

        # output: (B, T, 3, H', W') in [-1, 1]
        output = torch.clamp(output, -1, 1)

        # 移除填充
        if pad_h > 0 or pad_w > 0:
            output = output[:, :, :, :H, :W]

        return output
