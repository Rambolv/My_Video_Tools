import multiprocessing
import cv2
import numpy as np
from typing import List, Tuple, Union

from backend.config import config

def merge_deformation_mask(
    coords_list: List[Tuple[int, int, int, int]],
    frame_width: int,
    frame_height: int,
    base_expand: int = 20,
    deform_factor: float = 0.3,
) -> List[Tuple[int, int, int, int]]:
    """
    变形自适应遮罩合并 — 针对极速变形扭曲的水印文字

    原理：OCR 检测到的文字框每帧不同（水印在变形/移动）。
    本函数分析所有帧的检测框，计算水印的**变形幅度**，
    生成能覆盖全部变形范围的统一遮罩。

    计算方式：
    1. 取所有检测框的最小/最大边界作为基础范围
    2. 用检测框位置的方差估算变形幅度
    3. 额外扩展 = base_expand + deform_factor × 变形幅度
    4. 合并重叠的框为一个大区域

    Parameters
    ----------
    coords_list : List[Tuple[int,int,int,int]]
        所有帧的检测框列表，格式为 (xmin, xmax, ymin, ymax)
    frame_width : int
    frame_height : int
    base_expand : int
        基础扩展像素
    deform_factor : float
        变形幅度放大因子

    Returns
    -------
    List[Tuple[int,int,int,int]]
        合并后的遮罩坐标列表
    """
    if not coords_list:
        return []

    n = len(coords_list)
    if n == 1:
        xmin, xmax, ymin, ymax = coords_list[0]
        expand = base_expand
        return [(
            max(0, xmin - expand),
            min(frame_width, xmax + expand),
            max(0, ymin - expand),
            min(frame_height, ymax + expand),
        )]

    # 计算所有检测框的位置统计
    xs_min = np.array([c[0] for c in coords_list])
    xs_max = np.array([c[1] for c in coords_list])
    ys_min = np.array([c[2] for c in coords_list])
    ys_max = np.array([c[3] for c in coords_list])

    # 整体范围
    overall_xmin = int(np.min(xs_min))
    overall_xmax = int(np.max(xs_max))
    overall_ymin = int(np.min(ys_min))
    overall_ymax = int(np.max(ys_max))

    # 变形幅度 = 检测框在各个方向的标准差
    deform_x = float(np.std(xs_min) + np.std(xs_max)) / 2.0
    deform_y = float(np.std(ys_min) + np.std(ys_max)) / 2.0

    # 额外扩展 = base + deform_factor × 变形幅度
    extra_x = int(base_expand + deform_factor * deform_x)
    extra_y = int(base_expand + deform_factor * deform_y)

    # 生成统一遮罩
    merged = [(
        max(0, overall_xmin - extra_x),
        min(frame_width, overall_xmax + extra_x),
        max(0, overall_ymin - extra_y),
        min(frame_height, overall_ymax + extra_y),
    )]

    return merged


def detect_text_deformation(
    sub_list: dict,
    start_frame: int,
    end_frame: int,
    pos_std_threshold: float = 15.0,
    size_std_threshold: float = 10.0,
) -> Tuple[bool, float]:
    """
    检测文字大幅度变形 — 分析检测框在帧间的剧烈变化

    原理：OCR 每帧检测文字框。当水印文字变形扭曲时：
    1. 文字框位置剧烈变化（高 std）
    2. 文字框大小剧烈变化（高 std）
    3. 框的数量可能变化（文字散开/聚合）

    当变形幅度超过阈值时，应使用用户手动选取的整个检测区域，
    而不是 OCR 检测到的零散小框。

    Parameters
    ----------
    sub_list : dict
        字幕检测结果 {frame_no: [(xmin,xmax,ymin,ymax), ...]}
    start_frame : int
        起始帧号
    end_frame : int
        结束帧号
    pos_std_threshold : float
        位置标准差阈值（像素），超过此值认为严重变形
    size_std_threshold : float
        尺寸标准差阈值（像素），超过此值认为严重变形

    Returns
    -------
    (is_deforming, deform_score)
        is_deforming : bool
            是否检测到大幅度变形
        deform_score : float
            变形幅度综合评分（0~1）
    """
    all_rects = []
    for fno in range(start_frame, end_frame + 1):
        if fno in sub_list:
            for rect in sub_list[fno]:
                all_rects.append(rect)

    if len(all_rects) < 5:
        return False, 0.0  # 帧太少无法判断

    xs_min = np.array([r[0] for r in all_rects])
    xs_max = np.array([r[1] for r in all_rects])
    ys_min = np.array([r[2] for r in all_rects])
    ys_max = np.array([r[3] for r in all_rects])
    widths = xs_max - xs_min
    heights = ys_max - ys_min

    # 计算位置和尺寸的标准差
    pos_std = float(np.mean([np.std(xs_min), np.std(xs_max),
                             np.std(ys_min), np.std(ys_max)]))
    size_std = float(np.mean([np.std(widths), np.std(heights)]))

    # 综合变形评分（归一化到 0~1）
    pos_score = min(1.0, pos_std / pos_std_threshold)
    size_score = min(1.0, size_std / size_std_threshold)
    deform_score = max(pos_score, size_score)

    is_deforming = (pos_std > pos_std_threshold) or (size_std > size_std_threshold)

    return is_deforming, deform_score


def batch_generator(data, max_batch_size):
    """
    根据data大小，生成最大长度不超过max_batch_size的均匀批次数据
    """
    n_samples = len(data)
    # 尝试找到一个比MAX_BATCH_SIZE小的batch_size，以使得所有的批次数量尽量接近
    batch_size = max_batch_size
    num_batches = n_samples // batch_size

    # 处理最后一批可能不足batch_size的情况
    # 如果最后一批少于其他批次，则减小batch_size尝试平衡每批的数量
    while n_samples % batch_size < batch_size / 2.0 and batch_size > 1:
        batch_size -= 1  # 减小批次大小
        num_batches = n_samples // batch_size

    # 生成前num_batches个批次
    for i in range(num_batches):
        yield data[i * batch_size:(i + 1) * batch_size]

    # 将剩余的数据作为最后一个批次
    last_batch_start = num_batches * batch_size
    if last_batch_start < n_samples:
        yield data[last_batch_start:]

def create_mask(size, coords_list, feather_edges: bool = True):
    """
    创建二值遮罩，支持边缘羽化

    Args:
        size: mask 尺寸 (height, width)
        coords_list: [(xmin,xmax,ymin,ymax), ...]
        feather_edges: 是否对 mask 边缘做高斯羽化（减少硬边残留）

    Returns:
        二值 mask 图像 (uint8)
    """
    mask = np.zeros(size, dtype="uint8")
    if coords_list:
        # 使用更大的扩展值
        expand = config.subtitleAreaDeviationPixel.value
        for coords in coords_list:
            xmin, xmax, ymin, ymax = coords
            x1 = max(0, xmin - expand)
            y1 = max(0, ymin - expand)
            x2 = xmax + expand
            y2 = ymax + expand
            cv2.rectangle(mask, (x1, y1), (x2, y2), (255, 255, 255), thickness=-1)

    # 边缘羽化：高斯模糊后重新二值化 → 柔化 mask 边界，减少修复痕迹
    if feather_edges and np.any(mask):
        blurred = cv2.GaussianBlur(mask.astype(np.float32), (7, 7), 3.0)
        # 保持核心区域不变，只柔化边缘
        core = cv2.erode(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)), iterations=1)
        edge_zone = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11)), iterations=1)
        edge_zone = cv2.subtract(edge_zone, core)
        # 边缘区域用模糊值，核心区域保持白色
        mask = np.where(core > 0, 255, blurred).astype(np.uint8)
        # 重新二值化
        _, mask = cv2.threshold(mask, 30, 255, cv2.THRESH_BINARY)

    return mask


