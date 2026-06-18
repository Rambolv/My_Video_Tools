"""
浮动水印跟踪器 — 基于帧间差分检测移动/浮动水印，生成跟踪遮罩
适用于台标、动态水印、浮动 Logo 等场景
"""
from __future__ import annotations

import cv2
import numpy as np
from typing import List, Tuple, Optional, Callable
from backend.config import config


class WatermarkTracker:
    """
    浮动水印跟踪器

    原理：
    1. 对视频片段做帧间差分，累积静态/半静态区域
    2. 通过时间统计分析，区分水印（持续出现）与场景内容（变化）
    3. 生成水印概率图（heatmap）→ 二值遮罩
    4. 支持跨帧跟踪和遮罩传播
    """

    def __init__(self, video_path: str, sample_step: int = 5,
                 log_callback: Optional[Callable] = None):
        self.video_path = video_path
        self.sample_step = sample_step
        self.log = log_callback or (lambda msg: None)

        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            raise IOError(f"无法打开视频: {video_path}")
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.cap.release()

    def detect_floating_watermark(self) -> np.ndarray:
        """
        检测浮动水印，返回水印概率热力图 (0-255, float32)

        改进策略：
        1. 跳过场景切换帧（整帧变化过大时）
        2. 边缘稳定性分析（水印边缘持续稳定）
        3. 关注画面边缘区域（水印通常在角落）
        4. 自适应阈值

        Returns
        -------
        heatmap : np.ndarray shape (H, W), 值越高越可能是水印
        """
        self.log("水印跟踪: 采样帧间差分…")
        cap = cv2.VideoCapture(self.video_path)

        ret, prev = cap.read()
        if not ret:
            cap.release()
            return np.zeros((self.height, self.width), dtype=np.float32)

        prev_gray = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)

        # 边缘累积图：统计每帧边缘中稳定出现的部分
        stable_edge_accum = np.zeros((self.height, self.width), dtype=np.float32)
        # 帧间变化累积（用于检测场景切换）
        total_diff_accum = 0.0
        diff_count = 0
        # 有效采样帧数
        sample_count = 0
        frame_count = 0
        # 边缘历史（多帧取交集）
        edge_history = []

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame_count += 1
            if frame_count % self.sample_step != 0:
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # 计算整帧平均变化量
            frame_diff = cv2.absdiff(gray, prev_gray)
            mean_diff = np.mean(frame_diff)

            # 场景切换检测：变化过大时跳过此帧（用更宽松的阈值）
            if mean_diff > 60 and diff_count > 5:
                prev_gray = gray
                continue

            total_diff_accum += mean_diff
            diff_count += 1

            # 提取边缘
            edges = cv2.Canny(gray, 30, 100)
            edge_history.append(edges)
            # 保持最近 5 帧
            if len(edge_history) > 5:
                edge_history.pop(0)

            # 多帧边缘交集：稳定边缘（可能是水印）
            if len(edge_history) >= 2:
                stable_edges = np.min(np.array(edge_history[-2:]), axis=0)
                stable_edge_accum += stable_edges.astype(np.float32)

            prev_gray = gray
            sample_count += 1

        cap.release()

        if sample_count == 0:
            return np.zeros((self.height, self.width), dtype=np.float32)

        # 归一化稳定边缘
        heatmap = stable_edge_accum / max(sample_count, 1)

        # 应用边缘权重掩膜：水印通常在画面边缘区域
        edge_weight = np.ones((self.height, self.width), dtype=np.float32)
        # 中心区域降权
        cy, cx = self.height // 2, self.width // 2
        Y, X = np.ogrid[:self.height, :self.width]
        dist_from_center = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
        max_dist = np.sqrt(cx ** 2 + cy ** 2)
        center_weight = 1.0 - (dist_from_center / max_dist) * 0.5
        center_weight = np.clip(center_weight, 0.5, 1.0)
        heatmap = heatmap * center_weight

        # 归一化到 0-255
        if heatmap.max() > 0:
            heatmap = (heatmap / heatmap.max() * 255).astype(np.uint8)
        else:
            heatmap = np.zeros((self.height, self.width), dtype=np.uint8)

        # 高斯模糊
        heatmap = cv2.GaussianBlur(heatmap, (7, 7), 2.0)

        # 自适应阈值已交由 heatmap_to_mask 处理，此处不再过滤
        self.log(f"水印跟踪完成: 采样 {sample_count} 帧，跳过 {frame_count - sample_count} 帧")
        return heatmap

    def heatmap_to_mask(self, heatmap: np.ndarray,
                        threshold: float = 0.3) -> np.ndarray:
        """
        将水印热力图转为二值遮罩 — 使用自适应阈值

        Parameters
        ----------
        heatmap : np.ndarray
        threshold : float 0-1, 相对于热力图最大值的比例

        Returns
        -------
        mask : np.ndarray shape (H, W), uint8, 0/255
        """
        if heatmap.max() == 0:
            return np.zeros((self.height, self.width), dtype=np.uint8)

        # 自适应阈值：相对于热力图最大值
        abs_threshold = max(heatmap.max() * threshold, 5)
        _, mask = cv2.threshold(heatmap, abs_threshold, 255, cv2.THRESH_BINARY)
        mask = mask.astype(np.uint8)

        # 形态学操作：去除噪点，填充空洞
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

        return mask

    def extract_watermark_regions(self, mask: np.ndarray,
                                  min_area: int = 500) -> List[Tuple]:
        """
        从遮罩中提取水印区域矩形

        Returns
        -------
        List[(xmin, xmax, ymin, ymax), ...]
        """
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        regions = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area:
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            regions.append((x, x + w, y, y + h))
        return regions

    def track_watermark_across_frames(
            self, heatmap: np.ndarray) -> List[Tuple[int, List[Tuple]]]:
        """
        跨帧跟踪水印位置变化

        Returns
        -------
        List[(frame_no, [(xmin,xmax,ymin,ymax), ...]), ...]
        """
        mask = self.heatmap_to_mask(heatmap, threshold=0.4)
        regions = self.extract_watermark_regions(mask)

        if not regions:
            return []

        # 扩展到全视频范围
        self.log(f"检测到 {len(regions)} 个水印区域，生成全视频遮罩…")
        result = []
        # 对关键帧采样，将水印区域传播到附近帧
        cap = cv2.VideoCapture(self.video_path)
        frame_no = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame_no += 1
            # 每 30 帧做一次检测，中间帧复用
            if frame_no % 30 == 1:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                active_regions = []
                for (xmin, xmax, ymin, ymax) in regions:
                    # 在当前帧中微调水印位置（模板匹配）
                    roi = gray[ymin:ymax, xmin:xmax]
                    if roi.size == 0:
                        active_regions.append((xmin, xmax, ymin, ymax))
                        continue
                    # 在局部区域内搜索最佳匹配
                    search_margin = 20
                    search_area = gray[
                        max(0, ymin - search_margin):min(self.height, ymax + search_margin),
                        max(0, xmin - search_margin):min(self.width, xmax + search_margin)
                    ]
                    if search_area.size == 0 or search_area.shape[0] < roi.shape[0] or search_area.shape[1] < roi.shape[1]:
                        active_regions.append((xmin, xmax, ymin, ymax))
                        continue
                    try:
                        res = cv2.matchTemplate(search_area, roi, cv2.TM_CCOEFF_NORMED)
                        _, max_val, _, max_loc = cv2.minMaxLoc(res)
                        if max_val > 0.5:
                            dx = max_loc[0] - search_margin
                            dy = max_loc[1] - search_margin
                            active_regions.append((
                                max(0, xmin + dx),
                                min(self.width, xmax + dx),
                                max(0, ymin + dy),
                                min(self.height, ymax + dy)
                            ))
                        else:
                            active_regions.append((xmin, xmax, ymin, ymax))
                    except Exception:
                        active_regions.append((xmin, xmax, ymin, ymax))
            result.append((frame_no, active_regions))
        cap.release()
        return result
