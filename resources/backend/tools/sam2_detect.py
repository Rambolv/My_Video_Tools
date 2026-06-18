"""
SAM2 视频水印检测包装器

SAM 2 (Segment Anything Model 2) - Meta FAIR
https://github.com/facebookresearch/sam2

用于视频中水印/Logo的智能检测与逐帧跟踪：
- 用户在第一帧框选水印 → SAM2 自动跟踪整个视频
- 输出每帧的像素级mask → 送入 E2FGVI / ProPainter 修复
- 支持动态水印（移动、缩放、变形、半透明）

模型下载地址（4个版本）：
  tiny:  https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_tiny.pt
  small: https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_small.pt
  base:  https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_base_plus.pt
  large: https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_large.pt
"""

import os
import sys
from pathlib import Path

import cv2
import numpy as np
import torch

# 将 SAM2 目录加入 Python 路径
_SAM2_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'sam2')
if _SAM2_DIR not in sys.path:
    sys.path.insert(0, _SAM2_DIR)

_MODEL_CONFIGS = {
    "tiny": {
        "cfg": "sam2/configs/sam2.1/sam2.1_hiera_t.yaml",
        "ckpt": "sam2.1_hiera_tiny.pt",
    },
    "small": {
        "cfg": "sam2/configs/sam2.1/sam2.1_hiera_s.yaml",
        "ckpt": "sam2.1_hiera_small.pt",
    },
    "base": {
        "cfg": "sam2/configs/sam2.1/sam2.1_hiera_b+.yaml",
        "ckpt": "sam2.1_hiera_base_plus.pt",
    },
    "large": {
        "cfg": "sam2/configs/sam2.1/sam2.1_hiera_l.yaml",
        "ckpt": "sam2.1_hiera_large.pt",
    },
}