def refine_inpaint_result(frame: np.ndarray, mask: np.ndarray,
                          inpainted: np.ndarray,
                          sharpen_strength: float = 0.3,
                          blend_feather: int = 15) -> np.ndarray:
    """
    修复结果后处理 — 消除颗粒感/模糊，提升画面合理性

    步骤：
    1. 对修复区域做自适应锐化（Unsharp Mask），恢复纹理细节
    2. 梯度羽化混合：修复区域与原始画面平滑过渡
    3. 颜色校正：修复区域的平均色值与周围匹配

    Parameters
    ----------
    frame : np.ndarray
        原始帧 (BGR)
    mask : np.ndarray
        修复遮罩 (H, W)，白色=修复区域
    inpainted : np.ndarray
        模型修复后的帧
    sharpen_strength : float
        锐化强度，0=不锐化，1=最大
    blend_feather : int
        羽化混合半径（像素）

    Returns
    -------
    np.ndarray
        后处理后的帧
    """
    result = inpainted.copy()

    # 1. 自适应锐化（仅对修复区域）
    if sharpen_strength > 0 and np.any(mask):
        blurred = cv2.GaussianBlur(inpainted, (0, 0), 2.0)
        sharpened = cv2.addWeighted(
            inpainted, 1.0 + sharpen_strength,
            blurred, -sharpen_strength, 0
        )
        # 只将锐化结果应用到遮罩区域
        mask_3ch = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR) > 0
        result = np.where(mask_3ch, sharpened, inpainted)

    # 2. 梯度羽化混合 — 修复区边缘与原始画面平滑过渡
    if blend_feather > 0 and np.any(mask):
        # 生成距离场：越靠近遮罩边缘权重越小
        dist = cv2.distanceTransform(
            cv2.bitwise_not(mask), cv2.DIST_L2, 5
        )
        # 在边缘创建渐变过渡带
        feather_radius = max(blend_feather, 3)
        alpha = np.clip(dist / feather_radius, 0, 1)
        alpha = 1.0 - alpha  # 遮罩内 alpha=1, 边缘渐变为0
        # 扩大 alpha 到边缘外
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                           (feather_radius * 2 + 1,
                                            feather_radius * 2 + 1))
        dilated_mask = cv2.dilate(mask, kernel, iterations=1)
        # 在扩张区域也应用渐变
        outer_dist = cv2.distanceTransform(
            cv2.bitwise_not(dilated_mask), cv2.DIST_L2, 5
        )
        outer_alpha = np.clip(outer_dist / feather_radius, 0, 1)
        outer_alpha = np.where(dilated_mask > 0,
                               np.maximum(alpha, 1.0 - outer_alpha), 0)
        # 应用混合
        alpha_3ch = cv2.cvtColor(
            (outer_alpha * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR
        ).astype(np.float32) / 255.0
        result = (result * alpha_3ch + frame * (1.0 - alpha_3ch)).astype(np.uint8)

    # 3. 颜色校正：修复区域的平均色值与周围区域匹配
    if np.any(mask):
        # 扩展 mask 取周围区域
        kernel_large = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
        surround = cv2.dilate(mask, kernel_large, iterations=1) - mask
        if np.any(surround > 0):
            # 计算修复区域和周围区域的平均颜色
            inpaint_mean = cv2.mean(result, mask)[:3]
            surround_mean = cv2.mean(frame, surround)[:3]
            # 如果色差较大，进行颜色迁移
            diff = np.array(surround_mean) - np.array(inpaint_mean)
            if np.max(np.abs(diff)) > 5:
                mask_3ch_b = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR).astype(bool)
                for c in range(3):
                    result[:, :, c] = np.where(
                        mask_3ch_b[:, :, c],
                        np.clip(result[:, :, c].astype(np.float32) + diff[c], 0, 255).astype(np.uint8),
                        result[:, :, c]
                    )

    return result


def batch_refine(frame_batch: List[np.ndarray],
                 mask: np.ndarray,
                 inpainted_batch: List[np.ndarray],
                 sharpen_strength: float = 0.3,
                 blend_feather: int = 15) -> List[np.ndarray]:
    """批量后处理（用于视频帧序列）"""
    return [
        refine_inpaint_result(f, mask, i, sharpen_strength, blend_feather)
        for f, i in zip(frame_batch, inpainted_batch)
    ]


def exemplar_fill_from_clean_frames(
    frames: List[np.ndarray],
    mask: np.ndarray,
    sub_dict: dict,
    start_frame: int,
    search_range: int = 30
) -> List[np.ndarray]:
    """
    从邻近干净帧中复制背景填充遮罩区域

    原理：对于每帧遮罩区域，在邻近 ±search_range 帧范围内，
    找到没有文字检测的帧，将干净的背景复制过来。
    使用真实视频像素填充，效果远优于 AI 修复。

    Parameters
    ----------
    frames : List[np.ndarray]
        当前批次的连续帧列表
    mask : np.ndarray
        遮罩 (H, W)
    sub_dict : dict
        字幕检测结果 {frame_no: [rects]}
    start_frame : int
        当前批次起始帧号
    search_range : int
        搜索范围（帧数）

    Returns
    -------
    List[np.ndarray]
        填充后的帧
    """
    if not frames or np.max(mask) == 0:
        return frames

    h, w = mask.shape
    result = [f.copy() for f in frames]
    # 扩张 mask 以确保覆盖
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    mask_expanded = cv2.dilate(mask, kernel, iterations=2)

    for i in range(len(frames)):
        current_frame_no = start_frame + i
        # 在邻近帧中搜索没有文字检测的帧
        clean_sources = []
        for offset in range(-search_range, search_range + 1):
            neighbor = current_frame_no + offset
            if neighbor < 1 or neighbor == current_frame_no:
                continue
            # 检查该帧是否有文字检测
            has_text = False
            if sub_dict and neighbor in sub_dict:
                for (xmin, xmax, ymin, ymax) in sub_dict[neighbor]:
                    # 检查检测框是否与遮罩区域重叠
                    if (xmin < w and xmax > 0 and ymin < h and ymax > 0):
                        has_text = True
                        break
            if not has_text:
                # 计算该帧相对于当前帧的索引
                neighbor_idx = i + offset
                if 0 <= neighbor_idx < len(frames):
                    clean_sources.append((neighbor_idx, abs(offset)))
                # 也尝试从已处理的结果中取
                # (如果该帧不在当前批次中，无法直接获取)

        if clean_sources:
            # 取最近的干净帧
            clean_sources.sort(key=lambda x: x[1])
            best_idx = clean_sources[0][0]
            # 将干净背景复制到当前帧
            result[i][mask_expanded > 0] = frames[best_idx][mask_expanded > 0]

    return result


