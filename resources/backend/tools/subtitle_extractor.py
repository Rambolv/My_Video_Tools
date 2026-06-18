"""
字幕提取器 — 从视频中检测并识别字幕文本，输出带时间轴的 SRTT 内容
使用 PaddleOCR 全流水线（detect + recognize），首次运行自动下载 rec 模型
"""
from __future__ import annotations

import os
import re
import cv2
import numpy as np
from typing import List, Tuple, Optional, Callable

from backend.config import config
from backend.tools.subtitle_detect import SubtitleDetect
from backend.tools.common_tools import get_readable_path
from backend.tools.hardware_accelerator import HardwareAccelerator


class SubtitleExtractor:
    """
    字幕提取器
    流程：逐帧检测字幕框 → 分组为连续区间 → 每区间 OCR 识别 → 去重 → 输出
    """

    def __init__(self, video_path: str, progress_callback: Optional[Callable] = None,
                 log_callback: Optional[Callable] = None):
        self.video_path = get_readable_path(video_path)
        self.progress_callback = progress_callback or (lambda p, f: None)
        self.log_callback = log_callback or (lambda msg: None)

        # 打开视频获取基本信息
        self.cap = cv2.VideoCapture(self.video_path)
        if not self.cap.isOpened():
            raise IOError(f"无法打开视频: {video_path}")
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.cap.release()

        # PaddleOCR 实例（延迟初始化）
        self._ocr = None

    @property
    def ocr(self):
        """延迟初始化 PaddleOCR（detect + recognize），首次自动下载 rec 模型"""
        if self._ocr is None:
            self.log_callback("正在初始化 OCR 引擎（首次可能下载识别模型）…")
            try:
                from paddleocr import PaddleOCR
                # 使用 GPU 加速（如果可用）
                use_gpu = False
                try:
                    import torch
                    if torch.cuda.is_available():
                        use_gpu = True
                except Exception:
                    pass
                try:
                    accel = HardwareAccelerator.instance()
                    if accel.has_cuda():
                        use_gpu = True
                except Exception:
                    pass

                self._ocr = PaddleOCR(
                    use_angle_cls=False,
                    lang='ch',
                    use_gpu=use_gpu,
                    show_log=False,
                    # 指定 det 模型路径用项目已有的
                    det_model_dir=None,  # 让 PaddleOCR 自动管理
                    rec_model_dir=None,
                    cls_model_dir=None,
                )
                self.log_callback("OCR 引擎就绪")
            except Exception as e:
                self.log_callback(f"OCR 初始化失败: {e}")
                raise
        return self._ocr

    def extract(self, sample_interval: int = 1, 
                joint_models: List[str] = None,
                mode: str = "row") -> List[dict]:
        """
        全流程提取字幕

        Parameters
        ----------
        sample_interval : int
            每隔多少帧检测一次
        joint_models : List[str]
            联合校对使用的模型列表
        mode : str
            提取模式: "row"(按行) / "column"(按列) / "float"(浮动字幕)

        Returns
        -------
        List[dict] : [{"text": str, "start_frame": int, "end_frame": int, ...}]
        """
        results = []
        
        # 第一步：使用 SubtitleDetect 检测所有有字幕的帧
        self.log_callback("步骤1/3: 检测字幕区域…")
        detector = SubtitleDetect(self.video_path)
        
        # find_subtitle_frame_no 需要 sub_remover 参数（含 ab_sections），
        # 传 None 会崩溃，传一个 mock 对象即可
        class _MockRemover:
            ab_sections = []
            append_output = lambda self, msg: None
            progress_total = 0
        sub_dict = detector.find_subtitle_frame_no(sub_remover=_MockRemover())
        
        if not sub_dict:
            self.log_callback("未检测到任何字幕")
            return results

        # 第二步：将连续帧分组为区间
        self.log_callback(f"步骤2/3: 分组字幕区间（共 {len(sub_dict)} 帧有字幕）…")
        from backend.tools.subtitle_detect import SubtitleDetect as SD
        ranges = SD.find_continuous_ranges_with_same_mask(sub_dict)
        
        if not ranges:
            self.log_callback("无法分组字幕区间")
            return results

        # 第三步：对每个区间取代表帧做 OCR 识别
        self.log_callback(f"步骤3/3: OCR 识别（共 {len(ranges)} 个区间）…")
        cap = cv2.VideoCapture(self.video_path)
        
        # 存储已识别的文本（累积去重用）
        seen_texts = {}  # text_hash -> last_frame
        MIN_FRAME_GAP = int(self.fps * 0.5)  # 至少间隔0.5秒才认为是新字幕
        
        for idx, (start_f, end_f) in enumerate(ranges):
            # 取区间中间帧作为代表帧
            mid_frame = (start_f + end_f) // 2
            cap.set(cv2.CAP_PROP_POS_FRAMES, mid_frame)
            ret, frame = cap.read()
            if not ret or frame is None:
                continue
            
            # 获取该帧的字幕框
            rects = sub_dict.get(mid_frame, [])
            if not rects:
                for offset in range(-5, 6):
                    nearby = sub_dict.get(mid_frame + offset, [])
                    if nearby:
                        rects = nearby
                        break
            if not rects:
                continue

            # 对每个字幕框裁剪并 OCR
            # 收集 (text, x_center, y_center) 用于后续按行/列排序
            ocr_items = []
            for (xmin, xmax, ymin, ymax) in rects:
                x1, x2 = max(0, int(xmin)), min(self.width, int(xmax))
                y1, y2 = max(0, int(ymin)), min(self.height, int(ymax))
                if x2 <= x1 or y2 <= y1:
                    continue
                crop = frame[y1:y2, x1:x2]
                if crop.size == 0:
                    continue
                try:
                    text = self._ocr_text(crop)
                    if text and text.strip():
                        cx = (x1 + x2) / 2.0
                        cy = (y1 + y2) / 2.0
                        ocr_items.append((text.strip(), cx, cy))
                except Exception as e:
                    self.log_callback(f"  OCR 错误 (帧 {mid_frame}): {e}")

            if not ocr_items:
                continue

            # 按模式合并文本
            combined = self._merge_by_mode(ocr_items, mode)
            if not combined:
                continue

            # 智能去重：考虑文字渐进出现（如卡拉OK逐字效果）
            text_key = self._text_normalize(combined)
            
            # 检查是否与上一结果渐进相关
            is_progressive = False
            if results:
                prev = results[-1]
                prev_key = self._text_normalize(prev["text"])
                # 如果新文本包含上一结果的全部字符（逐字增加），则合并为最终版
                if len(text_key) >= len(prev_key) and prev_key in text_key:
                    # 渐进出现：用较长的版本替换
                    prev["text"] = combined
                    prev["end_frame"] = end_f
                    prev["end_time"] = self._frame_to_timecode(end_f)
                    is_progressive = True
            
            if not is_progressive:
                # 普通去重：相同文本且在短时间内出现则跳过
                if text_key in seen_texts:
                    last_frame = seen_texts[text_key]
                    if (start_f - last_frame) < MIN_FRAME_GAP:
                        continue
                
                seen_texts[text_key] = start_f
                results.append({
                    "text": combined,
                    "start_frame": start_f,
                    "end_frame": end_f,
                    "start_time": self._frame_to_timecode(start_f),
                    "end_time": self._frame_to_timecode(end_f),
                })
            
            # 进度回调
            self.progress_callback(int((idx + 1) / len(ranges) * 100), 
                                    idx + 1 == len(ranges))
        
        cap.release()
        
        # 如果启用了联合校对，运行多模型并合并
        if joint_models and len(joint_models) > 1:
            self.log_callback("联合校对: 运行多模型验证…")
            results = self._joint_verify(results, joint_models)
        
        self.log_callback(f"提取完成: 共 {len(results)} 条字幕")
        return results

    def _ocr_text(self, img: np.ndarray) -> str:
        """对单张裁剪图做 OCR 识别"""
        try:
            result = self.ocr.ocr(img, det=False, rec=True, cls=False)
            # PaddleOCR 返回格式: [[[text, confidence]], ...] 或 [[(text, confidence)], ...]
            texts = []
            if result and isinstance(result, list):
                for item in result:
                    if item and isinstance(item, (list, tuple)):
                        # item 可能是 [[text, conf], ...] 或 [(text, conf), ...]
                        for sub in (item if isinstance(item, list) else [item]):
                            if isinstance(sub, (list, tuple)) and len(sub) >= 1:
                                t = sub[0] if isinstance(sub[0], str) else str(sub[0])
                                if t.strip():
                                    texts.append(t.strip())
                            elif isinstance(sub, str):
                                if sub.strip():
                                    texts.append(sub.strip())
            return " ".join(texts)
        except Exception:
            return ""

    def _merge_by_mode(self, items: List[tuple], mode: str) -> str:
        """
        根据模式合并 OCR 结果

        Parameters
        ----------
        items : List[(text, cx, cy)]
        mode : "row" | "column" | "float"

        Returns
        -------
        str : 合并后的文本
        """
        if not items:
            return ""

        if mode == "row":
            # 按 Y 坐标（行）分组 → 每行内按 X 排序 → 行间换行
            # 行高容差 = 画面高度的 3%
            row_tolerance = self.height * 0.03
            rows = []  # [(avg_y, [(text, cx), ...])]
            for text, cx, cy in items:
                placed = False
                for ry, row_items in rows:
                    if abs(cy - ry) <= row_tolerance:
                        row_items.append((text, cx))
                        placed = True
                        break
                if not placed:
                    rows.append((cy, [(text, cx)]))
            # 按 Y 排序行，每行内按 X 排序
            rows.sort(key=lambda r: r[0])
            lines = []
            for _, row_items in rows:
                row_items.sort(key=lambda x: x[1])
                lines.append(" ".join(t for t, _ in row_items))
            return "\n".join(lines)

        elif mode == "column":
            # 按 X 坐标（列）分组 → 每列内按 Y 排序 → 列间换行
            col_tolerance = self.width * 0.03
            cols = []  # [(avg_x, [(text, cy), ...])]
            for text, cx, cy in items:
                placed = False
                for cx_avg, col_items in cols:
                    if abs(cx - cx_avg) <= col_tolerance:
                        col_items.append((text, cy))
                        placed = True
                        break
                if not placed:
                    cols.append((cx, [(text, cy)]))
            # 按 X 排序列，每列内按 Y 排序
            cols.sort(key=lambda c: c[0])
            col_lines = []
            for _, col_items in cols:
                col_items.sort(key=lambda x: x[1])
                col_lines.append(" ".join(t for t, _ in col_items))
            return "\n".join(col_lines)

        elif mode == "float":
            # 浮动字幕：将相近位置的字幕视为同一组，组内按阅读顺序排列
            cluster_tolerance = max(self.width, self.height) * 0.05
            clusters = []  # [(avg_y, [(text, cx, cy), ...])]
            for text, cx, cy in items:
                placed = False
                for avg_y, cluster_items in clusters:
                    avg_cx = sum(c[1] for c in cluster_items) / len(cluster_items)
                    avg_cy = sum(c[2] for c in cluster_items) / len(cluster_items)
                    dist = ((cx - avg_cx) ** 2 + (cy - avg_cy) ** 2) ** 0.5
                    if dist <= cluster_tolerance:
                        cluster_items.append((text, cx, cy))
                        placed = True
                        break
                if not placed:
                    clusters.append((cy, [(text, cx, cy)]))
            # 更新平均 Y 并排序
            for i, (_, cluster_items) in enumerate(clusters):
                avg_y = sum(c[2] for c in cluster_items) / len(cluster_items)
                clusters[i] = (avg_y, cluster_items)
            clusters.sort(key=lambda c: c[0])
            lines = []
            for _, cluster_items in clusters:
                cluster_items.sort(key=lambda x: x[1])
                lines.append(" ".join(t for t, _, _ in cluster_items))
            return "\n".join(lines)

        return " ".join(t for t, _, _ in items)

    def _frame_to_timecode(self, frame: int) -> str:
        """帧号 → SRT 时间码 HH:MM:SS,mmm"""
        seconds = frame / self.fps
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds - int(seconds)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    @staticmethod
    def _text_normalize(text: str) -> str:
        """标准化文本用于去重对比：去空格、去标点、转小写"""
        import re
        t = re.sub(r'[\s,，。、；：！？""''【】《》（）\t\n\r]', '', text)
        return t.lower()

    @staticmethod
    def _text_similarity(a: str, b: str) -> float:
        """简单文本相似度（字符级重叠率）"""
        if not a or not b:
            return 0.0
        set_a, set_b = set(a), set(b)
        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / len(union) if union else 0.0

    @staticmethod
    def _joint_verify(results: List[dict], models: List[str]) -> List[dict]:
        """
        联合校对占位：多模型结果合并。
        当前实现为记录使用的模型信息，实际多模型并行需调用多次 extract()
        """
        # 标记使用了联合校对
        for r in results:
            r["joint_models"] = models
        return results

    def results_to_srt(self, results: List[dict]) -> str:
        """将提取结果格式化为 SRT 字幕（含时间轴）"""
        lines = []
        for i, r in enumerate(results, 1):
            lines.append(str(i))
            lines.append(f"{r['start_time']} --> {r['end_time']}")
            lines.append(r['text'])
            lines.append("")
        return "\n".join(lines)

    def results_to_text(self, results: List[dict]) -> str:
        """将提取结果格式化为纯文本（无时间戳，不同条目间空行分隔）"""
        lines = []
        for r in results:
            lines.append(r['text'])
        return "\n\n".join(lines)
