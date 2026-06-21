
import os
from pathlib import Path
from qfluentwidgets import (qconfig, ConfigItem, QConfig, OptionsValidator, BoolValidator, OptionsConfigItem, 
                            EnumSerializer, RangeValidator, RangeConfigItem, ConfigValidator)
from backend.tools.constant import InpaintMode, SubtitleDetectMode
import configparser

# 项目版本号
VERSION = "1.4.0"
PROJECT_HOME_URL = "https://github.com/YaoFANGUK/video-subtitle-remover"
PROJECT_ISSUES_URL = PROJECT_HOME_URL + "/issues"
PROJECT_RELEASES_URL = PROJECT_HOME_URL + "/releases"
PROJECT_UPDATE_URLS = [
    "https://api.github.com/repos/YaoFANGUK/video-subtitle-remover/releases/latest",
    "https://accelerate.xdow.net/api/repos/YaoFANGUK/video-subtitle-remover/releases/latest",
] 

# 硬件加速选项开关
HARDWARD_ACCELERATION_OPTION = True

class Config(QConfig):
    # 界面语言设置
    intefaceTexts = {
        '简体中文': 'ch',
        '繁體中文': 'chinese_cht',
        'English': 'en',
        '한국어': 'ko',
        '日本語': 'japan',
        'Tiếng Việt': 'vi',
        'Español': 'es'
    }
    interface = OptionsConfigItem("Window", "Interface", "ChineseSimplified", OptionsValidator(intefaceTexts.values()), restart = True)
    
    # 窗口位置和大小
    windowX = ConfigItem("Window", "X", None)
    windowY = ConfigItem("Window", "Y", None)
    windowW = ConfigItem("Window", "Width", 1200)
    windowH = ConfigItem("Window", "Height", 1200)

    # 使用一个配置项存储所有选区
    # 默认值为一个选区，格式为："ymin,ymax,xmin,xmax;ymin,ymax,xmin,xmax;..."，分号分隔不同选区
    subtitleSelectionAreas = ConfigItem("Main", "SubtitleSelectionAreas", "0.88,0.99,0.15,0.85")

    """
    MODE可选算法类型
    - InpaintMode.STTN_AUTO 智能擦除版
    - InpaintMode.STTN_DET 带字幕检测版, 无智能擦除
    - InpaintMode.LAMA 算法：对于动画类视频效果好，速度一般，不可以跳过字幕检测
    - InpaintMode.PROPAINTER 算法： 需要消耗大量显存，速度较慢，对运动非常剧烈的视频效果较好
    """
    # 【设置inpaint算法】
    inpaintMode = OptionsConfigItem("Main", "InpaintMode", InpaintMode.STTN_AUTO, OptionsValidator(InpaintMode), EnumSerializer(InpaintMode))
    
    subtitleDetectMode =  OptionsConfigItem("Main", "SubtitleDetectMode", SubtitleDetectMode.PP_OCRv4_SERVER, OptionsValidator(SubtitleDetectMode), EnumSerializer(SubtitleDetectMode))

    # ============ 动态水印处理深度（0-100 连续滑块）============
    # 0=最快(低VRAM), 25=轻度, 50=标准, 75=深度, 100=极致(最强效果/最大VRAM)
    processingDepth = RangeConfigItem("Main", "ProcessingDepth", 50, RangeValidator(0, 100))

    # ============ 资源管理总开关 ============
    enableResourceManagement = ConfigItem("Main", "EnableResourceManagement", False, BoolValidator())

    # ============ 资源调配等级 ============
    # performance=性能优先, balanced=平衡, power_saving=最节约资源
    resourceProfile = OptionsConfigItem("Main", "ResourceProfile", "balanced",
        OptionsValidator(["performance", "balanced", "power_saving"]))

    # ============ VRAM 被动监控 ============
    # 开启后，每次处理视频时自动采样 GPU 显存峰值，写入 vram_records.json 供参考表使用
    enableVramMonitoring = ConfigItem("Main", "EnableVramMonitoring", False, BoolValidator())

    # ============ 锁定专用显存 ============
    # 开启后锁定 GPU 专用显存上限，在专用显存耗尽前不使用共享系统内存
    # 可避免 Windows WDDM 驱动将部分数据溢出到慢速共享内存导致性能骤降
    lockDedicatedVram = ConfigItem("Main", "LockDedicatedVram", True, BoolValidator())

    # 【设置像素点偏差】
    # 用于判断是不是非字幕区域(一般认为字幕文本框的长度是要大于宽度的，如果字幕框的高大于宽，且大于的幅度超过指定像素点大小，则认为是错误检测)
    subtitleYXAxisDifferencePixel = RangeConfigItem("Main", "SubtitleYXAxisDifferencePixel", 10, RangeValidator(0, 300))
    # 用于放大mask大小，防止自动检测的文本框过小，inpaint阶段出现文字边，有残留
    subtitleAreaDeviationPixel = RangeConfigItem("Main", "SubtitleAreaDeviationPixel", 10, RangeValidator(1, 300))
    # 同于判断两个文本框是否为同一行字幕，高度差距指定像素点以内认为是同一行
    subtitleAreaYAxisDifferencePixel = RangeConfigItem("Main", "SubtitleAreaYAxisDifferencePixel", 20, RangeValidator(0, 300))
    # 用于判断两个字幕文本的矩形框是否相似，如果X轴和Y轴偏差都在指定阈值内，则认为时同一个文本框
    subtitleAreaPixelToleranceYPixel = RangeConfigItem("Main", "SubtitleAreaPixelToleranceYPixel", 20, RangeValidator(0, 300))
    subtitleAreaPixelToleranceXPixel = RangeConfigItem("Main", "SubtitleAreaPixelToleranceXPixel", 20, RangeValidator(0, 300))
    subtitleTimelineBackwardFrameCount = RangeConfigItem("Main", "SubtitleTimelineBackwardFrameCount", 3, RangeValidator(0, 300))
    subtitleTimelineForwardFrameCount = RangeConfigItem("Main", "subtitleTimelineForwardFrameCount", 3, RangeValidator(0, 300))
    # 以下参数仅适用STTN算法时，才生效
    """
    1. STTN_SKIP_DETECTION
    含义：是否使用跳过检测
    效果：设置为True跳过字幕检测，会省去很大时间，但是可能误伤无字幕的视频帧或者会导致去除的字幕漏了

    2. STTN_NEIGHBOR_STRIDE
    含义：相邻帧数步长, 如果需要为第50帧填充缺失的区域，STTN_NEIGHBOR_STRIDE=5，那么算法会使用第45帧、第40帧等作为参照。
    效果：用于控制参考帧选择的密度，较大的步长意味着使用更少、更分散的参考帧，较小的步长意味着使用更多、更集中的参考帧。

    3. STTN_REFERENCE_LENGTH
    含义：参数帧数量，STTN算法会查看每个待修复帧的前后若干帧来获得用于修复的上下文信息
    效果：调大会增加显存占用，处理效果变好，但是处理速度变慢

    4. STTN_MAX_LOAD_NUM
    含义：STTN算法每次最多加载的视频帧数量
    效果：设置越大速度越慢，但效果越好
    注意：要保证STTN_MAX_LOAD_NUM大于STTN_NEIGHBOR_STRIDE和STTN_REFERENCE_LENGTH
    """
    # 参考帧步长
    sttnNeighborStride = RangeConfigItem("Sttn", "NeighborStride", 5, RangeValidator(1, 100))
    # 参考帧数量
    sttnReferenceLength = RangeConfigItem("Sttn", "ReferenceLength", 10, RangeValidator(1, 100))
    # 设置STTN算法最大同时处理的帧数量
    sttnMaxLoadNum = RangeConfigItem("Sttn", "MaxLoadNum", 50, RangeValidator(1, 300))
    def getSttnMaxLoadNum(self):
        """获取 STTN 最大同时处理帧数（lambda 改为方法，避免闭包问题）"""
        return max(self.sttnMaxLoadNum.value, self.sttnNeighborStride.value * self.sttnReferenceLength.value)
    
    # 以下参数仅适用PROPAINTER算法时，才生效
    # 【根据自己的GPU显存大小设置】最大同时处理的图片数量，设置越大处理效果越好，但是要求显存越高
    # 1280x720p视频设置80需要25G显存，设置50需要19G显存
    # 720x480p视频设置80需要8G显存，设置50需要7G显存
    propainterMaxLoadNum = RangeConfigItem("ProPainter", "MaxLoadNum", 70, RangeValidator(1, 300))    # ProPainter mask膨胀像素数：越大掩膜越宽，动态/半透明水印清理更干净但可能过度修复
    propainterMaskDilates = RangeConfigItem("ProPainter", "MaskDilates", 8, RangeValidator(0, 30))
    # ProPainter 光流mask膨胀像素数：防止光流在mask边缘计算不准确
    propainterFlowMaskDilates = RangeConfigItem("ProPainter", "FlowMaskDilates", 12, RangeValidator(0, 40))
    # E2FGVI 最大同时处理帧数，越大效果越好显存越高
    # 1080p建议8-16，720p建议16-32，4090建议32-50
    e2fgviMaxLoadNum = RangeConfigItem("E2FGVI", "MaxLoadNum", 8, RangeValidator(1, 200))

    # 是否使用硬件加速
    hardwareAcceleration = ConfigItem("Main", "HardwareAcceleration", HARDWARD_ACCELERATION_OPTION, BoolValidator())
    
    # 最大并发处理任务数 (1-8)，提高 GPU 利用率
    maxConcurrentTasks = OptionsConfigItem("Main", "MaxConcurrentTasks", 1, OptionsValidator([1, 2, 3, 4, 5, 6, 7, 8]))
    
    # ==================== 变形水印检测配置 ====================
    # 是否启用水印模板匹配检测
    enableWatermarkDetection = ConfigItem("Watermark", "EnableWatermarkDetection", False, BoolValidator())
    # 水印模板图片路径（留空则禁用模板匹配）
    watermarkTemplatePath = ConfigItem("Watermark", "TemplatePath", "", ConfigValidator())
    # 模板匹配阈值 (0.0~1.0)，越高越严格
    watermarkMatchThreshold = RangeConfigItem("Watermark", "MatchThreshold", 0.65, RangeValidator(0.3, 0.95))
    # 多尺度检测：最小缩放比例
    watermarkScaleMin = RangeConfigItem("Watermark", "ScaleMin", 0.3, RangeValidator(0.1, 1.0))
    # 多尺度检测：最大缩放比例
    watermarkScaleMax = RangeConfigItem("Watermark", "ScaleMax", 2.0, RangeValidator(1.0, 5.0))
    # 多尺度检测：缩放步数
    watermarkScaleSteps = RangeConfigItem("Watermark", "ScaleSteps", 12, RangeValidator(3, 30))
    # 多角度检测：最小旋转角度（度）
    watermarkRotationMin = RangeConfigItem("Watermark", "RotationMin", -45, RangeValidator(-180, 0))
    # 多角度检测：最大旋转角度（度）
    watermarkRotationMax = RangeConfigItem("Watermark", "RotationMax", 45, RangeValidator(0, 180))
    # 多角度检测：旋转步数
    watermarkRotationSteps = RangeConfigItem("Watermark", "RotationSteps", 15, RangeValidator(4, 36))
    # 是否启用透视变换检测
    watermarkEnablePerspective = ConfigItem("Watermark", "EnablePerspective", True, BoolValidator())
    # 是否启用特征点匹配检测（SIFT/ORB）
    watermarkEnableFeatureMatch = ConfigItem("Watermark", "EnableFeatureMatch", False, BoolValidator())
    # 每帧最多返回的水印检测结果数
    watermarkMaxResults = RangeConfigItem("Watermark", "MaxResults", 5, RangeValidator(1, 20))
    # 多边形 mask 额外扩展像素数
    watermarkPolygonExpandPixels = RangeConfigItem("Watermark", "PolygonExpandPixels", 5, RangeValidator(0, 30))
    # 邻近帧全策略检测窗口（秒）：检测到文字时，前后N秒内的帧执行全策略水印检测
    watermarkProximityWindowSeconds = RangeConfigItem("Watermark", "ProximityWindowSeconds", 2.0, RangeValidator(0.0, 10.0))
    # 检测灵敏度: low=0.75(严格), medium=0.65(默认), high=0.55(宽松)
    watermarkDetectionSensitivity = OptionsConfigItem("Watermark", "DetectionSensitivity", "medium", OptionsValidator(["low", "medium", "high"]))
    # 水印推测：提取文字颜色，在邻近帧中查找同色块作为水印
    watermarkColorPropagationEnabled = ConfigItem("Watermark", "ColorPropagationEnabled", False, BoolValidator())
    # 颜色匹配容差 (0-100)，越大匹配越宽松
    watermarkColorTolerance = RangeConfigItem("Watermark", "ColorTolerance", 30, RangeValidator(5, 80))
    # 同色块最小面积（像素），过滤噪点
    watermarkColorMinArea = RangeConfigItem("Watermark", "ColorMinArea", 200, RangeValidator(50, 5000))
    # 水印强力清扫：在邻近帧中以0.1秒间隔采样区域图像，通过时间差分检测静态水印
    watermarkPowerSweepEnabled = ConfigItem("Watermark", "PowerSweepEnabled", False, BoolValidator())
    # 采样间隔（秒），默认0.1秒
    watermarkPowerSweepInterval = RangeConfigItem("Watermark", "PowerSweepInterval", 0.1, RangeValidator(0.05, 1.0))
    # 变化程度阈值 (0~255)，逐帧差分值高于此值视为快速变化目标，越高越严格
    watermarkPowerSweepChangeLevel = RangeConfigItem("Watermark", "PowerSweepChangeLevel", 60, RangeValidator(10, 200))
    # 水印区域全部清扫：文字帧前后N秒内，将整个文字区域直接标记为水印去除
    watermarkRegionFullSweepEnabled = ConfigItem("Watermark", "RegionFullSweepEnabled", False, BoolValidator())
    # 强制清理区域水印：文字帧前后N秒内，强制用处理模型重绘整个文字区域
    watermarkForceRegionInpaintEnabled = ConfigItem("Watermark", "ForceRegionInpaintEnabled", False, BoolValidator())
    # 跟踪浮动水印
    watermarkTrackFloating = ConfigItem("Watermark", "TrackFloating", False, BoolValidator())
    # 强力去水印模式：增加 mask 膨胀和清扫强度
    watermarkAggressiveMode = ConfigItem("Watermark", "AggressiveMode", False, BoolValidator())
    # 强制全帧遮罩：在用户框选的区域上，对所有帧强制生成遮罩（不依赖OCR检测）
    forceSubAreaMaskAllFrames = ConfigItem("Inpaint", "ForceSubAreaMaskAllFrames", False, BoolValidator())
    # 时序中值滤波：对遮罩区域做跨帧中值滤波，消除变色/变形文字
    temporalMedianFilter = ConfigItem("Inpaint", "TemporalMedianFilter", False, BoolValidator())
    # 时序滤波窗口大小（帧数）
    temporalMedianWindow = RangeConfigItem("Inpaint", "TemporalMedianWindow", 15, RangeValidator(3, 61))
    # 修复后处理锐化强度 (0-100)
    postSharpenStrength = RangeConfigItem("Inpaint", "PostSharpenStrength", 40, RangeValidator(0, 100))
    # 纹理传输修复强度 (0=关闭, 100=最大)
    textureTransferStrength = RangeConfigItem("Inpaint", "TextureTransferStrength", 0, RangeValidator(0, 100))
    # 尝试扫除模式：强力去除半透明水印，使用精确遮罩 + 时序滤波 + 零膨胀
    sweepModeEnabled = ConfigItem("Inpaint", "SweepModeEnabled", False, BoolValidator())
    # 扫除重复次数：将输出视频再次作为输入反复扫除，逐步清除顽固水印
    sweepIterations = RangeConfigItem("Inpaint", "SweepIterations", 1, RangeValidator(1, 10))

    # ==================== 视频增强（超分辨率 + 帧插值） ====================
    # Real-ESRGAN 超分辨率: https://github.com/xinntao/Real-ESRGAN
    enableSuperResolution = ConfigItem("Enhancement", "EnableSuperResolution", False, BoolValidator())
    # 超分模型名称（含 Real-ESRGAN + waifu2x 两种算法）
    # Real-ESRGAN: Python CUDA / ncnn Vulkan 后端
    # waifu2x:     waifu2x-ncnn-vulkan (单独的 Vulkan 算法，选择后自动使用)
    srModelName = OptionsConfigItem("Enhancement", "SRModelName", "realesr-animevideov3",
        OptionsValidator([
            "realesr-animevideov3", "RealESRGAN_x4plus", "RealESRGAN_x2plus", "realesr-general-x4v3",
            "waifu2x-cunet", "waifu2x-upconv_anime",
        ]))
    # 分块大小（0 = 不分块）
    srTileSize = RangeConfigItem("Enhancement", "SRTileSize", 0, RangeValidator(0, 1024))
    # 超分后端（仅 Real-ESRGAN 有效，waifu2x 模型自动走 Vulkan）
    srBackend = OptionsConfigItem("Enhancement", "SRBackend", "python",
        OptionsValidator(["python", "ncnn"]))
    # 是否使用半精度推理
    srUseHalf = ConfigItem("Enhancement", "SRUseHalf", True, BoolValidator())
    # RIFE 帧插值: https://github.com/hzwer/ECCV2022-RIFE
    enableFrameInterpolation = ConfigItem("Enhancement", "EnableFrameInterpolation", False, BoolValidator())
    # 帧率倍增系数
    fiMultiplier = OptionsConfigItem("Enhancement", "FIMultiplier", 2, OptionsValidator([2, 3, 4, 5, 6, 7, 8]))
    # RIFE ncnn 模型名称（与 Flowframes 兼容）
    fiModelName = OptionsConfigItem("Enhancement", "FIModelName", "rife-v3.1",
        OptionsValidator(["rife-v3.1", "rife-v3.0", "rife-v2.4", "rife-anime"]))
    # RIFE ncnn 线程参数: load:proc:save，越大越快但越耗显存
    # 推荐: 保守=1:2:2, 平衡=2:4:4, 激进=4:8:8
    fiNcnnThreads = ConfigItem("Enhancement", "FINcnnThreads", "1:2:2", ConfigValidator())
    # RIFE 模型目录（留空使用内置）
    fiModelDir = ConfigItem("Enhancement", "FIModelDir", "", ConfigValidator())
    # 先超分再插帧（否则先插帧再超分）
    enhanceSrFirst = ConfigItem("Enhancement", "EnhanceSrFirst", True, BoolValidator())
    # 帧插值后端: python = Python CUDA, ncnn = rife-ncnn-vulkan
    fiBackend = OptionsConfigItem("Enhancement", "FIBackend", "python",
        OptionsValidator(["python", "ncnn"]))

    # 启动时检查应用更新
    checkUpdateOnStartup = ConfigItem("Main", "CheckUpdateOnStartup", True, BoolValidator())

    # 视频保存目录
    saveDirectory = ConfigItem("Main", "SaveDirectory", "", ConfigValidator())

    # ============ UI 折叠状态持久化 ============
    removalCardCollapsed = ConfigItem("UI", "RemovalCardCollapsed", False, BoolValidator())
    extractCardCollapsed = ConfigItem("UI", "ExtractCardCollapsed", False, BoolValidator())
    watermarkSectionCollapsed = ConfigItem("UI", "WatermarkSectionCollapsed", False, BoolValidator())

    # ============ 字幕提取模式 ============
    subtitleExtractMode = OptionsConfigItem("SubtitleExtract", "Mode", "row",
        OptionsValidator(["row", "column", "float"]))
    # ============ 启动弹窗 ============
    skipStartupDialog = ConfigItem("UI", "SkipStartupDialog", False, BoolValidator())
    startupDonateCount = ConfigItem("UI", "StartupDonateCount", 0, RangeValidator(0, 99))

CONFIG_FILE = 'config/config.json'
config = Config()
qconfig.load(CONFIG_FILE, config)

# 读取界面语言配置
tr = configparser.ConfigParser()

TRANSLATION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'interface', f"{config.interface.value}.ini")
tr.read(TRANSLATION_FILE, encoding='utf-8')

# 项目的base目录
BASE_DIR = str(Path(os.path.abspath(__file__)).parent)

os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'