def restore_film_grain(frame: np.ndarray, mask: np.ndarray,
                       strength: float = 0.5) -> np.ndarray:
    """
    为修复区域恢复胶片颗粒感，使其与原始画面纹理匹配

    原理：从原始帧的非遮罩区域采样纹理噪声特征，
    在修复区域上叠加匹配的颗粒噪声，消除 AI 修复的"塑料感"

    Parameters
    ----------
    frame : np.ndarray
        原始帧 (BGR)
    mask : np.ndarray
        遮罩 (H, W)，白色=修复区域
    strength : float
        颗粒强度 (0-1)

    Returns
    -------
    np.ndarray
        添加颗粒感后的帧
    """
    if np.max(mask) == 0 or strength <= 0:
        return frame

    result = frame.copy()

    # 从非遮罩区域采样纹理噪声特征
    non_mask = cv2.bitwise_not(mask)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    non_mask = cv2.erode(non_mask, kernel, iterations=1)  # 避免边缘

    if np.sum(non_mask > 0) < 1000:
        return result  # 采样区域太小

    # 计算非遮罩区域的局部标准差（作为噪声量级）
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    local_std = cv2.GaussianBlur(gray.astype(np.float32), (0, 0), 2.0)
    local_std = cv2.absdiff(gray.astype(np.float32), local_std)
    noise_level = np.mean(local_std[non_mask > 0]) if np.any(non_mask > 0) else 3.0

    # 生成匹配的颗粒噪声
    if noise_level > 1.0:
        noise = np.random.randn(*frame.shape).astype(np.float32) * noise_level * strength
        mask_3ch = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR).astype(bool)
        result = np.where(mask_3ch,
                          np.clip(frame.astype(np.float32) + noise, 0, 255).astype(np.uint8),
                          frame)

    return result


def batch_restore_grain(frame_batch: List[np.ndarray], mask: np.ndarray,
                        strength: float = 0.5) -> List[np.ndarray]:
    """批量恢复胶片颗粒"""
    return [restore_film_grain(f, mask, strength) for f in frame_batch]


def robust_background_estimate(
    frames: List[np.ndarray],
    mask: np.ndarray,
    trim_percent: float = 0.25
) -> np.ndarray:
    """
    鲁棒背景估计 — 对急速变化扭曲水印的终极方案

    原理：对遮罩区域的每个像素，收集在 N 帧中的所有观测值。
    由于水印内容每帧变化（扭曲/变形/变色），而背景相对稳定，
    用截尾平均（去掉最高/最低 25% 后取均值）可以鲁棒地估计真实背景。

    相比中值滤波的优势：
    - 中值只取中间值，对于变化剧烈的水印仍可能选中带水印的帧
    - 截尾平均丢弃极值后取均值，更准确地逼近背景

    Parameters
    ----------
    frames : List[np.ndarray]
        连续帧列表（越多越好，建议 30+ 帧）
    mask : np.ndarray
        精确遮罩 (H, W)，白色=水印区域
    trim_percent : float
        截尾比例，0.25 = 去掉最高/最低各 25%

    Returns
    -------
    np.ndarray
        背景估计帧（仅遮罩区域被填充，其余保持第一帧）
    """
    if not frames or np.max(mask) == 0:
        return frames[0] if frames else np.zeros((480, 852, 3), dtype=np.uint8)

    n = len(frames)
    h, w = mask.shape[:2]
    result = frames[0].copy()
    ys, xs = np.where(mask > 0)

    if len(ys) == 0:
        return result

    # 对每个像素收集所有帧的观测值
    # 批量处理以加速
    pixels = np.zeros((n, len(ys), 3), dtype=np.uint8)
    for i in range(n):
        pixels[i] = frames[i][ys, xs]

    # 排序并截尾平均
    pixels_sorted = np.sort(pixels.astype(np.float32), axis=0)
    trim = int(n * trim_percent)
    if trim > 0:
        trimmed = pixels_sorted[trim:-trim]
    else:
        trimmed = pixels_sorted
    background = np.mean(trimmed, axis=0).astype(np.uint8)

    # 写入结果
    result[ys, xs] = background
    return result


def density_background_estimate(
    frames: List[np.ndarray],
    mask: np.ndarray,
    density_radius: float = 18.0,
    min_cluster: float = 0.3,
) -> np.ndarray:
    """
    🎯 密度峰值背景估计 — 专杀带色调混合色的半透明AI水印

    豆包水印真相：白色不是纯白(255,255,255)，而是带色调的混合色。
    这意味着水印像素在RGB空间中向任意方向偏移，不一定是"变亮"。

    本方案用**局部密度聚类**：对每个像素在N帧中的观测值，
    找色彩空间中最稠密的区域 = 背景（因为大部分帧在该像素是干净的）。

    关键改进：
    - 全RGB三维空间聚类，保留色彩相关性
    - 密度半径自适应：用帧间的平均色差作为半径参考
    - 只取最稠密簇的平均，天然排除水印污染帧
    - 对任意颜色的水印都有效（不假设亮度方向）

    Parameters
    ----------
    frames : List[np.ndarray]
        连续帧列表（建议 30+ 帧）
    mask : np.ndarray
        遮罩 (H, W)，白色=水印区域
    density_radius : float
        密度半径（RGB空间欧氏距离），默认18
    min_cluster : float
        最小保留比例，防止空簇

    Returns
    -------
    np.ndarray
        背景估计帧
    """
    if not frames or np.max(mask) == 0:
        return frames[0].copy() if frames else None

    h, w = mask.shape[:2]
    result = frames[0].copy()
    ys, xs = np.where(mask > 0)
    if len(ys) == 0:
        return result

    n = len(frames)
    n_pix = len(ys)
    if n < 3:
        return result

    # 收集所有帧在遮罩像素的值: (N_frames, N_pixels, 3)
    pixels = np.stack([f[ys, xs] for f in frames], axis=0).astype(np.float32)

    bg_vals = np.zeros((n_pix, 3), dtype=np.float32)
    batch_size = 1500

    for start_idx in range(0, n_pix, batch_size):
        end_idx = min(start_idx + batch_size, n_pix)
        pix_block = pixels[:, start_idx:end_idx, :]
        bsize = end_idx - start_idx

        for pb in range(bsize):
            vals = pix_block[:, pb, :]  # (N, 3)

            # 对每帧，统计其密度半径内的邻居数
            # 使用向量化计算所有 pairwise 距离
            # vals: (N, 3) → diff: (N, N, 3)
            # 计算 L2 距离矩阵
            sq_diff = (vals[:, None, :] - vals[None, :, :]) ** 2
            dist_mat = np.sqrt(np.sum(sq_diff, axis=2))  # (N, N)

            # 邻居数：距离 < density_radius 的其他帧数
            neighbor_counts = np.sum(dist_mat < density_radius, axis=1)  # (N,)

            # 密度最高的帧 = 背景簇中心
            best_idx = np.argmax(neighbor_counts)

            # 该帧的所有邻居（包括自身）
            in_cluster = dist_mat[best_idx] < density_radius
            n_cluster = np.sum(in_cluster)

            # 至少保留 min_cluster 比例的帧
            if n_cluster < max(2, int(n * min_cluster)):
                # 密度不足时扩大半径重试
                sorted_dists = np.sort(dist_mat[best_idx])
                cutoff = sorted_dists[max(2, int(n * min_cluster)) - 1]
                in_cluster = dist_mat[best_idx] <= max(cutoff, 5.0)

            bg_vals[start_idx + pb] = np.mean(vals[in_cluster], axis=0)

    result[ys, xs] = bg_vals.astype(np.uint8)
    return result


