import os
import sys
from functools import cached_property

# 确保 FFmpeg 单线程解码 + 错误容忍，避免子进程退出时的线程竞态条件
os.environ.setdefault('OPENCV_FFMPEG_THREADS', '1')
os.environ.setdefault('OPENCV_FFMPEG_CAPTURE_OPTIONS', 'err_detect;ignore_err|flags2;showall')

import cv2
import numpy as np
from tqdm import tqdm

from .model_config import ModelConfig
from .hardware_accelerator import HardwareAccelerator
from .common_tools import get_readable_path
from .ocr import get_coordinates
from backend.config import config, tr
from backend.scenedetect import scene_detect
from backend.scenedetect.detectors import ContentDetector
from backend.tools.inpaint_tools import is_frame_number_in_ab_sections

class SubtitleDetect:
    """
    文本框检测类，用于检测视频帧中是否存在文本框

    支持两种检测模式：
    1. OCR 文本检测（默认，检测字幕文本）
    2. 水印模板匹配（检测变形 Logo 水印）
    """

    def __init__(self, video_path, sub_areas=[]):
        self.video_path = video_path
        self.sub_areas = sub_areas
        # 水印检测缓存与采样控制
        self._watermark_cache = {}  # {frame_no: [rects]} 缓存已检测的水印位置
        self._watermark_sample_interval = 30  # 每N帧采样一次水印检测
        self._watermark_last_sample_frame = -999  # 上次采样的帧号
        self._watermark_cached_result = None  # 最近一次检测结果（用于帧间复用）

    @cached_property
    def text_detector(self):
        import paddle
        paddle.disable_signal_handler()
        from paddleocr.tools.infer import utility
        from paddleocr.tools.infer.predict_det import TextDetector
        hardware_accelerator = HardwareAccelerator.instance()
        onnx_providers = hardware_accelerator.onnx_providers
        model_config = ModelConfig()
        parser = utility.init_args()
        args = parser.parse_args([])
        args.det_algorithm = 'DB'
        args.det_model_dir = os.path.join(model_config.DET_MODEL_DIR, 'inference.onnx') if len(onnx_providers) > 0 else model_config.DET_MODEL_DIR
        args.use_gpu=False
        args.use_onnx=len(onnx_providers) > 0
        args.onnx_providers=onnx_providers
        return TextDetector(args)

    @cached_property
    def watermark_detector(self):
        """
        获取水印检测器实例（惰性加载）

        仅在启用水印检测且提供了模板路径时加载
        """
        if not config.enableWatermarkDetection.value:
            return None
        template_path = config.watermarkTemplatePath.value
        if not template_path or not os.path.exists(template_path):
            return None
        try:
            from backend.tools.watermark_detect import WatermarkDetector
            detector = WatermarkDetector(
                template_path=template_path,
                match_threshold=config.watermarkMatchThreshold.value,
                scale_range=(
                    config.watermarkScaleMin.value,
                    config.watermarkScaleMax.value,
                ),
                scale_steps=config.watermarkScaleSteps.value,
                rotation_range=(
                    config.watermarkRotationMin.value,
                    config.watermarkRotationMax.value,
                ),
                rotation_steps=config.watermarkRotationSteps.value,
                enable_perspective=config.watermarkEnablePerspective.value,
                enable_feature_match=config.watermarkEnableFeatureMatch.value,
                max_results=config.watermarkMaxResults.value,
                target_region=None,
            )
            return detector
        except Exception:
            return None

    def detect_subtitle(self, img):
        temp_list = []
        dt_boxes, elapse = self.text_detector(img)
        coordinate_list = get_coordinates(dt_boxes.tolist())
        if coordinate_list:
            for coordinate in coordinate_list:
                xmin, xmax, ymin, ymax = coordinate
                if self.sub_areas is not None and len(self.sub_areas) > 0:
                    for sub_area in self.sub_areas:
                        s_ymin, s_ymax, s_xmin, s_xmax = sub_area
                        if (s_xmin <= xmin and xmax <= s_xmax
                                and s_ymin <= ymin
                                and ymax <= s_ymax):
                            temp_list.append((xmin, xmax, ymin, ymax))
                else:
                    temp_list.append((xmin, xmax, ymin, ymax))
        return temp_list

    def detect_subtitle_with_watermark(self, img, frame_no=None):
        """
        增强版检测：OCR 文本检测 + 水印模板匹配（智能采样）

        性能优化策略：
        - OCR 找到文字时直接返回，跳过水印检测（文字区域已覆盖）
        - 水印检测仅每N帧采样一次，结果缓存复用
        - 采样时使用快速模式（仅多尺度旋转匹配，跳过高开销策略）

        Returns:
            List[Tuple[int, int, int, int]]: 混合检测结果
        """
        # 1. OCR 文本检测
        ocr_results = self.detect_subtitle(img)

        # OCR 找到结果 → 直接返回，不跑水印检测（字幕/文字已覆盖）
        if len(ocr_results) > 0:
            return ocr_results

        # 2. 水印模板检测（仅 OCR 无结果时采样运行）
        detector = self.watermark_detector
        if detector is None:
            return ocr_results  # 未配置水印检测，返回空

        # 采样控制：每 N 帧重新检测一次，其余帧复用缓存
        current_frame = frame_no if frame_no is not None else 0
        need_sample = (
            current_frame - self._watermark_last_sample_frame
            >= self._watermark_sample_interval
        )

        if need_sample:
            # 执行快速水印检测
            try:
                watermark_rects = self._fast_watermark_detect(detector, img)
                self._watermark_cached_result = watermark_rects
                self._watermark_last_sample_frame = current_frame
            except Exception:
                watermark_rects = self._watermark_cached_result or []
        else:
            # 复用缓存
            watermark_rects = self._watermark_cached_result or []

        # 3. 应用子区域过滤
        watermark_results = []
        for xmin, xmax, ymin, ymax in watermark_rects:
            if self.sub_areas is not None and len(self.sub_areas) > 0:
                for sub_area in self.sub_areas:
                    s_ymin, s_ymax, s_xmin, s_xmax = sub_area
                    if (s_xmin <= xmin and xmax <= s_xmax
                            and s_ymin <= ymin and ymax <= s_ymax):
                        watermark_results.append((xmin, xmax, ymin, ymax))
                        break
            else:
                watermark_results.append((xmin, xmax, ymin, ymax))

        return watermark_results

    def _fast_watermark_detect(self, detector, img):
        """
        快速水印检测：仅使用轻量级多尺度旋转匹配
        跳过透视检测和特征点匹配（这两种极其耗时）
        """
        # 直接调用 detector 的内部快速方法
        # 仅做旋转模板匹配（最快且最常用）
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        # 先缩放图像以提高速度（缩小到 640 宽度）
        h, w = gray.shape[:2]
        fast_scale = 1.0
        if w > 640:
            fast_scale = 640.0 / w
            new_w = 640
            new_h = int(h * fast_scale)
            gray = cv2.resize(gray, (new_w, new_h))

        # 仅用旋转模板匹配，使用更少的步数
        results = detector._detect_by_rotated_template(gray)

        # 将坐标缩放回原始尺寸
        rects = []
        for r in results:
            if r.polygon is not None:
                x_coords = r.polygon[:, 0] / fast_scale
                y_coords = r.polygon[:, 1] / fast_scale
                rects.append((
                    int(np.min(x_coords)),
                    int(np.max(x_coords)),
                    int(np.min(y_coords)),
                    int(np.max(y_coords)),
                ))
        return rects

    @staticmethod
    def _compute_rect_iou(rect_a, rect_b):
        """计算两个轴对齐矩形的 IoU"""
        ax1, ax2, ay1, ay2 = rect_a
        bx1, bx2, by1, by2 = rect_b

        ix1 = max(ax1, bx1)
        iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2)
        iy2 = min(ay2, by2)

        if ix1 >= ix2 or iy1 >= iy2:
            return 0.0

        inter_area = (ix2 - ix1) * (iy2 - iy1)
        area_a = (ax2 - ax1) * (ay2 - ay1)
        area_b = (bx2 - bx1) * (by2 - by1)
        union_area = area_a + area_b - inter_area

        if union_area <= 0:
            return 0.0
        return inter_area / union_area

    @staticmethod
    def detect_watermark_polygons(img, watermark_detector):
        """
        使用水印检测器获取多边形格式的结果

        Returns:
            List[np.ndarray]: 每个元素为 (N, 2) 的多边形坐标
        """
        if watermark_detector is None:
            return []
        try:
            results = watermark_detector.detect(img)
            polygons = [r.polygon for r in results if r.polygon is not None]
            return polygons
        except Exception:
            return []

    def find_subtitle_frame_no(self, sub_remover=None):
        video_cap = cv2.VideoCapture(get_readable_path(self.video_path))
        frame_count = video_cap.get(cv2.CAP_PROP_FRAME_COUNT)
        tbar = tqdm(total=int(frame_count), unit='frame', position=0, file=sys.__stdout__, desc='Subtitle Finding')
        current_frame_no = 0
        subtitle_frame_no_box_dict = {}
        if sub_remover:
            sub_remover.append_output(tr['Main']['ProcessingStartFindingSubtitles'])
        while video_cap.isOpened():
            ret, frame = video_cap.read()
            # 如果读取视频帧失败（视频读到最后一帧）
            if not ret:
                break
            # 读取视频帧成功
            current_frame_no += 1
            if not is_frame_number_in_ab_sections(current_frame_no - 1, sub_remover.ab_sections):
                tbar.update(1)
                continue
            temp_list = self.detect_subtitle_with_watermark(frame, current_frame_no)
            if len(temp_list) > 0:
                subtitle_frame_no_box_dict[current_frame_no] = temp_list
            tbar.update(1)
            if sub_remover:
                sub_remover.progress_total = (100 * float(current_frame_no) / float(frame_count)) // 2
        # ---- 二遍扫描：邻近帧全策略水印检测 ----
        if self.watermark_detector is not None and len(subtitle_frame_no_box_dict) > 0:
            fps = video_cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                fps = 30.0
            proximity_frames = int(config.watermarkProximityWindowSeconds.value * fps)
            if proximity_frames > 0:
                tbar.write(f'Proximity watermark scan: ±{proximity_frames} frames around text-detected frames')
                subtitle_frame_no_box_dict = self._proximity_watermark_scan(
                    video_cap, subtitle_frame_no_box_dict,
                    frame_count, proximity_frames, sub_remover
                )
        video_cap.release()
        
        subtitle_frame_no_box_dict = self.unify_regions(subtitle_frame_no_box_dict)
        if sub_remover:
            sub_remover.append_output(tr['Main']['FinishedFindingSubtitles'])
        new_subtitle_frame_no_box_dict = dict()
        for key in subtitle_frame_no_box_dict.keys():
            if len(subtitle_frame_no_box_dict[key]) > 0:
                new_subtitle_frame_no_box_dict[key] = subtitle_frame_no_box_dict[key]
        return new_subtitle_frame_no_box_dict

    def _proximity_watermark_scan(self, video_cap, frame_box_dict, total_frames,
                                   proximity_frames, sub_remover=None):
        """
        邻近帧全策略水印扫描 + 颜色传播检测

        1. 模板匹配全策略检测
        2. 提取文字颜色，邻近帧同色块传播检测
        """
        text_frames = sorted(frame_box_dict.keys())
        scan_frame_set = set()
        for tf in text_frames:
            start = max(1, tf - proximity_frames)
            end = min(int(total_frames), tf + proximity_frames)
            for fn in range(start, end + 1):
                if fn not in frame_box_dict:
                    scan_frame_set.add(fn)

        if not scan_frame_set:
            return frame_box_dict

        scan_frames = sorted(scan_frame_set)

        # ---- 颜色传播：提取文字颜色 -------
        text_colors = []
        if config.watermarkColorPropagationEnabled.value:
            text_colors = self._extract_text_colors(video_cap, frame_box_dict)

        tbar = tqdm(total=len(scan_frames), unit='frame', position=0,
                     file=sys.__stdout__, desc='Proximity Watermark Scan')

        detector = self._get_full_strategy_detector()
        color_tolerance = config.watermarkColorTolerance.value
        color_min_area = config.watermarkColorMinArea.value
        has_color_propagation = (
            config.watermarkColorPropagationEnabled.value
            and len(text_colors) > 0
        )

        for frame_no in scan_frames:
            video_cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no - 1)
            ret, frame = video_cap.read()
            if not ret:
                tbar.update(1)
                continue

            try:
                all_rects = []

                # 策略A: 全策略模板匹配
                if detector is not None:
                    results = detector.detect(frame)
                    for r in results:
                        if r.polygon is not None:
                            xc = r.polygon[:, 0]
                            yc = r.polygon[:, 1]
                            all_rects.append((
                                int(np.min(xc)), int(np.max(xc)),
                                int(np.min(yc)), int(np.max(yc)),
                            ))

                # 策略B: 颜色传播检测 🆕
                if has_color_propagation:
                    for tc in text_colors:
                        color_rects = self._find_same_color_regions(
                            frame, tc, color_tolerance, color_min_area
                        )
                        all_rects.extend(color_rects)
                # 策略C: 水印强力清扫
                if config.watermarkPowerSweepEnabled.value:
                    sweep_rects = self._power_sweep_detect(
                        video_cap, frame_no, frame_box_dict,
                        total_frames
                    )
                    all_rects.extend(sweep_rects)

                # 策略D: 水印区域全部清扫
                if config.watermarkRegionFullSweepEnabled.value:
                    region_rects = self._region_full_sweep(
                        frame_no, frame_box_dict, proximity_frames
                    )
                    all_rects.extend(region_rects)

                # 策略E: 强制清理区域水印（全宽水平条覆盖）
                if config.watermarkForceRegionInpaintEnabled.value:
                    force_rects = self._force_region_inpaint(
                        frame_no, frame_box_dict, proximity_frames, frame
                    )
                    all_rects.extend(force_rects)

                # 去重合并
                all_rects = self._deduplicate_rects(all_rects)

                # 应用子区域过滤
                filtered = []
                for xmin, xmax, ymin, ymax in all_rects:
                    if self.sub_areas is not None and len(self.sub_areas) > 0:
                        for sa in self.sub_areas:
                            s_ymin, s_ymax, s_xmin, s_xmax = sa
                            if (s_xmin <= xmin and xmax <= s_xmax
                                    and s_ymin <= ymin and ymax <= s_ymax):
                                filtered.append((xmin, xmax, ymin, ymax))
                                break
                    else:
                        filtered.append((xmin, xmax, ymin, ymax))

                if filtered:
                    frame_box_dict[frame_no] = filtered
            except Exception:
                pass

            tbar.update(1)
            if sub_remover:
                sub_remover.progress_total = 50 + (50 * tbar.n / len(scan_frames))

        tbar.close()
        return frame_box_dict

    def _extract_text_colors(self, video_cap, frame_box_dict):
        """
        从检测到文字的帧中提取文字颜色

        Returns:
            List[Tuple[int, int, int]]: 提取到的文字颜色列表 (B, G, R)
        """
        colors = []
        max_samples = 10  # 最多采样10帧
        text_frames = sorted(frame_box_dict.keys())
        sample_frames = text_frames[::max(1, len(text_frames) // max_samples)][:max_samples]

        for frame_no in sample_frames:
            boxes = frame_box_dict.get(frame_no, [])
            if not boxes:
                continue
            video_cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no - 1)
            ret, frame = video_cap.read()
            if not ret:
                continue

            h, w = frame.shape[:2]
            for xmin, xmax, ymin, ymax in boxes:
                x1 = max(0, int(xmin))
                x2 = min(w, int(xmax))
                y1 = max(0, int(ymin))
                y2 = min(h, int(ymax))
                if x2 <= x1 or y2 <= y1:
                    continue
                roi = frame[y1:y2, x1:x2]
                if roi.size == 0:
                    continue

                # 使用 K-Means 找主导颜色（排除过暗/过亮的背景）
                pixels = roi.reshape(-1, 3).astype(np.float32)
                if len(pixels) < 10:
                    continue

                # 过滤掉太暗（背景）和太亮（高光）的像素
                brightness = np.mean(pixels, axis=1)
                mask = (brightness > 30) & (brightness < 240)
                filtered_pixels = pixels[mask]
                if len(filtered_pixels) < 5:
                    continue

                # K-Means 聚类找主导色
                criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
                k = min(3, len(filtered_pixels) // 5)
                if k < 1:
                    k = 1
                try:
                    _, labels, centers = cv2.kmeans(
                        filtered_pixels, k, None, criteria, 3,
                        cv2.KMEANS_RANDOM_CENTERS
                    )
                    # 取最大簇的颜色
                    if labels is not None and len(labels) > 0:
                        unique, counts = np.unique(labels, return_counts=True)
                        dominant_idx = unique[np.argmax(counts)]
                        dominant_color = tuple(int(c) for c in centers[dominant_idx])
                        if dominant_color not in colors:
                            colors.append(dominant_color)
                except Exception:
                    pass

        return colors

    def _find_same_color_regions(self, frame, target_color, tolerance, min_area):
        """
        在帧中查找与目标颜色相同的连通区域

        Args:
            frame: BGR 图像
            target_color: (B, G, R) 目标颜色
            tolerance: 颜色容差 (0-100)
            min_area: 最小连通区域面积

        Returns:
            List[Tuple[int, int, int, int]]: 检测到的矩形区域
        """
        h, w = frame.shape[:2]
        # 转为 HSV 做颜色匹配（对光照变化更鲁棒）
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        target_bgr = np.uint8([[target_color]])
        target_hsv = cv2.cvtColor(target_bgr, cv2.COLOR_BGR2HSV)[0, 0]

        # 在 HSV 空间构建范围
        t = tolerance  # 0-100 -> 映射到 HSV 范围
        h_tol = t * 1.8  # H: 0-360, 按比例放大
        s_tol = t * 2.55  # S: 0-255
        v_tol = t * 2.55  # V: 0-255

        h_low = max(0, int(target_hsv[0]) - int(h_tol))
        h_high = min(180, int(target_hsv[0]) + int(h_tol))
        s_low = max(0, int(target_hsv[1]) - int(s_tol))
        s_high = min(255, int(target_hsv[1]) + int(s_tol))
        v_low = max(0, int(target_hsv[2]) - int(v_tol))
        v_high = min(255, int(target_hsv[2]) + int(v_tol))

        lower = np.array([h_low, s_low, v_low])
        upper = np.array([h_high, s_high, v_high])

        mask = cv2.inRange(hsv, lower, upper)

        # 形态学操作：去除噪点，连接碎片
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        # 连通组件分析
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
            mask, connectivity=8
        )

        rects = []
        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            if area < min_area:
                continue
            x = stats[i, cv2.CC_STAT_LEFT]
            y = stats[i, cv2.CC_STAT_TOP]
            bw = stats[i, cv2.CC_STAT_WIDTH]
            bh = stats[i, cv2.CC_STAT_HEIGHT]
            # 过滤长宽比异常的区域（太细长或太扁可能是边缘）
            aspect_ratio = max(bw, bh) / (min(bw, bh) + 1)
            if aspect_ratio > 15:
                continue
            rects.append((x, x + bw, y, y + bh))

        return rects

    def _power_sweep_detect(self, video_cap, frame_no, frame_box_dict, total_frames):
        """
        水印强力清扫：逐帧差分检测快速变化目标

        每1帧对文字区域做差分比较，变化超过阈值的像素标记为水印目标。
        缓存优化：每个文字检测帧只计算一次，结果复用给邻近帧。
        """
        if not hasattr(self, '_sweep_cache'):
            self._sweep_cache = {}

        fps = video_cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30.0

        change_level = config.watermarkPowerSweepChangeLevel.value  # 0-255
        proximity_sec = config.watermarkProximityWindowSeconds.value
        proximity_frames = int(proximity_sec * fps)
        if proximity_frames < 3:
            return []

        text_frames = sorted(frame_box_dict.keys())
        nearest_tf = min(text_frames, key=lambda tf: abs(tf - frame_no))
        if abs(nearest_tf - frame_no) > proximity_frames:
            return []

        cache_key = (nearest_tf, proximity_frames, change_level)
        if cache_key in self._sweep_cache:
            return self._sweep_cache[cache_key]

        boxes = frame_box_dict.get(nearest_tf, [])
        if not boxes:
            self._sweep_cache[cache_key] = []
            return []

        sample_start = max(1, nearest_tf - proximity_frames)
        sample_end = min(int(total_frames), nearest_tf + proximity_frames)
        sample_nos = list(range(sample_start, sample_end + 1))  # 每1帧采样
        if len(sample_nos) < 3:
            self._sweep_cache[cache_key] = []
            return []

        all_sweep_rects = []
        h, w = 0, 0

        for xmin, xmax, ymin, ymax in boxes:
            x1 = max(0, int(xmin))
            x2 = max(x1 + 1, int(xmax))
            y1 = max(0, int(ymin))
            y2 = max(y1 + 1, int(ymax))

            # 读取所有采样帧的同一区域
            patches = []
            for sno in sample_nos:
                video_cap.set(cv2.CAP_PROP_POS_FRAMES, sno - 1)
                ret, sframe = video_cap.read()
                if not ret:
                    continue
                if h == 0:
                    h, w = sframe.shape[:2]
                    x2 = min(w, x2)
                    y2 = min(h, y2)
                ph = min(y2, sframe.shape[0]) - y1
                pw = min(x2, sframe.shape[1]) - x1
                if ph > 0 and pw > 0:
                    patch = sframe[y1:y1+ph, x1:x1+pw].astype(np.float32)
                    patches.append(patch)

            if len(patches) < 3:
                continue

            # 逐帧差分：计算相邻帧之间的绝对差值
            diff_sum = np.zeros_like(patches[0], dtype=np.float32)
            diff_count = 0
            for i in range(1, len(patches)):
                if patches[i].shape == patches[i-1].shape:
                    diff = np.abs(patches[i] - patches[i-1])
                    diff_sum += diff
                    diff_count += 1

            if diff_count == 0:
                continue

            # 平均差分 → 各通道均值 → 单通道
            avg_diff = diff_sum / diff_count
            mean_diff = np.mean(avg_diff, axis=2)  # (H, W)

            # 变化超过阈值的像素 → 快速变化目标
            change_mask = (mean_diff > change_level).astype(np.uint8) * 255

            # 形态学处理
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            change_mask = cv2.morphologyEx(change_mask, cv2.MORPH_CLOSE, kernel)
            change_mask = cv2.morphologyEx(change_mask, cv2.MORPH_OPEN, kernel)

            num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
                change_mask, connectivity=8
            )

            for i in range(1, num_labels):
                area = stats[i, cv2.CC_STAT_AREA]
                if area < 20:
                    continue
                sx = stats[i, cv2.CC_STAT_LEFT] + x1
                sy = stats[i, cv2.CC_STAT_TOP] + y1
                sw = stats[i, cv2.CC_STAT_WIDTH]
                sh = stats[i, cv2.CC_STAT_HEIGHT]
                region_area = (x2 - x1) * (y2 - y1)
                if area > region_area * 0.85:
                    continue  # 几乎整个区域都变 → 可能是场景切换，跳过
                all_sweep_rects.append((sx, sx + sw, sy, sy + sh))

        self._sweep_cache[cache_key] = all_sweep_rects
        return all_sweep_rects

    def _region_full_sweep(self, frame_no, frame_box_dict, proximity_frames):
        """
        水印区域全部清扫：将文字帧的整块区域在邻近帧中直接标记为水印

        最激进的清扫策略——只要当前帧在文字帧的 ±N 帧范围内，
        就直接把文字区域的坐标复制过来作为水印区域。
        """
        text_frames = sorted(frame_box_dict.keys())
        rects = []
        for tf in text_frames:
            if abs(tf - frame_no) <= proximity_frames:
                boxes = frame_box_dict.get(tf, [])
                rects.extend(boxes)
        return rects

    def _force_region_inpaint(self, frame_no, frame_box_dict, proximity_frames, frame):
        """
        强制清理区域水印：将文字区域原样复制到邻近帧，强制重绘

        与区域全部清扫的区别：
        - 区域全部清扫：仅在检测阶段标记坐标
        - 强制清理：相同的原样文字框坐标，确保inpaint阶段重绘
        """
        text_frames = sorted(frame_box_dict.keys())
        rects = []
        for tf in text_frames:
            if abs(tf - frame_no) <= proximity_frames:
                boxes = frame_box_dict.get(tf, [])
                rects.extend(boxes)
        return rects

    @staticmethod
    def _deduplicate_rects(rects, iou_threshold=0.4):
        """IoU去重"""
        if len(rects) <= 1:
            return rects
        keep = []
        for i, ra in enumerate(rects):
            is_dup = False
            for j, rb in enumerate(keep):
                iou = SubtitleDetect._compute_rect_iou(ra, rb)
                if iou > iou_threshold:
                    is_dup = True
                    break
            if not is_dup:
                keep.append(ra)
        return keep

    def _get_full_strategy_detector(self):
        """
        获取全策略水印检测器（根据灵敏度调整阈值）
        仅在邻近帧扫描时使用，开销较大但检测更全面
        """
        from backend.tools.watermark_detect import WatermarkDetector
        template_path = config.watermarkTemplatePath.value
        if not template_path or not os.path.exists(template_path):
            return None

        # 根据灵敏度调整匹配阈值
        sensitivity = config.watermarkDetectionSensitivity.value
        sensitivity_thresholds = {
            "low": 0.75,    # 严格：减少误检
            "medium": 0.65,  # 默认
            "high": 0.55,   # 宽松：更多检测
        }
        threshold = sensitivity_thresholds.get(sensitivity, 0.65)

        return WatermarkDetector(
            template_path=template_path,
            match_threshold=threshold,
            scale_range=(config.watermarkScaleMin.value, config.watermarkScaleMax.value),
            scale_steps=config.watermarkScaleSteps.value,
            rotation_range=(config.watermarkRotationMin.value, config.watermarkRotationMax.value),
            rotation_steps=config.watermarkRotationSteps.value,
            enable_perspective=config.watermarkEnablePerspective.value,
            enable_feature_match=config.watermarkEnableFeatureMatch.value,
            max_results=config.watermarkMaxResults.value,
            target_region=None,
        )

    @staticmethod
    def split_range_by_scene(intervals, points):
        # 确保离散值列表是有序的
        points.sort()
        # 用于存储结果区间的列表
        result_intervals = []
        # 遍历区间
        for start, end in intervals:
            # 在当前区间内的点
            current_points = [p for p in points if start <= p <= end]

            # 遍历当前区间内的离散点
            for p in current_points:
                # 如果当前离散点不是区间的起始点，添加从区间开始到离散点前一个数字的区间
                if start < p:
                    result_intervals.append((start, p - 1))
                # 更新区间开始为当前离散点
                start = p
            # 添加从最后一个离散点或区间开始到区间结束的区间
            result_intervals.append((start, end))
        # 输出结果
        return result_intervals

    @staticmethod
    def get_scene_div_frame_no(v_path):
        """
        获取发生场景切换的帧号
        """
        scene_div_frame_no_list = []
        scene_list = scene_detect(v_path, ContentDetector())
        for scene in scene_list:
            start, end = scene
            if start.frame_num == 0:
                pass
            else:
                scene_div_frame_no_list.append(start.frame_num + 1)
        return scene_div_frame_no_list

    @staticmethod
    def are_similar(region1, region2):
        """判断两个区域是否相似。"""
        xmin1, xmax1, ymin1, ymax1 = region1
        xmin2, xmax2, ymin2, ymax2 = region2

        return abs(xmin1 - xmin2) <= config.subtitleAreaPixelToleranceXPixel.value and abs(xmax1 - xmax2) <= config.subtitleAreaPixelToleranceXPixel.value and \
            abs(ymin1 - ymin2) <= config.subtitleAreaPixelToleranceYPixel.value and abs(ymax1 - ymax2) <= config.subtitleAreaPixelToleranceYPixel.value

    def unify_regions(self, raw_regions):
        """将连续相似的区域统一，保持列表结构。"""
        if len(raw_regions) > 0:
            keys = sorted(raw_regions.keys())  # 对键进行排序以确保它们是连续的
            unified_regions = {}

            # 初始化
            last_key = keys[0]
            unify_value_map = {last_key: raw_regions[last_key]}

            for key in keys[1:]:
                current_regions = raw_regions[key]

                # 新增一个列表来存放匹配过的标准区间
                new_unify_values = []

                for idx, region in enumerate(current_regions):
                    last_standard_region = unify_value_map[last_key][idx] if idx < len(unify_value_map[last_key]) else None

                    # 如果当前的区间与前一个键的对应区间相似，我们统一它们
                    if last_standard_region and self.are_similar(region, last_standard_region):
                        new_unify_values.append(last_standard_region)
                    else:
                        new_unify_values.append(region)

                # 更新unify_value_map为最新的区间值
                unify_value_map[key] = new_unify_values
                last_key = key

            # 将最终统一后的结果传递给unified_regions
            for key in keys:
                unified_regions[key] = unify_value_map[key]
            return unified_regions
        else:
            return raw_regions

    @staticmethod
    def find_continuous_ranges(subtitle_frame_no_box_dict):
        """
        获取字幕出现的起始帧号与结束帧号
        """
        numbers = sorted(list(subtitle_frame_no_box_dict.keys()))
        ranges = []
        start = numbers[0]  # 初始区间开始值

        for i in range(1, len(numbers)):
            # 如果当前数字与前一个数字间隔超过1，
            # 则上一个区间结束，记录当前区间的开始与结束
            if numbers[i] - numbers[i - 1] != 1:
                end = numbers[i - 1]  # 则该数字是当前连续区间的终点
                ranges.append((start, end))
                start = numbers[i]  # 开始下一个连续区间
        # 添加最后一个区间
        ranges.append((start, numbers[-1]))
        return ranges

    @staticmethod
    def find_continuous_ranges_with_same_mask(subtitle_frame_no_box_dict):
        numbers = sorted(list(subtitle_frame_no_box_dict.keys()))
        ranges = []
        start = numbers[0]  # 初始区间开始值
        for i in range(1, len(numbers)):
            # 如果当前帧号与前一个帧号间隔超过1，
            # 则上一个区间结束，记录当前区间的开始与结束
            if numbers[i] - numbers[i - 1] != 1:
                end = numbers[i - 1]  # 则该数字是当前连续区间的终点
                ranges.append((start, end))
                start = numbers[i]  # 开始下一个连续区间
            # 如果当前帧号与前一个帧号间隔为1，且当前帧号对应的坐标点与上一帧号对应的坐标点不一致
            # 记录当前区间的开始与结束
            if numbers[i] - numbers[i - 1] == 1:
                if subtitle_frame_no_box_dict[numbers[i]] != subtitle_frame_no_box_dict[numbers[i - 1]]:
                    end = numbers[i - 1]  # 则该数字是当前连续区间的终点
                    ranges.append((start, end))
                    start = numbers[i]  # 开始下一个连续区间
        # 添加最后一个区间
        ranges.append((start, numbers[-1]))
        return ranges

    @staticmethod
    def filter_and_merge_intervals(intervals, target_length):
        """
        合并传入的字幕起始区间，确保区间大小最低为STTN_REFERENCE_LENGTH
        """
        expanded = []
        # 首先单独处理单点区间以扩展它们
        for start, end in intervals:
            if start == end:  # 单点区间
                # 扩展到接近的目标长度，但保证前后不重叠
                prev_end = expanded[-1][1] if expanded else float('-inf')
                next_start = float('inf')
                # 查找下一个区间的起始点
                for ns, ne in intervals:
                    if ns > end:
                        next_start = ns
                        break
                # 确定新的扩展起点和终点
                new_start = max(start - (target_length - 1) // 2, prev_end + 1)
                new_end = min(start + (target_length - 1) // 2, next_start - 1)
                # 如果新的扩展终点在起点前面，说明没有足够空间来进行扩展
                if new_end < new_start:
                    new_start, new_end = start, start  # 保持原样
                expanded.append((new_start, new_end))
            else:
                # 非单点区间直接保留，稍后处理任何可能的重叠
                expanded.append((start, end))
        # 排序以合并那些因扩展导致重叠的区间
        expanded.sort(key=lambda x: x[0])
        # 合并重叠的区间，但仅当它们之间真正重叠且小于目标长度时
        merged = [expanded[0]]
        for start, end in expanded[1:]:
            last_start, last_end = merged[-1]
            # 检查是否重叠
            if start <= last_end and (end - last_start + 1 < target_length or last_end - last_start + 1 < target_length):
                # 需要合并
                merged[-1] = (last_start, max(last_end, end))  # 合并区间
            elif start == last_end + 1 and (end - last_start + 1 < target_length or last_end - last_start + 1 < target_length):
                # 相邻区间也需要合并的场景
                merged[-1] = (last_start, end)
            else:
                # 如果没有重叠且都大于目标长度，则直接保留
                merged.append((start, end))
        return merged