class SAM2WatermarkDetector:
    """
    SAM2 水印检测器

    工作流程：
    1. init_state(video_path) - 初始化视频状态
    2. add_prompt(frame_idx, box/point) - 在第一帧标记水印位置
    3. propagate() - 自动跟踪所有帧
    4. get_masks() - 获取每帧的mask

    Usage:
        detector = SAM2WatermarkDetector(model_size="small")
        masks = detector.detect_video_watermark(
            video_path="video.mp4",
            prompt_box=(x1, y1, x2, y2),  # 水印位置框
            prompt_frame=0,
        )
    """

    def __init__(self, model_size="small", device=None):
        """
        Args:
            model_size: "tiny", "small", "base", "large"
            device: torch device，None则自动选择cuda/cpu
        """
        if model_size not in _MODEL_CONFIGS:
            raise ValueError(f"Invalid model_size: {model_size}. Choose from {list(_MODEL_CONFIGS.keys())}")

        self.model_size = model_size
        cfg_rel = _MODEL_CONFIGS[model_size]["cfg"]
        ckpt_name = _MODEL_CONFIGS[model_size]["ckpt"]

        self.config_path = os.path.join(_SAM2_DIR, cfg_rel)
        self.checkpoint_path = os.path.join(_SAM2_DIR, "checkpoints", ckpt_name)

        if not os.path.exists(self.checkpoint_path):
            alt_path = os.path.join(_SAM2_DIR, "checkpoints", ckpt_name.replace("sam2.1_", "sam2_"))
            if os.path.exists(alt_path):
                self.checkpoint_path = alt_path
            else:
                raise FileNotFoundError(
                    f"SAM2 模型未找到: {self.checkpoint_path}\n"
                    f"请下载模型到 sam2/checkpoints/ 目录"
                )

        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = device

        print(f"[SAM2] Loading {model_size} model from {self.checkpoint_path}")
        from sam2.build_sam import build_sam2_video_predictor
        self.predictor = build_sam2_video_predictor(
            self.config_path, self.checkpoint_path, device=self.device
        )
        self._state = None
        self._masks = {}
        print(f"[SAM2] Model loaded on {self.device}")

    def detect_video_watermark(
        self,
        video_path: str,
        prompt_box: tuple = None,
        prompt_points: list = None,
        prompt_labels: list = None,
        prompt_frame: int = 0,
    ) -> dict:
        """
        检测整个视频中的水印

        Args:
            video_path: 视频文件路径
            prompt_box: 水印边界框 (x1, y1, x2, y2) 或 None
            prompt_points: 水印上的点坐标列表 [(x, y), ...]（配合 prompt_labels 使用）
            prompt_labels: 点标签列表 [1=前景, 0=背景]
            prompt_frame: 在第几帧进行提示（默认第0帧）

        Returns:
            dict: {frame_idx: np.ndarray} 每帧的二值mask (True=水印区域)
        """
        print(f"[SAM2] Processing video: {video_path}")

        # 读取视频帧
        cap = cv2.VideoCapture(video_path)
        frames = []
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        cap.release()

        if len(frames) == 0:
            raise ValueError("Failed to read video frames")

        print(f"[SAM2] Read {len(frames)} frames, running inference...")

        # 初始化推理状态
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            self._state = self.predictor.init_state(video_path=frames)

            # 在第 prompt_frame 帧添加提示
            prompt_frame = min(prompt_frame, len(frames) - 1)

            if prompt_box is not None:
                # 框提示
                x1, y1, x2, y2 = prompt_box
                box = np.array([[x1, y1, x2, y2]], dtype=np.float32)
                _, _, masks = self.predictor.add_new_points_or_box(
                    self._state, box=box, frame_idx=prompt_frame, obj_id=0
                )
            elif prompt_points is not None:
                # 点提示
                points = np.array(prompt_points, dtype=np.float32)
                labels = np.array(prompt_labels or [1] * len(points), dtype=np.int32)
                _, _, masks = self.predictor.add_new_points_or_box(
                    self._state,
                    points=points,
                    labels=labels,
                    frame_idx=prompt_frame,
                    obj_id=0,
                )
            else:
                raise ValueError("必须提供 prompt_box 或 prompt_points")

            self._masks = {}

            # 保存提示帧的mask
            if masks is not None and len(masks) > 0:
                self._masks[prompt_frame] = masks[0, 0].cpu().numpy() > 0

            # 传播到所有帧
            for out_frame_idx, out_obj_ids, out_masks in self.predictor.propagate_in_video(self._state):
                if out_masks is not None and len(out_masks) > 0:
                    self._masks[out_frame_idx] = out_masks[0, 0].cpu().numpy() > 0

        print(f"[SAM2] Detected watermark in {len(self._masks)} frames")
        return self._masks

    def detect_watermark_polygons(self, frame_idx: int) -> list:
        """
        将SAM2 mask转换为多边形坐标列表

        Args:
            frame_idx: 帧索引

        Returns:
            List[np.ndarray]: 多边形列表，每个多边形(N,2)
        """
        if frame_idx not in self._masks:
            return []

        mask = (self._masks[frame_idx] * 255).astype(np.uint8)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        polygons = []
        for cnt in contours:
            if len(cnt) < 3:
                continue
            # 简化轮廓
            epsilon = 0.005 * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, epsilon, True)
            polygons.append(approx.reshape(-1, 2).astype(np.float32))

        return polygons

    def get_mask(self, frame_idx: int) -> np.ndarray:
        """获取指定帧的mask"""
        return self._masks.get(frame_idx, None)

    def get_all_masks(self) -> dict:
        """获取所有帧的mask"""
        return self._masks

    def get_frame_box_dict(self) -> dict:
        """
        获取帧号 -> 矩形坐标的映射（兼容现有检测接口）

        Returns:
            dict: {frame_no: [(xmin, xmax, ymin, ymax), ...]}
        """
        result = {}
        for frame_idx, mask in self._masks.items():
            if not mask.any():
                continue
            # 找mask的边界框
            rows = np.any(mask, axis=1)
            cols = np.any(mask, axis=0)
            if rows.any() and cols.any():
                ymin, ymax = np.where(rows)[0][[0, -1]]
                xmin, xmax = np.where(cols)[0][[0, -1]]
                result[frame_idx + 1] = [(int(xmin), int(xmax), int(ymin), int(ymax))]  # 1-based frame number
        return result