def batch_density_estimate(
    frames: List[np.ndarray],
    mask: np.ndarray,
    window: int = 31,
    blend_orig: float = 0.15
) -> List[np.ndarray]:
    """
    批量密度峰值背景估计

    对每帧以其前后窗口内的帧做密度聚类背景估计。
    使用 RGB 三维密度峰值聚类，精准识别任意色调的半透明水印背景。
    """
    n = len(frames)
    half = window // 2
    result = []
    for i in range(n):
        start = max(0, i - half)
        end = min(n, i + half + 1)
        bg = density_background_estimate(frames[start:end], mask, density_radius=18.0)
        if bg is not None:
            if blend_orig > 0:
                mask_3ch = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR).astype(bool)
                blended = bg.copy()
                blended[mask_3ch] = cv2.addWeighted(
                    bg[mask_3ch], 1.0 - blend_orig,
                    frames[i][mask_3ch], blend_orig, 0
                )
                result.append(blended)
            else:
                result.append(bg)
        else:
            result.append(frames[i].copy())
    return result


def detect_residual_text_mask(
    frame: np.ndarray,
    inpainted: np.ndarray,
    mask: np.ndarray,
    edge_threshold: int = 25,
    min_contour_area: int = 15,
) -> np.ndarray:
    """
    检测修复后残留文字/图形痕迹，生成二次修补遮罩

    原理：
    1. 在遮罩区域内检测边缘（Canny）
    2. 如果修复不彻底，残留的文字笔画会产生明显的边缘响应
    3. 将这些边缘区域膨胀、连通，形成新的遮罩

    Parameters
    ----------
    frame : np.ndarray
        原始帧 (BGR) — 用于亮度参考
    inpainted : np.ndarray
        修复后的帧 (BGR)
    mask : np.ndarray
        原始遮罩 (H, W)，白色=修复区
    edge_threshold : int
        边缘检测阈值（越低越敏感，默认25）
    min_contour_area : int
        最小轮廓面积（像素），小于此值忽略

    Returns
    -------
    np.ndarray
        二次修补遮罩（仅残留严重的子区域）
    """
    if np.max(mask) == 0:
        return np.zeros_like(mask)

    gray_inpainted = cv2.cvtColor(inpainted, cv2.COLOR_BGR2GRAY)

    # 在遮罩区域内检测边缘
    edges = cv2.Canny(gray_inpainted, edge_threshold, edge_threshold * 3)
    edges = cv2.bitwise_and(edges, mask)  # 只保留遮罩内的边缘

    if np.sum(edges > 0) < min_contour_area:
        return np.zeros_like(mask)

    # 膨胀边缘使断开笔画连通
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    dilated = cv2.dilate(edges, kernel, iterations=3)

    # 找到连通区域
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    residual_mask = np.zeros_like(mask)
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area >= min_contour_area:
            cv2.drawContours(residual_mask, [cnt], -1, 255, thickness=-1)

    return residual_mask


def exemplar_fill_residuals(
    frame_batch: List[np.ndarray],
    inpainted_batch: List[np.ndarray],
    mask: np.ndarray,
    sub_dict: dict,
    start_frame: int,
    search_range: int = 15,
) -> List[np.ndarray]:
    """
    残留文字二次修补 — 从邻近干净帧精确复制像素

    对每个检测到残留的帧，从邻近无检测帧的相同位置复制背景像素。
    与 exemplar_fill_from_clean_frames 不同，本函数检测残留区域后
    只修补残留严重的子区域（而非整个 mask），避免破坏已修复好的区域。

    Parameters
    ----------
    frame_batch : List[np.ndarray]
        原始帧列表
    inpainted_batch : List[np.ndarray]
        修复后的帧列表
    mask : np.ndarray
        修复遮罩
    sub_dict : dict
        字幕检测结果 {frame_no: [(xmin,xmax,ymin,ymax), ...]}
    start_frame : int
        当前批次起始帧号
    search_range : int
        搜索范围（帧数）

    Returns
    -------
    List[np.ndarray]
        二次修补后的帧列表
    """
    result = [f.copy() for f in inpainted_batch]

    for i in range(len(inpainted_batch)):
        # 检测残留
        res_mask = detect_residual_text_mask(
            frame_batch[i], inpainted_batch[i], mask
        )
        if np.max(res_mask) == 0:
            continue

        current_frame_no = start_frame + i

        # 从邻近帧搜索没有文字检测的帧
        best_source = None
        for offset in range(-search_range, search_range + 1):
            neighbor = current_frame_no + offset
            if neighbor < 1 or neighbor == current_frame_no:
                continue
            neighbor_idx = i + offset
            if 0 <= neighbor_idx < len(frame_batch):
                has_text = False
                if sub_dict and neighbor in sub_dict:
                    for (xmin, xmax, ymin, ymax) in sub_dict[neighbor]:
                        if xmin < mask.shape[1] and xmax > 0 and ymin < mask.shape[0] and ymax > 0:
                            has_text = True
                            break
                if not has_text:
                    best_source = neighbor_idx
                    break

        if best_source is not None:
            # 从干净帧复制背景到残留区域
            result[i][res_mask > 0] = frame_batch[best_source][res_mask > 0]

    return result


def batch_robust_estimate(
    frames: List[np.ndarray],
    mask: np.ndarray,
    window: int = 31
) -> List[np.ndarray]:
    """
    批量鲁棒背景估计 — 对每帧以其前后窗口内的帧做背景估计

    Parameters
    ----------
    frames : List[np.ndarray]
    mask : np.ndarray
    window : int
        时间窗口（帧数），奇数

    Returns
    -------
    List[np.ndarray]
    """
    n = len(frames)
    half = window // 2
    result = []
    for i in range(n):
        start = max(0, i - half)
        end = min(n, i + half + 1)
        bg = robust_background_estimate(frames[start:end], mask, trim_percent=0.25)
        result.append(bg)
    return result


