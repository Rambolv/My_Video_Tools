"""
变形视频水印检测模块

支持：
- 多尺度模板匹配（缩放不变性）
- 多角度旋转匹配（旋转不变性）
- 透视变换匹配（透视变形不变性）
- 特征点匹配（SIFT/ORB 作为备选方案）
- 多边形/旋转矩形输出

用于检测视频中经过缩放、旋转、透视变换的 Logo 水印。
"""

import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional


@dataclass
class WatermarkDetectResult:
    """水印检测结果"""
    # 旋转矩形的三个参数: ((cx, cy), (w, h), angle)
    rotated_rect: Optional[Tuple] = None
    # 四个角点 (用于透视/多边形), 顺序: 左上, 右上, 右下, 左下
    polygon: Optional[np.ndarray] = None
    # 匹配置信度 0.0~1.0
    confidence: float = 0.0
    # 检测方法: "template_rotated", "template_scaled", "feature_match", "perspective"
    method: str = ""


class WatermarkDetector:
    """
    变形水印检测器

    支持多种检测策略：
    1. 多尺度 + 多旋转 模板匹配
    2. 透视变换模板匹配
    3. 特征点匹配（SIFT/ORB）

    Usage:
        detector = WatermarkDetector(template_path='watermark_template.png')
        results = detector.detect(frame)
        for r in results:
            polygon = r.polygon  # 4个角点
    """

    def __init__(
        self,
        template_path: Optional[str] = None,
        template_img: Optional[np.ndarray] = None,
        match_threshold: float = 0.65,
        scale_range: Tuple[float, float] = (0.3, 2.0),
        scale_steps: int = 15,
        rotation_range: Tuple[float, float] = (-45.0, 45.0),
        rotation_steps: int = 18,
        enable_perspective: bool = True,
        enable_feature_match: bool = True,
        max_results: int = 8,
        target_region: Optional[Tuple[int, int, int, int]] = None,  # (ymin, ymax, xmin, xmax)
    ):
        """
        Args:
            template_path: 水印模板图片路径
            template_img: 水印模板图像 (BGR numpy array)，与 template_path 二选一
            match_threshold: 匹配阈值 (0.0~1.0)，越高越严格
            scale_range: 缩放范围 (min_scale, max_scale)
            scale_steps: 缩放的步数
            rotation_range: 旋转角度范围 (min_angle, max_angle) 单位：度
            rotation_steps: 旋转角度的步数
            enable_perspective: 是否启用透视变换检测
            enable_feature_match: 是否启用特征点匹配
            max_results: 每帧最多返回的结果数
            target_region: 限定检测区域 (ymin, ymax, xmin, xmax)，None 表示全图
        """
        self.match_threshold = match_threshold
        self.scale_range = scale_range
        self.scale_steps = scale_steps
        self.rotation_range = rotation_range
        self.rotation_steps = rotation_steps
        self.enable_perspective = enable_perspective
        self.enable_feature_match = enable_feature_match
        self.max_results = max_results
        self.target_region = target_region

        # 加载模板
        if template_img is not None:
            self.template = template_img.copy()
        elif template_path is not None:
            self.template = cv2.imread(template_path)
            if self.template is None:
                raise FileNotFoundError(f"无法加载水印模板: {template_path}")
        else:
            raise ValueError("必须提供 template_path 或 template_img")

        # 转换为灰度图用于模板匹配
        if len(self.template.shape) == 3:
            self.template_gray = cv2.cvtColor(self.template, cv2.COLOR_BGR2GRAY)
        else:
            self.template_gray = self.template.copy()

        # 初始化特征检测器
        if self.enable_feature_match:
            self._init_feature_detector()

    def _init_feature_detector(self):
        """初始化特征点检测器"""
        try:
            self.sift = cv2.SIFT_create()
            self.use_sift = True
        except Exception:
            # 如果 SIFT 不可用，回退到 ORB
            self.orb = cv2.ORB_create(nfeatures=2000)
            self.use_sift = False

        # 计算模板的特征点和描述子
        if self.use_sift:
            self.template_kp, self.template_des = self.sift.detectAndCompute(
                self.template_gray, None
            )
            if len(self.template_kp) < 4:
                self.enable_feature_match = False
            else:
                flann_index = 1  # SIFT 使用 KD-Tree
                index_params = dict(algorithm=flann_index, trees=5)
                search_params = dict(checks=50)
                self.flann = cv2.FlannBasedMatcher(index_params, search_params)
        else:
            self.template_kp, self.template_des = self.orb.detectAndCompute(
                self.template_gray, None
            )
            if len(self.template_kp) < 4:
                self.enable_feature_match = False
            else:
                self.bf_matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)

    def _crop_frame(self, frame: np.ndarray) -> np.ndarray:
        """根据 target_region 裁剪帧"""
        if self.target_region is None:
            return frame
        ymin, ymax, xmin, xmax = self.target_region
        h, w = frame.shape[:2]
        ymin = max(0, ymin)
        ymax = min(h, ymax)
        xmin = max(0, xmin)
        xmax = min(w, xmax)
        return frame[ymin:ymax, xmin:xmax]

    def _offset_polygon(self, polygon: np.ndarray, offset_x: int, offset_y: int) -> np.ndarray:
        """将裁剪区域内的坐标偏移回原图坐标"""
        result = polygon.copy().astype(np.float32)
        result[:, 0] += offset_x
        result[:, 1] += offset_y
        return result

    def detect(self, frame: np.ndarray) -> List[WatermarkDetectResult]:
        """
        检测帧中的所有水印

        Args:
            frame: 输入帧 (BGR)

        Returns:
            检测结果列表，按置信度降序排列
        """
        results = []

        # 裁剪到目标区域
        offset_x, offset_y = 0, 0
        if self.target_region is not None:
            ymin, ymax, xmin, xmax = self.target_region
            offset_x, offset_y = xmin, ymin
            crop = self._crop_frame(frame)
        else:
            crop = frame

        if len(crop.shape) == 3:
            crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        else:
            crop_gray = crop.copy()

        # 策略1: 多尺度 + 多旋转 模板匹配
        rotated_results = self._detect_by_rotated_template(crop_gray)
        for r in rotated_results:
            if r.polygon is not None and offset_x + offset_y > 0:
                r.polygon = self._offset_polygon(r.polygon, offset_x, offset_y)
            results.append(r)

        # 策略2: 透视变换检测
        if self.enable_perspective:
            persp_results = self._detect_by_perspective(crop_gray)
            for r in persp_results:
                if r.polygon is not None and offset_x + offset_y > 0:
                    r.polygon = self._offset_polygon(r.polygon, offset_x, offset_y)
                results.append(r)

        # 策略3: 特征点匹配
        if self.enable_feature_match:
            feat_results = self._detect_by_feature_match(crop_gray)
            for r in feat_results:
                if r.polygon is not None and offset_x + offset_y > 0:
                    r.polygon = self._offset_polygon(r.polygon, offset_x, offset_y)
                results.append(r)

        # 按置信度排序并限制数量
        results.sort(key=lambda x: x.confidence, reverse=True)
        # NMS: 去除重叠的检测结果
        results = self._non_max_suppression(results)
        return results[: self.max_results]

    def _detect_by_rotated_template(
        self, gray_frame: np.ndarray
    ) -> List[WatermarkDetectResult]:
        """
        多尺度 + 多角度旋转模板匹配
        """
        results = []
        th, tw = self.template_gray.shape[:2]
        fh, fw = gray_frame.shape[:2]

        # 预计算尺度和角度列表
        scales = np.linspace(
            self.scale_range[0], self.scale_range[1], self.scale_steps
        )
        angles = np.linspace(
            self.rotation_range[0], self.rotation_range[1], self.rotation_steps
        )

        for scale in scales:
            new_w = int(tw * scale)
            new_h = int(th * scale)
            if new_w < 5 or new_h < 5:
                continue
            if new_w > fw or new_h > fh:
                continue

            scaled_template = cv2.resize(
                self.template_gray, (new_w, new_h), interpolation=cv2.INTER_LINEAR
            )

            for angle in angles:
                if abs(angle) < 1.0:
                    # 0度附近直接用缩放后的模板
                    rotated_template = scaled_template
                    rot_w, rot_h = new_w, new_h
                else:
                    # 旋转模板
                    center = (new_w // 2, new_h // 2)
                    rot_mat = cv2.getRotationMatrix2D(center, angle, 1.0)
                    # 计算旋转后的边界
                    cos = abs(rot_mat[0, 0])
                    sin = abs(rot_mat[0, 1])
                    rot_w = int(new_h * sin + new_w * cos)
                    rot_h = int(new_h * cos + new_w * sin)
                    # 调整旋转矩阵使模板居中
                    rot_mat[0, 2] += rot_w / 2 - center[0]
                    rot_mat[1, 2] += rot_h / 2 - center[1]
                    rotated_template = cv2.warpAffine(
                        scaled_template,
                        rot_mat,
                        (rot_w, rot_h),
                        flags=cv2.INTER_LINEAR,
                        borderMode=cv2.BORDER_CONSTANT,
                        borderValue=0,
                    )

                if rot_w > fw or rot_h > fh:
                    continue

                # 模板匹配
                try:
                    match_result = cv2.matchTemplate(
                        gray_frame, rotated_template, cv2.TM_CCOEFF_NORMED
                    )
                except cv2.error:
                    continue

                # 找到所有匹配位置
                locations = np.where(match_result >= self.match_threshold)
                scores = match_result[locations]

                for pt_y, pt_x, score in zip(
                    locations[0], locations[1], scores
                ):
                    # 计算旋转矩形的三个参数
                    rect_center = (
                        float(pt_x + rot_w / 2),
                        float(pt_y + rot_h / 2),
                    )
                    rect_size = (float(rot_w), float(rot_h))
                    rect_angle = angle

                    # 计算四个角点（在旋转矩形的坐标系中）
                    box = cv2.boxPoints(
                        (rect_center, rect_size, rect_angle)
                    )

                    results.append(
                        WatermarkDetectResult(
                            rotated_rect=(rect_center, rect_size, rect_angle),
                            polygon=box,
                            confidence=float(score),
                            method=f"template_rotated_s{scale:.1f}_a{angle:.0f}",
                        )
                    )

        return results

    def _detect_by_perspective(
        self, gray_frame: np.ndarray
    ) -> List[WatermarkDetectResult]:
        """
        透视变换模板匹配

        通过对模板施加随机/网格化透视变换来匹配变形的水印
        """
        results = []
        th, tw = self.template_gray.shape[:2]
        fh, fw = gray_frame.shape[:2]

        if th < 10 or tw < 10:
            return results

        # 透视变换参数网格
        # 对模板四个角施加偏移来模拟透视变形
        perspective_offsets = [
            # (偏移比例, 描述)
            (0.00, "无变形(原始比例)"),
            (0.05, "轻微透视"),
            (0.10, "中度透视"),
            (0.15, "较强透视"),
            (0.20, "强透视"),
        ]

        # 同时尝试不同缩放
        scales = np.linspace(
            max(0.3, self.scale_range[0]),
            self.scale_range[1],
            max(3, self.scale_steps // 3),
        )

        for scale in scales:
            new_w = int(tw * scale)
            new_h = int(th * scale)
            if new_w < 10 or new_h < 10 or new_w > fw or new_h > fh:
                continue

            for offset_ratio, _desc in perspective_offsets:
                max_offset = int(max(new_w, new_h) * offset_ratio)

                # 原始四个角点 (左上, 右上, 右下, 左下)
                src_pts = np.float32(
                    [[0, 0], [new_w - 1, 0], [new_w - 1, new_h - 1], [0, new_h - 1]]
                )

                # 生成透视变形的目标点，考虑几个不同的透视方向
                offset_configs = [
                    # (左上偏移, 右上偏移, 右下偏移, 左下偏移)
                    # X轴透视（水平倾斜）
                    [(0, 0), (max_offset, 0), (max_offset, 0), (0, 0)],
                    [(0, 0), (-max_offset, 0), (-max_offset, 0), (0, 0)],
                    # Y轴透视（垂直倾斜）
                    [(0, 0), (0, 0), (0, max_offset), (0, max_offset)],
                    [(0, 0), (0, 0), (0, -max_offset), (0, -max_offset)],
                    # 对角线透视
                    [(0, 0), (max_offset, 0), (max_offset, max_offset), (0, max_offset)],
                    [(0, 0), (-max_offset, 0), (-max_offset, max_offset), (0, max_offset)],
                ]

                if offset_ratio == 0.0:
                    offset_configs = [[(0, 0), (0, 0), (0, 0), (0, 0)]]

                for offsets in offset_configs:
                    dst_pts = np.float32(
                        [
                            [src_pts[0][0] + offsets[0][0], src_pts[0][1] + offsets[0][1]],
                            [src_pts[1][0] + offsets[1][0], src_pts[1][1] + offsets[1][1]],
                            [src_pts[2][0] + offsets[2][0], src_pts[2][1] + offsets[2][1]],
                            [src_pts[3][0] + offsets[3][0], src_pts[3][1] + offsets[3][1]],
                        ]
                    )

                    try:
                        M = cv2.getPerspectiveTransform(
                            src_pts, dst_pts
                        )
                        # 计算输出尺寸
                        x_coords = dst_pts[:, 0]
                        y_coords = dst_pts[:, 1]
                        out_w = int(max(x_coords) - min(x_coords))
                        out_h = int(max(y_coords) - min(y_coords))

                        if out_w < 5 or out_h < 5 or out_w > fw or out_h > fh:
                            continue

                        warped = cv2.warpPerspective(
                            cv2.resize(
                                self.template_gray, (new_w, new_h)
                            ),
                            M,
                            (out_w, out_h),
                            borderMode=cv2.BORDER_CONSTANT,
                            borderValue=0,
                        )

                        match_result = cv2.matchTemplate(
                            gray_frame, warped, cv2.TM_CCOEFF_NORMED
                        )

                        locations = np.where(
                            match_result >= self.match_threshold + 0.05
                        )
                        scores = match_result[locations]

                        for py, px, score in zip(
                            locations[0], locations[1], scores
                        ):
                            # 将检测到的角点映射回帧坐标
                            frame_polygon = dst_pts.copy()
                            frame_polygon[:, 0] += px
                            frame_polygon[:, 1] += py

                            results.append(
                                WatermarkDetectResult(
                                    polygon=frame_polygon,
                                    confidence=float(score),
                                    method=f"perspective_s{scale:.1f}",
                                )
                            )
                    except cv2.error:
                        continue

        return results

    def _detect_by_feature_match(
        self, gray_frame: np.ndarray
    ) -> List[WatermarkDetectResult]:
        """
        基于特征点的匹配检测
        使用 SIFT 或 ORB 特征点匹配来定位变形水印
        """
        results = []

        if not self.enable_feature_match:
            return results

        try:
            if self.use_sift:
                frame_kp, frame_des = self.sift.detectAndCompute(gray_frame, None)
            else:
                frame_kp, frame_des = self.orb.detectAndCompute(gray_frame, None)
        except Exception:
            return results

        if frame_des is None or len(frame_kp) < 4:
            return results

        if self.use_sift:
            try:
                matches = self.flann.knnMatch(
                    self.template_des, frame_des, k=2
                )
            except Exception:
                return results

            # Lowe's ratio test
            good_matches = []
            for match_pair in matches:
                if len(match_pair) >= 2:
                    m, n = match_pair
                    if m.distance < 0.75 * n.distance:
                        good_matches.append(m)
        else:
            try:
                raw_matches = self.bf_matcher.knnMatch(
                    self.template_des, frame_des, k=2
                )
            except Exception:
                return results

            good_matches = []
            for match_pair in raw_matches:
                if len(match_pair) >= 2:
                    m, n = match_pair
                    if m.distance < 0.75 * n.distance:
                        good_matches.append(m)

        min_match_count = 8
        if len(good_matches) >= min_match_count:
            src_pts = np.float32(
                [self.template_kp[m.queryIdx].pt for m in good_matches]
            ).reshape(-1, 1, 2)
            dst_pts = np.float32(
                [frame_kp[m.trainIdx].pt for m in good_matches]
            ).reshape(-1, 1, 2)

            try:
                # 使用 RANSAC 计算单应矩阵
                H, mask = cv2.findHomography(
                    src_pts,
                    dst_pts,
                    cv2.RANSAC,
                    ransacReprojThreshold=5.0,
                    maxIters=2000,
                )

                if H is None:
                    return results

                # 计算内点比例作为置信度
                inlier_ratio = (
                    np.sum(mask) / len(mask) if mask is not None and len(mask) > 0 else 0
                )

                if inlier_ratio < 0.3:
                    return results

                th, tw = self.template_gray.shape[:2]
                # 模板的四个角点
                template_corners = np.float32(
                    [[0, 0], [tw - 1, 0], [tw - 1, th - 1], [0, th - 1]]
                ).reshape(-1, 1, 2)

                # 变换到帧坐标
                frame_corners = cv2.perspectiveTransform(template_corners, H)
                polygon = frame_corners.reshape(-1, 2)

                results.append(
                    WatermarkDetectResult(
                        polygon=polygon,
                        confidence=float(inlier_ratio),
                        method=f"feature_match_inliers{len(good_matches)}",
                    )
                )
            except cv2.error:
                pass

        return results

    def _non_max_suppression(
        self,
        results: List[WatermarkDetectResult],
        iou_threshold: float = 0.45,
    ) -> List[WatermarkDetectResult]:
        """
        非极大值抑制，去除重叠的检测结果
        """
        if len(results) <= 1:
            return results

        keep = []
        suppressed = [False] * len(results)

        for i in range(len(results)):
            if suppressed[i]:
                continue
            keep.append(results[i])

            for j in range(i + 1, len(results)):
                if suppressed[j]:
                    continue
                iou = self._compute_polygon_iou(
                    results[i].polygon, results[j].polygon
                )
                if iou > iou_threshold:
                    suppressed[j] = True

        return keep

    def _compute_polygon_iou(
        self, poly_a: np.ndarray, poly_b: np.ndarray
    ) -> float:
        """计算两个多边形的 IoU"""
        if poly_a is None or poly_b is None:
            return 0.0

        try:
            # 获取边界框
            ax_min = int(max(0, np.min(poly_a[:, 0])))
            ay_min = int(max(0, np.min(poly_a[:, 1])))
            ax_max = int(np.max(poly_a[:, 0]))
            ay_max = int(np.max(poly_a[:, 1]))

            bx_min = int(max(0, np.min(poly_b[:, 0])))
            by_min = int(max(0, np.min(poly_b[:, 1])))
            bx_max = int(np.max(poly_b[:, 0]))
            by_max = int(np.max(poly_b[:, 1]))

            # 计算交集区域
            ix_min = max(ax_min, bx_min)
            iy_min = max(ay_min, by_min)
            ix_max = min(ax_max, bx_max)
            iy_max = min(ay_max, by_max)

            if ix_min >= ix_max or iy_min >= iy_max:
                return 0.0

            inter_area = (ix_max - ix_min) * (iy_max - iy_min)
            area_a = (ax_max - ax_min) * (ay_max - ay_min)
            area_b = (bx_max - bx_min) * (by_max - by_min)
            union_area = area_a + area_b - inter_area

            if union_area <= 0:
                return 0.0

            return inter_area / union_area
        except Exception:
            return 0.0

    def detect_as_rectangles(
        self, frame: np.ndarray
    ) -> List[Tuple[int, int, int, int]]:
        """
        便捷方法：检测并返回轴对齐矩形格式
        返回 [(xmin, xmax, ymin, ymax), ...]
        """
        results = self.detect(frame)
        rects = []
        for r in results:
            if r.polygon is not None:
                x_coords = r.polygon[:, 0]
                y_coords = r.polygon[:, 1]
                rects.append(
                    (
                        int(np.min(x_coords)),
                        int(np.max(x_coords)),
                        int(np.min(y_coords)),
                        int(np.max(y_coords)),
                    )
                )
        return rects