def texture_transfer_inpaint(
    frame: np.ndarray,
    mask: np.ndarray,
    patch_size: int = 7,
    search_radius: int = 40,
    blend_strength: float = 0.7
) -> np.ndarray:
    """
    纹理传输修复 — 从遮罩周围区域采样纹理补丁，填充遮罩区域

    专门针对半透明 AI 水印：在模型修复后执行此函数，
    从周围非遮罩区域采集真实纹理补丁，替换修复区域的模糊纹理。
    效果远优于纯 AI 修复，因为使用的是视频本身的真实像素纹理。

    Parameters
    ----------
    frame : np.ndarray
        当前帧 (BGR)
    mask : np.ndarray
        二值遮罩，白色=需要修复的区域
    patch_size : int
        纹理补丁大小（奇数），默认7x7
    search_radius : int
        搜索半径（像素），默认40px
    blend_strength : float
        混合强度 0-1，越高保留越多传输纹理

    Returns
    -------
    np.ndarray
        纹理传输修复后的帧
    """
    if np.max(mask) == 0:
        return frame

    h, w = mask.shape[:2]
    result = frame.copy()

    # 扩张遮罩作为目标区域
    kernel_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    target_mask = cv2.dilate(mask, kernel_dilate, iterations=2)

    # 找到遮罩区域的边界像素（用于匹配）
    edges = cv2.Canny(mask, 0, 1)
    edge_points = np.argwhere(edges > 0)

    if len(edge_points) == 0:
        return result

    # 对遮罩区域内的每个像素，从周围区域找最佳匹配补丁
    ys, xs = np.where(target_mask > 0)
    half_p = patch_size // 2

    # 为加速，只在边缘区域做纹理传输（内部用 inpainting 结果）
    # 边缘区域是修复痕迹最明显的地方
    edge_zone = cv2.dilate(mask, cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (15, 15)), iterations=1)
    edge_zone = cv2.subtract(edge_zone, cv2.erode(
        mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)), iterations=1))
    ey_points = np.argwhere(edge_zone > 0)

    if len(ey_points) == 0:
        return result

    # 对每个边缘像素进行纹理传输
    import random
    rng = random.Random(42)

    for py, px in ey_points:
        # 跳过靠近边界的像素
        if (py < half_p or py >= h - half_p or
            px < half_p or px >= w - half_p):
            continue

        # 提取目标补丁（当前帧的像素）
        target_patch = frame[py-half_p:py+half_p+1,
                             px-half_p:px+half_p+1].astype(np.float32)

        # 在周围搜索区域找最佳匹配
        best_match = None
        best_dist = float('inf')

        # 搜索范围
        y_start = max(half_p, py - search_radius)
        y_end = min(h - half_p, py + search_radius)
        x_start = max(half_p, px - search_radius)
        x_end = min(w - half_p, px + search_radius)

        # 随机采样搜索（加速）
        search_points = []
        for sy in range(y_start, y_end, 2):
            for sx in range(x_start, x_end, 2):
                # 跳过遮罩内的点
                if target_mask[sy, sx] > 0:
                    continue
                search_points.append((sy, sx))

        # 随机打乱并取前200个
        if len(search_points) > 200:
            search_points = rng.sample(search_points, 200)

        for sy, sx in search_points:
            src_patch = frame[sy-half_p:sy+half_p+1,
                              sx-half_p:sx+half_p+1].astype(np.float32)
            dist = np.sum((src_patch - target_patch) ** 2)
            if dist < best_dist:
                best_dist = dist
                best_match = (sy, sx)

        # 应用最佳匹配纹理
        if best_match is not None:
            sy, sx = best_match
            src_tex = frame[sy-half_p:sy+half_p+1,
                            sx-half_p:sx+half_p+1].astype(np.float32)

            # 混合：传输纹理 + 原始修复结果
            alpha = blend_strength
            blended = (src_tex * alpha +
                       result[py-half_p:py+half_p+1,
                              px-half_p:px+half_p+1].astype(np.float32) * (1 - alpha))

            result[py-half_p:py+half_p+1,
                   px-half_p:px+half_p+1] = np.clip(blended, 0, 255).astype(np.uint8)

    return result


def batch_texture_transfer(frame_batch: List[np.ndarray],
                           mask: np.ndarray) -> List[np.ndarray]:
    """批量纹理传输"""
    return [texture_transfer_inpaint(f, mask) for f in frame_batch]


def create_polygon_mask(
    size: Tuple[int, int],
    polygons: List[np.ndarray],
    dilate_kernel_size: int = 3,
    expand_pixels: int = 0,
) -> np.ndarray:
    """
    创建基于多边形的 mask，支持非矩形水印区域

    相比 create_mask() 的轴对齐矩形，此函数支持：
    - 旋转矩形
    - 透视变形后的四边形
    - 任意多边形

    Args:
        size: mask 尺寸 (height, width)
        polygons: 多边形列表，每个多边形为 (N, 2) 的 numpy 数组
        dilate_kernel_size: 膨胀核大小，用于平滑 mask 边缘
        expand_pixels: 额外扩展的像素数

    Returns:
        二值 mask 图像 (uint8)
    """
    mask = np.zeros(size, dtype="uint8")

    if not polygons:
        return mask

    for polygon in polygons:
        if polygon is None or len(polygon) < 3:
            continue

        # 转换为整数坐标
        pts = np.int32(polygon)

        # 填充多边形
        cv2.fillPoly(mask, [pts], (255, 255, 255))

    # 膨胀以扩大 mask 覆盖范围
    if expand_pixels > 0:
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (expand_pixels * 2 + 1, expand_pixels * 2 + 1)
        )
        mask = cv2.dilate(mask, kernel, iterations=1)

    # 轻微模糊 + 重新二值化，平滑 mask 边缘
    if dilate_kernel_size > 0:
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (dilate_kernel_size, dilate_kernel_size)
        )
        mask = cv2.dilate(mask, kernel, iterations=1)

    return mask


def create_unified_mask(
    size: Tuple[int, int],
    coords_list: List[Union[Tuple, np.ndarray]],
    polygon_expand_pixels: int = 5,
) -> np.ndarray:
    """
    统一 mask 创建函数：自动识别矩形坐标或多边形坐标

    支持混合输入：
    - (xmin, xmax, ymin, ymax) 元组 → 轴对齐矩形
    - (N, 2) numpy 数组 → 多边形

    Args:
        size: mask 尺寸 (height, width)
        coords_list: 混合坐标列表
        polygon_expand_pixels: 多边形额外扩展像素

    Returns:
        二值 mask 图像 (uint8)
    """
    mask = np.zeros(size, dtype="uint8")

    if not coords_list:
        return mask

    rect_coords = []
    polygon_coords = []

    for coords in coords_list:
        if isinstance(coords, np.ndarray) and coords.ndim == 2:
            # 多边形
            polygon_coords.append(coords)
        elif isinstance(coords, (tuple, list)) and len(coords) == 4:
            # 轴对齐矩形
            rect_coords.append(coords)
        elif isinstance(coords, np.ndarray) and coords.shape == (4,):
            rect_coords.append(tuple(coords.tolist()))

    # 绘制矩形部分
    if rect_coords:
        for xmin, xmax, ymin, ymax in rect_coords:
            x1 = int(xmin) - config.subtitleAreaDeviationPixel.value
            if x1 < 0:
                x1 = 0
            y1 = int(ymin) - config.subtitleAreaDeviationPixel.value
            if y1 < 0:
                y1 = 0
            x2 = int(xmax) + config.subtitleAreaDeviationPixel.value
            y2 = int(ymax) + config.subtitleAreaDeviationPixel.value
            cv2.rectangle(
                mask, (x1, y1), (x2, y2), (255, 255, 255), thickness=-1
            )

    # 绘制多边形部分
    if polygon_coords:
        poly_mask = create_polygon_mask(
            size, polygon_coords, expand_pixels=polygon_expand_pixels
        )
        mask = cv2.bitwise_or(mask, poly_mask)

    return mask


def temporal_median_filter_frames(
    frames: List[np.ndarray],
    mask: np.ndarray,
    window: int = 15
) -> List[np.ndarray]:
    """
    时序中值滤波 — 对遮罩区域做跨帧中值滤波

    原理：对每帧遮罩区域的像素，取其前后 ±window/2 帧的中值替换。
    对于变色/变形的文字水印，文字在时间轴上变化而背景相对稳定，
    中值滤波可以保留稳定背景、消除变化文字。

    Parameters
    ----------
    frames : List[np.ndarray]
        连续帧列表 (BGR)
    mask : np.ndarray
        遮罩 (H, W)，uint8，白色区域为待处理区
    window : int
        时间窗口（帧数），奇数，默认15

    Returns
    -------
    List[np.ndarray]
        处理后的帧列表
    """
    if not frames or mask is None or np.max(mask) == 0:
        return frames
    if window < 3:
        window = 3
    window = window // 2 * 2 + 1  # 确保奇数

    n = len(frames)
    half = window // 2
    h, w = mask.shape[:2]
    ys, xs = np.where(mask > 0)
    if len(ys) == 0:
        return frames

    result = [f.copy() for f in frames]

    # 对遮罩中的每个像素，收集时间维度的值取中值
    for idx in range(len(ys)):
        y, x = ys[idx], xs[idx]
        start = max(0, idx - half if False else 0)  # per-pixel would be slow
        # 改为逐帧批量处理
        pass

    # 逐帧批量处理（更高效）
    for i in range(n):
        # 收集前后帧
        start = max(0, i - half)
        end = min(n, i + half + 1)
        # 对遮罩区域取时间维中值
        roi_values = []
        for j in range(start, end):
            roi_values.append(frames[j][mask > 0])
        if roi_values:
            # shape: (window_size, num_pixels, 3)
            stack = np.stack(roi_values, axis=0)
            median_val = np.median(stack, axis=0).astype(np.uint8)
            result[i][mask > 0] = median_val

    return result


def temporal_median_filter_frame(
    frame: np.ndarray,
    neighbor_frames: List[np.ndarray],
    mask: np.ndarray
) -> np.ndarray:
    """
    对单帧做时序中值滤波（用于视频流式处理）

    Parameters
    ----------
    frame : np.ndarray
        当前帧
    neighbor_frames : List[np.ndarray]
        邻居帧列表（包含当前帧）
    mask : np.ndarray
        遮罩

    Returns
    -------
    np.ndarray
        处理后的帧
    """
    if not neighbor_frames or np.max(mask) == 0:
        return frame

    result = frame.copy()
    # 收集所有帧在遮罩区域的像素
    pixels = np.stack([f[mask > 0] for f in neighbor_frames], axis=0)
    median_val = np.median(pixels, axis=0).astype(np.uint8)
    result[mask > 0] = median_val
    return result


def remove_bright_residuals(
    frame: np.ndarray,
    inpainted: np.ndarray,
    mask: np.ndarray,
    threshold_std: float = 1.8,
    blend_radius: int = 5
) -> np.ndarray:
    """
    去除修复后残留的白色/亮色半透明伪影

    原理：水印被修复后，如果模型未能完全去除，会在遮罩区域留下
    异常明亮的像素（白色/淡白色半透明）。本函数检测这些异常亮斑，
    将其与周围正常像素平滑混合。

    Parameters
    ----------
    frame : np.ndarray
        原始帧（BGR），用于参考周围区域的真实亮度
    inpainted : np.ndarray
        修复后的帧
    mask : np.ndarray
        修复遮罩 (H, W)，白色=修复区
    threshold_std : float
        标准差倍数阈值，亮度超过周围均值+threshold_std*标准差 的像素被视为残留
    blend_radius : int
        混合半径（用于从边界采样替代像素）

    Returns
    -------
    np.ndarray
        清理残留后的帧
    """
    if np.max(mask) == 0:
        return inpainted

    result = inpainted.copy()
    gray = cv2.cvtColor(inpainted, cv2.COLOR_BGR2GRAY).astype(np.float32)

    # 扩张mask取周围区域（用于亮度参考）
    kernel_large = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
    surround = cv2.dilate(mask, kernel_large, iterations=1)
    surround = cv2.subtract(surround, mask)

    if np.sum(surround > 0) < 100:
        return result

    # 计算周围区域的亮度统计
    surround_gray = gray[surround > 0]
    if len(surround_gray) == 0:
        return result
    surround_mean = np.mean(surround_gray)
    surround_std = np.std(surround_gray)
    if surround_std < 1.0:
        surround_std = 1.0

    # 亮度阈值：周围平均亮度 + N倍标准差
    bright_threshold = surround_mean + threshold_std * surround_std

    # 找到异常亮的像素（在mask区域内且亮度超标）
    ys, xs = np.where((mask > 0) & (gray > bright_threshold))
    if len(ys) == 0:
        return result

    # 对每个异常亮像素，从周围非遮罩区域采样正常像素替代
    h, w = mask.shape[:2]
    for y, x in zip(ys, xs):
        search_y1 = max(0, y - blend_radius)
        search_y2 = min(h, y + blend_radius + 1)
        search_x1 = max(0, x - blend_radius)
        search_x2 = min(w, x + blend_radius + 1)

        neighborhood = inpainted[search_y1:search_y2, search_x1:search_x2]
        neigh_mask = mask[search_y1:search_y2, search_x1:search_x2]
        neigh_gray = gray[search_y1:search_y2, search_x1:search_x2]

        # 找到非遮罩、亮度正常的像素
        valid = (neigh_mask == 0) & (neigh_gray <= bright_threshold)
        if np.any(valid):
            valid_pts = np.argwhere(valid)
            best_dist = float('inf')
            best_pixel = None
            cy, cx = y - search_y1, x - search_x1
            for vy, vx in valid_pts:
                dist = abs(vy - cy) + abs(vx - cx)
                if dist < best_dist:
                    best_dist = dist
                    best_pixel = neighborhood[vy, vx]
            if best_pixel is not None:
                # 替代并轻微混合
                alpha = min(1.0, best_dist / (blend_radius * 2))
                result[y, x] = (
                    best_pixel.astype(np.float32) * (1 - alpha * 0.3) +
                    inpainted[y, x].astype(np.float32) * (alpha * 0.3)
                ).astype(np.uint8)

    return result


def batch_remove_bright_residuals(
    frame_batch: List[np.ndarray],
    inpainted_batch: List[np.ndarray],
    mask: np.ndarray
) -> List[np.ndarray]:
    """批量去除亮色残留"""
    return [
        remove_bright_residuals(f, i, mask)
        for f, i in zip(frame_batch, inpainted_batch)
    ]


def get_inpaint_area_by_mask(W, H, h, mask, multiple=1):
    """
    获取字幕去除区域，根据mask来确定需要填补的区域和高度，
    并根据模型要求调整区域大小为指定倍数
    
    Args:
        W: 图像宽度
        H: 图像高度
        h: 检测区域高度
        mask: 遮罩图像
        multiple: 区域尺寸需要满足的倍数，默认为1
    
    Returns:
        调整后的绘画区域列表，格式为[(ymin, ymax, xmin, xmax), ...]
    """
    # 存储绘画区域的列表
    inpaint_area = []
    
    # 如果mask全为0，直接返回空列表
    if np.all(mask == 0):
        return inpaint_area
    
    # 使用连通组件分析找出mask中的所有孤岛
    # 首先确保mask是二值图像
    binary_mask = (mask > 0).astype(np.uint8) * 255
    
    # 查找连通组件
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary_mask, connectivity=8)
    
    # 跳过背景（标签0）
    island_info = []
    for i in range(1, num_labels):
        # 获取当前孤岛的统计信息
        x = stats[i, cv2.CC_STAT_LEFT]
        y = stats[i, cv2.CC_STAT_TOP]
        w = stats[i, cv2.CC_STAT_WIDTH]
        height = stats[i, cv2.CC_STAT_HEIGHT]
        area = stats[i, cv2.CC_STAT_AREA]
        
        # 忽略太小的区域（可能是噪点）
        if area < 10:
            continue
        
        # 保存孤岛信息：顶部y坐标，底部y坐标，中心点y坐标，面积，标签
        center_y = int(centroids[i][1])
        island_info.append((y, y + height, center_y, area, i))
    
    # 如果没有有效孤岛，返回空列表
    if not island_info:
        return inpaint_area
    
    # 按中心点y坐标排序孤岛
    island_info.sort(key=lambda x: x[2])
    
    # 尝试合并孤岛
    merged_islands = []
    current_group = [island_info[0]]
    
    for i in range(1, len(island_info)):
        # 当前组的范围
        min_y = min([island[0] for island in current_group])
        max_y = max([island[1] for island in current_group])
        
        # 当前孤岛
        top_y, bottom_y, center_y, _, _ = island_info[i]
        
        # 计算如果添加当前孤岛，新组的范围
        new_min_y = min(min_y, top_y)
        new_max_y = max(max_y, bottom_y)
        
        # 检查是否有mask连接当前组和新孤岛
        has_connection = False
        if max_y < top_y:  # 只有当前组在新孤岛上方时才需要检查连接
            # 检查两个区域之间是否有mask像素
            middle_region = binary_mask[max_y:top_y, :]
            if np.any(middle_region > 0):
                has_connection = True
        else:  # 重叠或相邻
            has_connection = True
        
        # 检查合并后的高度是否在h范围内，并且有连接
        if new_max_y - new_min_y <= h and has_connection:
            # 可以合并
            current_group.append(island_info[i])
        else:
            # 无法合并，保存当前组并开始新组
            merged_islands.append(current_group)
            current_group = [island_info[i]]
    
    # 添加最后一个组
    merged_islands.append(current_group)
    
    # 为每个合并后的组创建区域
    for group in merged_islands:
        # 获取组内所有孤岛的范围
        min_y = min([island[0] for island in group])
        max_y = max([island[1] for island in group])
        
        # 计算组的中心点
        center_y = sum([island[2] for island in group]) // len(group)
        
        # 确保区域高度精确等于h
        half_h = h // 2
        
        # 从中心点向上下扩展，确保高度为h
        ymin = max(0, center_y - half_h)
        ymax = ymin + h  # 确保高度精确等于h
        
        # 如果超出图像底部，从底部向上调整
        if ymax > H:
            ymax = H
            ymin = max(0, H - h)  # 确保高度为h
        
        # 检查是否包含了所有孤岛
        if ymin > min_y or ymax < max_y:
            # 如果区域不能完全包含所有孤岛，尝试调整位置但保持高度为h
            if max_y - min_y <= h:
                # 孤岛总高度不超过h，可以调整位置使其完全包含
                ymin = min_y
                ymax = ymin + h
                # 如果超出底部，从底部向上调整
                if ymax > H:
                    ymax = H
                    ymin = max(0, H - h)
            else:
                # 孤岛总高度超过h，无法完全包含，优先包含中心区域
                # 计算孤岛的中心
                island_center = (min_y + max_y) // 2
                ymin = max(0, island_center - half_h)
                ymax = ymin + h
                # 如果超出底部，从底部向上调整
                if ymax > H:
                    ymax = H
                    ymin = max(0, H - h)
        
        # 使用完整宽度
        xmin = 0
        xmax = W
        
        # 调整区域大小为指定倍数
        if multiple > 1:
            # 计算区域高度
            height = ymax - ymin
            # 计算需要调整的高度，使其成为multiple的倍数
            remainder = height % multiple
            
            if remainder != 0:
                # 需要调整的像素数
                adjust_pixels = multiple - remainder
                
                # 计算区域中心点
                center_y = (ymin + ymax) / 2
                
                # 优先对称扩展
                if ymin - adjust_pixels/2 >= 0 and ymax + adjust_pixels/2 <= H:
                    # 对称扩展
                    ymin = int(center_y - height/2 - adjust_pixels/2)
                    ymax = int(center_y + height/2 + adjust_pixels/2)
                # 如果对称扩展会超出边界，尝试对称缩小
                elif height > multiple:  # 确保缩小后高度至少为multiple
                    # 对称缩小
                    ymin = int(center_y - (height - remainder)/2)
                    ymax = int(center_y + (height - remainder)/2)
                # 如果无法对称调整，则尝试单边调整
                else:
                    # 向下扩展
                    if ymax + adjust_pixels <= H:
                        ymax += adjust_pixels
                    # 向上扩展
                    elif ymin - adjust_pixels >= 0:
                        ymin -= adjust_pixels
                    # 如果都不行，则尝试缩小区域
                    elif height > multiple:
                        ymax = ymin + height - remainder
            
            # 调整宽度，确保是multiple的倍数
            width = xmax - xmin
            remainder_w = width % multiple
            
            if remainder_w != 0:
                # 需要调整的像素数
                adjust_pixels_w = multiple - remainder_w
                
                # 计算中心点，对称缩小
                center_x = (xmin + xmax) / 2
                xmin = int(center_x - (width - remainder_w)/2)
                xmax = int(center_x + (width - remainder_w)/2)
        
        # 将该区域添加到列表中，格式为(ymin, ymax, xmin, xmax)
        area = (int(ymin), int(ymax), int(xmin), int(xmax))
        if area not in inpaint_area:
            inpaint_area.append(area)
    
    return inpaint_area  # 返回绘画区域列表，格式为[(ymin, ymax, xmin, xmax), ...]
    
def expand_frame_ranges(frame_ranges, backward_frame_count, forward_frame_count):
    """
    扩展帧区间列表，向前和向后扩展指定的帧数，并确保区间连续性
    
    Args:
        frame_ranges: 帧区间列表，格式为[(start1, end1), (start2, end2), ...]
        backward_frame_count: 向前扩展的帧数
        forward_frame_count: 向后扩展的帧数
        
    Returns:
        扩展后的帧区间，保证连续性
    """
    if not frame_ranges:
        return []
    
    # 按起始帧排序
    sorted_ranges = sorted(frame_ranges)
    expanded_ranges = []
    
    for i, (start, end) in enumerate(sorted_ranges):
        # 向前扩展，但不能小于1
        new_start = max(1, start - backward_frame_count)
        
        # 向后扩展
        new_end = end + forward_frame_count
        
        # 检查是否与下一个区间重叠
        if i < len(sorted_ranges) - 1:
            next_start = sorted_ranges[i + 1][0]
            
            # 如果扩展后的结束帧超过了下一个区间的起始帧
            if new_end >= next_start:
                # 计算中点
                mid_point = (end + next_start) // 2
                
                # 如果区间是连续的(相差1)，则对半平分
                if next_start - end == 1:
                    new_end = end  # 保持原结束帧
                else:
                    # 非连续区间，限制扩展到下一个区间起始帧减去backward_frame_count
                    max_expand = next_start - 1  # 确保不会与下一个区间重叠
                    new_end = min(new_end, max_expand)
        
        # 确保与前一个区间不重叠
        if expanded_ranges:
            prev_end = expanded_ranges[-1][1]
            if new_start <= prev_end:
                # 如果新区间的开始小于等于前一个区间的结束，调整开始位置
                new_start = prev_end + 1
        
        # 确保区间有效（开始不大于结束）
        if new_start <= new_end:
            expanded_ranges.append((new_start, new_end))
        else:
            # 如果调整后区间无效，保留原始区间
            expanded_ranges.append((start, end))
    
    return expanded_ranges

def is_frame_number_in_ab_sections(frame_no, ab_sections):
    """
    检查给定的帧号是否在指定的A/B区间内。

    Args:
        frame_no: 要检查的帧号
        ab_sections: 包含A/B区间的列表，格式为[range(start, end), ...]

    Returns:
        如果帧号在A/B区间内，返回True；否则返回False。
    """
    if ab_sections is None:
        return True
    if len(ab_sections) <= 0:
        return True
    for section in ab_sections:
        if frame_no in section:
            return True
    return False


def temporal_smooth_mask(mask_sequence, window=3):
    """
    时序遮罩平滑 — 对连续帧的 mask 做时间维度的中值滤波，
    减少闪烁和噪点，使修复结果更稳定。

    Parameters
    ----------
    mask_sequence : list of np.ndarray
        连续帧的 mask 列表 (H, W) uint8 0/255
    window : int
        时间窗口大小（奇数）

    Returns
    -------
    list of np.ndarray
        平滑后的 mask 列表
    """
    if not mask_sequence:
        return []
    if window < 1:
        return mask_sequence

    window = max(1, window // 2 * 2 + 1)  # 确保奇数
    half = window // 2
    n = len(mask_sequence)
    h, w = mask_sequence[0].shape
    smoothed = []

    # 构建时间-空间体积 (T, H, W)
    volume = np.array(mask_sequence, dtype=np.uint8)

    for i in range(n):
        start = max(0, i - half)
        end = min(n, i + half + 1)
        # 时间维中值滤波
        median_mask = np.median(volume[start:end], axis=0).astype(np.uint8)
        # 二值化
        _, median_mask = cv2.threshold(median_mask, 127, 255, cv2.THRESH_BINARY)
        smoothed.append(median_mask)

    return smoothed


def adaptive_orig_blend(
    raw_orig_batch: List[np.ndarray],
    processed_batch: List[np.ndarray],
    mask: np.ndarray,
    color_threshold: float = 2.0,
    bright_threshold: float = 1.5,
    feather_blend: int = 10
) -> List[np.ndarray]:
    """
    自适应原始保护混合 v2 — 多模态水印检测（文字+图像）

    原理：使用处理后的帧作为"干净背景参考"，对比原始帧与参考帧在
    遮罩区的差异。差异来源包括：
    - 白色文字水印 → 亮度异常（gray域检测）
    - 彩色图像水印 → 色差异常（CIELAB ΔE 检测）
    - 任意颜色半透明水印 → 综合颜色距离

    对每个像素独立判断：
    - 原始像素与参考帧差异大 → 有水印 → 使用处理结果
    - 原始像素与参考帧差异小 → 无残留 → 保留原始完美画质

    Parameters
    ----------
    raw_orig_batch : List[np.ndarray]
        未经任何处理的原始帧（原始视频帧）
    processed_batch : List[np.ndarray]
        经过修复和后处理的帧
    mask : np.ndarray
        遮罩 (H, W)
    color_threshold : float
        色差阈值（标准差倍数），越低越保守
    bright_threshold : float
        亮度异常阈值（灰度标准差倍数）
    feather_blend : int
        边缘羽化半径

    Returns
    -------
    List[np.ndarray]
    """
    if not raw_orig_batch or not processed_batch or np.max(mask) == 0:
        return processed_batch

    n = len(processed_batch)
    h, w = mask.shape[:2]

    # 用处理后的帧构建"干净背景参考"：取每像素时间维中值
    # 处理后的帧已经去除了大部分水印，中值进一步平滑异常
    stack = np.stack([p.astype(np.float32) for p in processed_batch], axis=0)
    bg_ref = np.median(stack, axis=0).astype(np.uint8)  # (H, W, 3)

    # 将背景参考转为 CIELAB 用于色差计算
    bg_lab = cv2.cvtColor(bg_ref, cv2.COLOR_BGR2LAB).astype(np.float32)

    # mask边缘羽化
    if feather_blend > 0:
        dist = cv2.distanceTransform(
            cv2.bitwise_not(mask), cv2.DIST_L2, 5
        )
        feather_alpha = np.clip(dist / feather_blend, 0, 1)
        feather_alpha = 1.0 - feather_alpha
        feather_alpha_3ch = cv2.cvtColor(
            (feather_alpha * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR
        ).astype(np.float32) / 255.0

    result = [p.copy() for p in processed_batch]

    for i in range(n):
        orig = raw_orig_batch[i].astype(np.float32)

        # ---- 检测方式1：灰度亮度异常（白色文字水印） ----
        orig_gray = cv2.cvtColor(orig.astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)
        ref_gray = cv2.cvtColor(bg_ref, cv2.COLOR_BGR2GRAY).astype(np.float32)
        # 原始帧比参考帧亮多少（正数=更亮=可能是白色水印）
        bright_diff = orig_gray - ref_gray

        # ---- 检测方式2：CIELAB 色差（彩色图像水印） ----
        orig_lab = cv2.cvtColor(orig.astype(np.uint8), cv2.COLOR_BGR2LAB).astype(np.float32)
        # ΔE 色差 (简化版: 欧氏距离在LAB空间)
        color_dist = np.sqrt(
            np.sum((orig_lab - bg_lab) ** 2, axis=2)
        )  # (H, W)

        # ---- 综合判断：在mask区域内做自适应阈值 ----
        mask_bright = bright_diff[mask > 0]
        mask_color = color_dist[mask > 0]

        if len(mask_bright) == 0:
            continue

        # 自适应阈值：均值 + N倍标准差
        b_mean = float(np.mean(mask_bright))
        b_std = float(np.std(mask_bright))
        c_mean = float(np.mean(mask_color))
        c_std = float(np.std(mask_color))
        if b_std < 1.0: b_std = 1.0
        if c_std < 1.0: c_std = 1.0

        # 水印判断：
        #   bright_diff > 0 = 原始比参考亮（白色水印特征）
        #   bright_diff > b_mean + bright_threshold * b_std = 异常亮
        #   color_dist > c_mean + color_threshold * c_std = 色差异常
        is_bright_watermark = (bright_diff > 0) & \
                              (bright_diff > b_mean + bright_threshold * b_std)
        is_color_watermark = (color_dist > c_mean + color_threshold * c_std)

        # 综合：任一条件成立 → 判定为水印残留
        is_watermark = is_bright_watermark | is_color_watermark
        is_watermark = is_watermark & (mask > 0)

        # 构建选择遮罩：True=保留原始（无水印），False=使用处理结果（有水印）
        use_orig = np.zeros_like(mask, dtype=bool)
        use_orig[(mask > 0) & (~is_watermark)] = True

        # 应用选择
        if np.any(use_orig):
            use_orig_3ch = np.stack([use_orig] * 3, axis=2)
            result[i] = np.where(
                use_orig_3ch,
                raw_orig_batch[i],
                processed_batch[i]
            )

        # 边缘羽化混合
        if feather_blend > 0:
            result[i] = (
                result[i].astype(np.float32) * feather_alpha_3ch +
                processed_batch[i].astype(np.float32) * (1.0 - feather_alpha_3ch)
            ).astype(np.uint8)

    return result


if __name__ == '__main__':
    multiprocessing.set_start_method("spawn")
