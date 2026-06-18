import os
os.environ.setdefault('OPENCV_FFMPEG_THREADS', '1')
os.environ.setdefault('OPENCV_FFMPEG_CAPTURE_OPTIONS', 'err_detect;ignore_err|flags2;showall')
import cv2
import threading
import multiprocessing
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
                               QTabWidget, QScrollArea, QSizePolicy)
from PySide6.QtCore import Slot, QRect, Signal, Qt, QMetaObject, Q_ARG
from PySide6 import QtWidgets
from qfluentwidgets import (PushButton, CardWidget, PlainTextEdit, FluentIcon,
                            BodyLabel, InfoBar, SwitchButton,
                            PrimaryPushButton)
from PySide6.QtGui import QColor
from ui.component.func_card import CollapsibleFuncCard, SettingRow, HelpButton, SectionHeader
from ui.component.video_display_component import VideoDisplayComponent
from ui.component.task_list_component import TaskListComponent, TaskStatus, TaskOptions
from ui.icon.my_fluent_icon import MyFluentIcon
from backend.config import config, tr
from backend.tools.subtitle_remover_remote_call import SubtitleRemoverRemoteCall
from backend.tools.process_manager import ProcessManager
from backend.tools.common_tools import get_readable_path, is_image_file, read_image
from backend.tools.constant import SubtitleDetectMode, InpaintMode

# ─── 字幕检测模型中文名映射 ───
_SUBTITLE_MODEL_NAMES = {
    SubtitleDetectMode.PP_OCRv4_SERVER:  "PP-OCRv4 Server",
    SubtitleDetectMode.PP_OCRv4_MOBILE:  "PP-OCRv4 Mobile",
    SubtitleDetectMode.PP_OCRv5_SERVER:  "PP-OCRv5 Server",
    SubtitleDetectMode.PP_OCRv5_MOBILE:  "PP-OCRv5 Mobile",
    SubtitleDetectMode.SAM2_TINY:        "SAM2-Tiny",
    SubtitleDetectMode.SAM2_SMALL:       "SAM2-Small",
    SubtitleDetectMode.SAM2_BASE:        "SAM2-Base",
    SubtitleDetectMode.SAM2_LARGE:       "SAM2-Large",
}
_SUBTITLE_MODEL_LIST = list(_SUBTITLE_MODEL_NAMES.keys())

class _SimpleCollapsible(QtWidgets.QWidget):
    """行内可折叠子区（如：水印检测），带▶/▼大箭头 + 持久化 + 视觉层次"""

    def __init__(self, title, config_item=None, parent=None, indent=84):
        super().__init__(parent)
        self._config_item = config_item
        if config_item is not None:
            self._expanded = not config_item.value
        else:
            self._expanded = False

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # 标题行（可点击）- 更大
        self._header = QtWidgets.QWidget()
        self._header.setCursor(Qt.PointingHandCursor)
        self._header.setFixedHeight(30)
        self._header.mousePressEvent = lambda e: self._toggle()
        hl = QtWidgets.QHBoxLayout(self._header)
        hl.setContentsMargins(indent, 0, 0, 0)
        self._arrow = QtWidgets.QLabel("▶")
        self._arrow.setStyleSheet("font-size: 12px; color: #4aa3df; font-weight: bold;")
        hl.addWidget(self._arrow)
        t = BodyLabel(title)
        t.setStyleSheet("font-size: 12px; font-weight: bold; color: #ccc;")
        hl.addWidget(t)
        hl.addStretch()
        layout.addWidget(self._header)

        self._content = QtWidgets.QWidget()
        self._content_layout = QtWidgets.QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(12, 0, 0, 0)
        self._content_layout.setSpacing(4)
        # 添加左边界线视觉效果
        self._content.setStyleSheet(
            "border-left: 2px solid #333; padding-left: 4px;")
        self._content.setVisible(self._expanded)
        layout.addWidget(self._content)
        self._update_arrow()

    def addWidget(self, w):
        self._content_layout.addWidget(w)

    @property
    def content_layout(self):
        return self._content_layout

    def _toggle(self):
        self._expanded = not self._expanded
        self._content.setVisible(self._expanded)
        self._update_arrow()
        if self._config_item is not None:
            from qfluentwidgets import qconfig
            qconfig.set(self._config_item, not self._expanded)

    def _update_arrow(self):
        self._arrow.setText("▼" if self._expanded else "▶")


class HomeInterface(QWidget):
    # 信号增加 task_index 以支持并发任务
    progress_signal = Signal(int, int, bool)
    append_log_signal = Signal(int, list)
    update_preview_with_comp_signal = Signal(int, list)
    task_error_signal = Signal(int, object)
    # 用于后台线程安全地更新按钮文本/启用状态
    _btn_text_signal = Signal(object, str)    # (button, text)
    _btn_enable_signal = Signal(object, bool) # (button, enabled)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("HomeInterface")
        self.video_path = None
        self.video_cap = None
        self.fps = None
        self.frame_count = None
        self.frame_width = None
        self.frame_height = None
        self.se = None
        self.xmin = self.xmax = self.ymin = self.ymax = None
        self.auto_scroll = True
        self.running_task = False
        self.running_process = None
        self.running_processes = []
        self.current_processing_task_index = -1

        self.__init_widgets()
        self.progress_signal.connect(self.update_progress)
        self.append_log_signal.connect(self.append_log)
        self.update_preview_with_comp_signal.connect(self.update_preview_with_comp)
        self.task_error_signal.connect(self.on_task_error)
        # 线程安全按钮操作
        self._btn_text_signal.connect(lambda btn, txt: btn.setText(txt))
        self._btn_enable_signal.connect(lambda btn, en: btn.setEnabled(en))

    def _build_inpaint_model_help(self):
        return (
            "<b>图像修复算法选择</b><br><br>"
            "• <b>STTN (智能擦除)</b>：基于光流的时序修复，速度快，适合普通字幕<br>"
            "• <b>STTN (字幕检测)</b>：先检测字幕区域再修复，适合固定位置字幕<br>"
            "• <b>LaMa</b>：适合动画/卡通类视频，速度一般<br>"
            "• <b>ProPainter</b>：对剧烈运动视频效果好，显存需求高<br>"
            "• <b>E2FGVI</b>：高质量时序修复，适合精细场景<br>"
            "• <b>OpenCV</b>：传统方法，速度最快但效果有限"
        )

    def _build_detect_model_help(self):
        return (
            "<b>字幕检测模型选择</b><br><br>"
            "• <b>PP-OCRv4/v5 Server</b>：高精度 OCR 检测，精度优先<br>"
            "• <b>PP-OCRv4/v5 Mobile</b>：轻量 OCR 检测，速度优先<br>"
            "• <b>SAM2-Tiny/Small</b>：基于分割的检测，适合不规则水印<br>"
            "• <b>SAM2-Base/Large</b>：高精度分割检测，显存需求高"
        )

    def __init_widgets(self):
        """创建主页面 — 新布局"""
        # ═══════════════════════════════════════════
        # 主分割器（水平）：左 = 视频+底栏，右 = 功能区
        # ═══════════════════════════════════════════
        self._main_splitter = QSplitter(Qt.Horizontal, self)
        self._main_splitter.setHandleWidth(4)
        self._main_splitter.setChildrenCollapsible(False)

        # ═══════════════════════
        # 左面板：视频 + 底栏（纵向分割器）
        # ═══════════════════════
        self._left_splitter = QSplitter(Qt.Vertical)
        self._left_splitter.setHandleWidth(4)
        self._left_splitter.setChildrenCollapsible(False)

        # ── 视频预览 ──
        self.video_display_component = VideoDisplayComponent(self)
        self.video_display_component.ab_sections_changed.connect(self.ab_sections_changed)
        self.video_display_component.selections_changed.connect(self.selections_changed)
        self.video_display = self.video_display_component.video_display
        self.video_slider = self.video_display_component.video_slider
        self.video_slider.valueChanged.connect(self.slider_changed)
        self._left_splitter.addWidget(self.video_display_component)

        # ── 底栏 Tab：任务列表 / 输出日志 / 字幕文本 ──
        self._bottom_tabs = QTabWidget()
        self._bottom_tabs.setTabPosition(QTabWidget.South)
        self._bottom_tabs.setDocumentMode(True)

        # Tab 1：任务列表
        self.task_list_component = TaskListComponent(self)
        self.task_list_component.task_selected.connect(self.on_task_selected)
        self.task_list_component.task_deleted.connect(self.on_task_deleted)
        # 让表格内容自动换行
        self.task_list_component.table.setTextElideMode(Qt.ElideNone)
        self._bottom_tabs.addTab(self.task_list_component, "📋 任务列表")

        # Tab 2：输出日志
        self.output_text = PlainTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.document().setDocumentMargin(6)
        # 开启自动换行
        self.output_text.setLineWrapMode(PlainTextEdit.WidgetWidth)
        self.output_text.verticalScrollBar().valueChanged.connect(self.on_scroll_change)
        self._bottom_tabs.addTab(self.output_text, "📝 输出日志")

        # Tab 3：字幕文本
        self.subtitle_text = PlainTextEdit()
        self.subtitle_text.setPlaceholderText("字幕提取结果将显示在此处…")
        self.subtitle_text.document().setDocumentMargin(6)
        self.subtitle_text.setLineWrapMode(PlainTextEdit.WidgetWidth)
        self._bottom_tabs.addTab(self.subtitle_text, "📄 字幕文本")

        self._left_splitter.addWidget(self._bottom_tabs)
        # 初始比例：视频 70%，底栏 30%
        self._left_splitter.setSizes([700, 300])

        self._main_splitter.addWidget(self._left_splitter)

        # ═══════════════════════
        # 右面板：两个功能大区（可滚动）
        # ═══════════════════════
        self._right_scroll = QScrollArea()
        self._right_scroll.setWidgetResizable(True)
        self._right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._right_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._right_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)

        right_content = QtWidgets.QWidget()
        self._right_layout = QtWidgets.QVBoxLayout(right_content)
        self._right_layout.setSpacing(8)
        self._right_layout.setContentsMargins(4, 0, 0, 0)

        # ─────────────────────────────────────────
        # 功能区 1：视频去字幕水印功能
        # ─────────────────────────────────────────
        self.func_removal = CollapsibleFuncCard(
            "视频去字幕水印功能", "🎬",
            config_item=config.removalCardCollapsed,
            parent=right_content)
        self._build_removal_card()
        self._right_layout.addWidget(self.func_removal)

        # ─────────────────────────────────────────
        # 功能区 2：字幕提取
        # ─────────────────────────────────────────
        self.func_extract = CollapsibleFuncCard(
            "字幕提取", "📝",
            config_item=config.extractCardCollapsed,
            parent=right_content)
        self._build_extract_card()
        self._right_layout.addWidget(self.func_extract)

        self._right_layout.addStretch()

        self._right_scroll.setWidget(right_content)
        self._main_splitter.addWidget(self._right_scroll)
        # 初始比例：左 55%，右 45%
        self._main_splitter.setSizes([550, 450])

        # 主布局
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.addWidget(self._main_splitter)

    def _build_depth_help(self):
        return ("<b>处理深度 (0-100)</b><br><br>"
                "控制所有模型的参数插值:<br>"
                "• <b>0-25</b>：极快模式，低 VRAM，最低效果<br>"
                "• <b>25-50</b>：轻度模式，平衡速度与效果<br>"
                "• <b>50-75</b>：标准模式，推荐日常使用<br>"
                "• <b>75-100</b>：深度模式，高 VRAM，最佳效果<br><br>"
                "拖动滑块实时调整 mask 膨胀、时间线范围、参考帧数等参数。")

    def _build_hw_accel_help(self):
        return ("<b>硬件加速</b><br><br>"
                "启用 GPU 硬件加速（如 CUDA）来提升模型推理速度。<br>"
                "关闭后使用 CPU 运算，速度较慢但兼容性更好。")

    def _build_concurrent_help(self):
        return ("<b>最大并发任务数</b><br><br>"
                "同时处理多个视频任务以充分利用 GPU。<br>"
                "• 数值越大，GPU 利用率越高<br>"
                "• 超出显存容量的选项会标红 ⚠️<br>"
                "• VRAM 监控开启后可自动采集真实数据")

    def _build_vram_monitor_help(self):
        return ("<b>VRAM 被动监控</b><br><br>"
                "开启后，每次处理视频时自动采样 GPU 显存峰值，<br>"
                "写入 <code>vram_records.json</code>。<br><br>"
                "采集的数据会覆盖内置基准值，用于推荐值和危险标记。<br>"
                "相同配置不会重复采集，有 OOM 记录会标记 ☠️。")

    def _build_extract_help(self):
        return ("<b>字幕提取</b><br><br>"
                "使用 OCR 模型从视频中自动检测并识别字幕文本。<br><br>"
                "• <b>一键提取</b>：使用当前选中的检测模型提取全部字幕<br>"
                "• <b>导出文本</b>：导出为无时间轴 .txt 文本文件<br>"
                "• <b>导出 SRT</b>：导出为标准 .srt 字幕文件（含时间轴）<br>"
                "• <b>联合校对</b>：用 3 个不同模型分别提取后合并择优<br><br>"
                "<b>提取模式</b><br>"
                "• <b>按行提取</b>：按 Y 轴分组（默认），适合横向字幕<br>"
                "• <b>按列提取</b>：按 X 轴分组，适合竖向排列文字<br>"
                "• <b>提取浮动字幕</b>：位置聚类合并，适合动态/浮动水印字幕")

    # ═══════════════════════════════════════════
    #  功能区 1：视频去字幕水印功能
    # ═══════════════════════════════════════════
    def _build_removal_card(self):
        """构建视频去字幕水印卡的内容"""
        card = self.func_removal

        # ── 核心设置 ──
        card.addWidget(SectionHeader("核心设置"))

        # 修复算法
        inpaint_combo = QtWidgets.QComboBox()
        inpaint_combo.addItems([m.value for m in config.inpaintMode.validator.options])
        inpaint_combo.setCurrentText(config.inpaintMode.value.value)

        self._e2fgvi_warn = BodyLabel("⚠️ E2FGVI 需要 48GB+ 显存")
        self._e2fgvi_warn.setStyleSheet("color: #e81123; font-size: 11px; padding-left: 84px;")
        self._e2fgvi_warn.setWordWrap(True)
        self._e2fgvi_warn.setVisible(False)

        def _on_inpaint_changed(text):
            config.set(config.inpaintMode,
                next(m for m in config.inpaintMode.validator.options if m.value == text))
            is_e2fgvi = "e2fgvi" in text.lower()
            self._e2fgvi_warn.setVisible(is_e2fgvi)
            if is_e2fgvi:
                try:
                    from backend.tools.hardware_accelerator import HardwareAccelerator
                    accel = HardwareAccelerator.instance()
                    vram = accel.get_gpu_vram_gb()
                    if vram >= 48:
                        self._e2fgvi_warn.setText("✅ E2FGVI (显存充足)")
                        self._e2fgvi_warn.setStyleSheet("color: #16ab39; font-size: 11px; padding-left: 84px;")
                    else:
                        self._e2fgvi_warn.setText(f"⚠️ E2FGVI 需要 48GB+ 显存 (当前 {vram:.0f}GB)")
                        self._e2fgvi_warn.setStyleSheet("color: #e81123; font-size: 11px; padding-left: 84px;")
                except Exception:
                    pass
            self._on_vram_config_changed()

        inpaint_combo.currentTextChanged.connect(_on_inpaint_changed)
        card.addWidget(SettingRow("修复算法", inpaint_combo,
            "修复算法说明", self._build_inpaint_model_help()))
        card.addWidget(self._e2fgvi_warn)

        # 检测模型
        detect_combo = QtWidgets.QComboBox()
        detect_combo.addItems([m.value for m in config.subtitleDetectMode.validator.options])
        detect_combo.setCurrentText(config.subtitleDetectMode.value.value)
        detect_combo.currentTextChanged.connect(
            lambda t: (config.set(config.subtitleDetectMode,
                next(m for m in config.subtitleDetectMode.validator.options if m.value == t)),
                self._on_vram_config_changed()))
        card.addWidget(SettingRow("检测模型", detect_combo,
            "检测模型说明", self._build_detect_model_help()))

        # 处理深度滑块 — 更大滑块手柄 + ? 帮助
        depth_row = QtWidgets.QHBoxLayout()
        depth_row.setSpacing(6)
        dl = BodyLabel("处理深度")
        dl.setFixedWidth(80)
        dl.setStyleSheet("font-size: 12px;")
        depth_row.addWidget(dl)
        depth_slider = QtWidgets.QSlider(Qt.Horizontal)
        depth_slider.setRange(0, 100)
        depth_slider.setValue(config.processingDepth.value)
        depth_slider.valueChanged.connect(lambda v: config.set(config.processingDepth, v))
        # 大滑块手柄样式
        depth_slider.setStyleSheet("""
            QSlider::handle:horizontal {
                background: #4aa3df;
                border: 1px solid #3a8fc9;
                width: 18px;
                height: 18px;
                margin: -6px 0;
                border-radius: 9px;
            }
            QSlider::handle:horizontal:hover {
                background: #5cb3ef;
                width: 20px;
                height: 20px;
                margin: -7px 0;
                border-radius: 10px;
            }
            QSlider::sub-page:horizontal {
                background: #4aa3df;
                border-radius: 3px;
            }
            QSlider::add-page:horizontal {
                background: #444;
                border-radius: 3px;
            }
        """)
        depth_row.addWidget(depth_slider, 1)
        self._depth_val_label = BodyLabel(str(config.processingDepth.value))
        self._depth_val_label.setFixedWidth(30)
        self._depth_val_label.setAlignment(Qt.AlignCenter)
        depth_row.addWidget(self._depth_val_label)
        # ? 帮助按钮
        depth_help = HelpButton("处理深度说明", self._build_depth_help())
        depth_row.addWidget(depth_help)
        depth_slider.valueChanged.connect(lambda v: self._depth_val_label.setText(str(v)))
        dw = QtWidgets.QWidget()
        dw.setLayout(depth_row)
        dw.setMinimumHeight(36)
        card.addWidget(dw)

        # ── 性能设置 ──
        card.addWidget(SectionHeader("性能设置"))

        # 硬件加速 + ?
        hw_switch = SwitchButton()
        hw_switch.setChecked(config.hardwareAcceleration.value)
        hw_switch.checkedChanged.connect(lambda v: config.set(config.hardwareAcceleration, v))
        card.addWidget(SettingRow("硬件加速", hw_switch,
            "硬件加速说明", self._build_hw_accel_help()))

        # 最大并发任务数 + ?
        self._concurrent_combo = QtWidgets.QComboBox()
        for n in range(1, 9):
            self._concurrent_combo.addItem(str(n), n)
        self._concurrent_combo.setCurrentIndex(config.maxConcurrentTasks.value - 1)
        self._concurrent_combo.currentIndexChanged.connect(
            lambda i: (config.set(config.maxConcurrentTasks, i + 1), self._refresh_vram_display()))
        card.addWidget(SettingRow("并发任务", self._concurrent_combo,
            "并发任务说明", self._build_concurrent_help()))
        self._color_concurrency_items()

        # ── 水印检测 ──
        wm_section = _SimpleCollapsible("水印检测",
            config_item=config.watermarkSectionCollapsed)
        from ui.component.watermark_template_widget import WatermarkTemplateWidget
        self.watermark_template_widget = WatermarkTemplateWidget(
            video_display_component=self.video_display_component,
            parent=wm_section.content_layout.parentWidget())
        wm_section.addWidget(self.watermark_template_widget)
        try:
            self.video_display_component.watermark_captured.connect(
                self.watermark_template_widget.set_capture_result)
        except AttributeError:
            pass
        card.addWidget(wm_section)

        # ═══════════════════════════════════════════
        #  显存估算与监控区（折叠）
        # ═══════════════════════════════════════════
        vram_section = _SimpleCollapsible("显存估算与监控")
        # GPU 总量
        self._vram_info_label = BodyLabel("🖥 GPU 显存总量: 检测中…")
        self._vram_info_label.setStyleSheet("font-size: 11px; color: #888; padding: 2px 0;")
        self._vram_info_label.setWordWrap(True)
        vram_section.addWidget(self._vram_info_label)

        # 当前配置估算
        self._vram_est_label = BodyLabel("📊 当前配置预估: 计算中…")
        self._vram_est_label.setStyleSheet("font-size: 11px; padding: 2px 0;")
        self._vram_est_label.setWordWrap(True)
        self._vram_est_label.setTextFormat(Qt.RichText)
        vram_section.addWidget(self._vram_est_label)

        # 被动监控开关 + ?
        monitor_row = QtWidgets.QHBoxLayout()
        monitor_row.setContentsMargins(0, 0, 0, 0)
        ml = BodyLabel("显存监控")
        ml.setStyleSheet("font-size: 11px;")
        monitor_row.addWidget(ml)
        self._vram_monitor_switch = SwitchButton()
        self._vram_monitor_switch.setChecked(config.enableVramMonitoring.value)
        self._vram_monitor_switch.checkedChanged.connect(
            lambda v: config.set(config.enableVramMonitoring, v))
        monitor_row.addWidget(self._vram_monitor_switch)
        monitor_row.addWidget(
            HelpButton("显存监控说明", self._build_vram_monitor_help()))
        monitor_row.addStretch()
        mw = QtWidgets.QWidget()
        mw.setLayout(monitor_row)
        mw.setMinimumHeight(26)
        vram_section.addWidget(mw)

        # 模型显存参考表
        self._vram_ref_table = QtWidgets.QTextEdit()
        self._vram_ref_table.setReadOnly(True)
        self._vram_ref_table.setMaximumHeight(180)
        self._vram_ref_table.setStyleSheet(
            "QTextEdit { background: transparent; border: none; font-size: 10px; color: #ccc; }")
        vram_section.addWidget(self._vram_ref_table)

        card.addWidget(vram_section)

        # 关联配置变更 → 刷新显存
        config.processingDepth.valueChanged.connect(self._on_vram_config_changed)
        config.inpaintMode.valueChanged.connect(self._on_vram_config_changed)
        config.subtitleDetectMode.valueChanged.connect(self._on_vram_config_changed)
        self._refresh_vram_info()
        self._refresh_vram_display()
        self._build_vram_ref_table()

        # ── 操作按钮行 ──
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(6)

        self.file_button = PushButton(tr['SubtitleExtractorGUI']['Open'])
        self.file_button.setIcon(FluentIcon.FOLDER)
        self.file_button.setMinimumHeight(34)
        self.file_button.setMinimumWidth(80)
        self.file_button.clicked.connect(self.open_file)
        btn_layout.addWidget(self.file_button)

        self.run_button = PushButton(tr['SubtitleExtractorGUI']['Run'])
        self.run_button.setIcon(FluentIcon.PLAY)
        self.run_button.setMinimumHeight(34)
        self.run_button.setMinimumWidth(80)
        self.run_button.clicked.connect(self.run_button_clicked)
        btn_layout.addWidget(self.run_button)

        self.stop_button = PushButton(tr['SubtitleExtractorGUI']['Stop'])
        self.stop_button.setIcon(MyFluentIcon.Stop)
        self.stop_button.setMinimumHeight(34)
        self.stop_button.setVisible(False)
        self.stop_button.clicked.connect(self.stop_button_clicked)
        btn_layout.addWidget(self.stop_button)
        btn_layout.addStretch()

        self.adv_btn = PushButton("⚙ 高级设置")
        self.adv_btn.setMinimumHeight(34)
        self.adv_btn.clicked.connect(self._open_advanced_settings)
        btn_layout.addWidget(self.adv_btn)

        bw = QtWidgets.QWidget()
        bw.setLayout(btn_layout)
        bw.setMinimumHeight(44)
        card.addWidget(bw)

    # ═══════════════════════════════════════════
    #  显存估算方法（从 setting_interface 恢复）
    # ═══════════════════════════════════════════
    def _on_vram_config_changed(self):
        """配置变更刷新显存估算并重绘并发选项颜色"""
        self._refresh_vram_display()
        self._color_concurrency_items()

    def _refresh_vram_info(self):
        """刷新 GPU 总量信息"""
        try:
            from backend.tools.hardware_accelerator import HardwareAccelerator
            accel = HardwareAccelerator.instance()
            gpu_vram = accel.get_gpu_vram_gb()
            gpu_name = ""
            try:
                import torch
                if accel.has_cuda():
                    gpu_name = torch.cuda.get_device_name(0)
            except Exception:
                pass
            gpu_str = f" ({gpu_name})" if gpu_name else ""
            self._vram_info_label.setText(f"🖥 GPU 显存总量: {gpu_vram:.1f} GB{gpu_str}")
        except Exception:
            self._vram_info_label.setText("🖥 GPU 显存: 无法获取")

    def _refresh_vram_display(self):
        """刷新当前配置的显存估算"""
        try:
            from backend.tools.vram_estimator import estimate_model_vram, get_vram_status_color
            est = estimate_model_vram(
                inpaint_mode=config.inpaintMode.value.value,
                detect_mode=config.subtitleDetectMode.value.value,
                concurrent_tasks=int(config.maxConcurrentTasks.value),
                processing_depth=config.processingDepth.value if hasattr(config, 'processingDepth') else 50,
            )
            color = get_vram_status_color(est["usage_pct"])
            self._vram_est_label.setText(
                f"📊 当前配置预估: 修复 {est['inpaint_gb']:.1f}GB + 检测 {est['detect_gb']:.1f}GB = "
                f"<b style='color:{color}'>{est['total_gb']:.1f}GB</b> "
                f"(占 GPU 的 {est['usage_pct']:.0f}%)"
                + (" ⚠️ 可能超出显存!" if est["over_limit"] else ""))
        except Exception:
            self._vram_est_label.setText("📊 当前配置预估: 计算失败")

    def _color_concurrency_items(self):
        """对并发任务数下拉框中超出显存的选项标红"""
        try:
            from backend.tools.vram_estimator import estimate_model_vram
            combo = self._concurrent_combo
            model = combo.model()
            if model is None:
                return
            for i in range(combo.count()):
                n = i + 1
                est = estimate_model_vram(
                    inpaint_mode=config.inpaintMode.value.value,
                    detect_mode=config.subtitleDetectMode.value.value,
                    concurrent_tasks=n,
                    processing_depth=config.processingDepth.value if hasattr(config, 'processingDepth') else 50,
                )
                item = model.item(i)
                if item is None:
                    continue
                if est["over_limit"]:
                    item.setForeground(QColor("#e81123"))
                    txt = item.text().replace(" ⚠️", "")
                    item.setText(f"{txt} ⚠️")
                else:
                    item.setForeground(QColor("#ccc"))
                    txt = item.text().replace(" ⚠️", "")
                    item.setText(txt)
        except Exception:
            pass

    def _build_vram_ref_table(self):
        """构建各模型显存参考表（实测值优先）"""
        try:
            from backend.tools.vram_estimator import _MODEL_VRAM_BASELINE_1080P, get_model_vram_baseline, get_all_model_vram_list
            from backend.tools.vram_estimator import has_real_data, get_model_danger_flags
            from backend.tools.constant import InpaintMode
            from backend.tools.hardware_accelerator import HardwareAccelerator
            accel = HardwareAccelerator.instance()
            gpu_vram = accel.get_gpu_vram_gb()

            has_real = has_real_data()
            danger_flags = get_model_danger_flags()
            source_note = "🔬真实采集" if has_real else "📦预估值"

            lines = [
                f"<table width='100%'>"
                f"<caption style='color:#888;font-size:10px'>{source_note} | GPU: {gpu_vram:.1f}GB</caption>",
                "<tr><th>类别</th><th>模型</th><th>显存(GB)</th><th>安全并发</th><th></th></tr>"
            ]
            for model_key in _MODEL_VRAM_BASELINE_1080P:
                vram = get_model_vram_baseline(model_key)
                cat = "修复" if model_key in [m.value for m in InpaintMode] else "检测"
                safe_n = max(1, int(gpu_vram / (vram * 1.1))) if vram > 0 else 99
                pct = vram / gpu_vram * 100 if gpu_vram > 0 else 999
                if pct >= 95:
                    vram_color = "#e81123"
                elif pct >= 70:
                    vram_color = "#ff8c00"
                else:
                    vram_color = "#16ab39"
                danger_mark = " ☠️" if danger_flags.get(model_key) else ""
                lines.append(
                    f"<tr><td>{cat}</td><td>{model_key}</td>"
                    f"<td style='color:{vram_color}'>{vram:.1f}GB{danger_mark}</td>"
                    f"<td>{safe_n}</td><td></td></tr>"
                )
            lines.append("</table>")
            self._vram_ref_table.setHtml("\n".join(lines))
        except Exception:
            self._vram_ref_table.setPlainText("无法加载显存参考表")

    # ═══════════════════════════════════════════
    #  功能区 2：字幕提取（VSE 风格）
    # ═══════════════════════════════════════════
    def _build_extract_card(self):
        card = self.func_extract

        # ── 主操作行 + ? 帮助 ──
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(6)

        self.extract_btn = PrimaryPushButton("一键提取")
        self.extract_btn.setIcon(FluentIcon.SEARCH)
        self.extract_btn.setMinimumHeight(34)
        self.extract_btn.clicked.connect(self._on_extract_subtitles)
        btn_row.addWidget(self.extract_btn)

        self.copy_btn = PushButton("导出文本")
        self.copy_btn.setIcon(FluentIcon.DOCUMENT)
        self.copy_btn.setMinimumHeight(34)
        self.copy_btn.clicked.connect(self._on_export_txt)
        btn_row.addWidget(self.copy_btn)

        self.export_srt_btn = PushButton("导出 SRT")
        self.export_srt_btn.setIcon(FluentIcon.SAVE)
        self.export_srt_btn.setMinimumHeight(34)
        self.export_srt_btn.clicked.connect(self._on_export_srt)
        btn_row.addWidget(self.export_srt_btn)

        # 提取模式选择
        mode_lbl = BodyLabel("模式")
        mode_lbl.setStyleSheet("font-size: 11px;")
        btn_row.addWidget(mode_lbl)
        self._extract_mode_combo = QtWidgets.QComboBox()
        self._extract_mode_combo.addItems(["按行提取", "按列提取", "提取浮动字幕"])
        self._extract_mode_combo.setCurrentIndex(0)
        self._extract_mode_combo.setFixedWidth(110)
        btn_row.addWidget(self._extract_mode_combo)

        # ? 帮助按钮
        btn_row.addWidget(HelpButton("字幕提取说明", self._build_extract_help()))
        btn_row.addStretch()

        bw = QtWidgets.QWidget()
        bw.setLayout(btn_row)
        bw.setMinimumHeight(40)
        card.addWidget(bw)

        # ── 联合校对子功能（行内可折叠）──
        self._joint_section = _SimpleCollapsible("联合校对（多模型择优）")

        # 模型选择行
        jm_container = QtWidgets.QWidget()
        jml = QtWidgets.QHBoxLayout(jm_container)
        jml.setContentsMargins(0, 0, 0, 0)
        jml.setSpacing(4)
        self._joint_model_combos = []
        for i in range(3):
            c = QtWidgets.QComboBox()
            for m in _SUBTITLE_MODEL_LIST:
                c.addItem(_SUBTITLE_MODEL_NAMES[m], m)
            c.currentIndexChanged.connect(lambda idx, cb=c: self._validate_joint_models(cb))
            self._joint_model_combos.append(c)
            lbl = BodyLabel(f"M{i+1}")
            lbl.setFixedWidth(20)
            lbl.setStyleSheet("font-size: 11px;")
            jml.addWidget(lbl)
            jml.addWidget(c, 1)
        self._joint_section.addWidget(jm_container)

        # 联合校对执行按钮
        self.joint_exec_btn = PushButton("▶ 执行校对")
        self.joint_exec_btn.setIcon(FluentIcon.UPDATE)
        self.joint_exec_btn.setMinimumHeight(28)
        self.joint_exec_btn.clicked.connect(self._on_joint_execute)
        self._joint_section.addWidget(self.joint_exec_btn)

        card.addWidget(self._joint_section)

        # ── 字幕预览 ──
        self._subtitle_preview = PlainTextEdit()
        self._subtitle_preview.setPlaceholderText("提取的字幕预览…\n支持 SRT 格式导出")
        self._subtitle_preview.setMaximumHeight(100)
        self._subtitle_preview.document().setDocumentMargin(4)
        self._subtitle_preview.setLineWrapMode(PlainTextEdit.WidgetWidth)
        card.addWidget(self._subtitle_preview)

        # 同步到左侧 Tab
        self._subtitle_preview.textChanged.connect(self._sync_subtitle_text)

    def _sync_subtitle_text(self):
        if hasattr(self, 'subtitle_text') and self.subtitle_text is not None:
            if self.subtitle_text.toPlainText() != self._subtitle_preview.toPlainText():
                self.subtitle_text.setPlainText(self._subtitle_preview.toPlainText())

    # ─── 字幕提取方法 ───
    def _on_extract_subtitles(self):
        """一键提取字幕"""
        if not self.video_path:
            self._append_output("请先打开一个视频文件")
            return

        self._append_output("开始提取字幕…")
        self.extract_btn.setEnabled(False)
        self.extract_btn.setText("提取中…")

        def _run():
            try:
                from backend.tools.subtitle_extractor import SubtitleExtractor
                extractor = SubtitleExtractor(
                    self.video_path,
                    log_callback=lambda msg: QMetaObject.invokeMethod(
                        self.output_text, "appendPlainText",
                        Qt.QueuedConnection, Q_ARG(str, f"> {msg}")),
                )
                mode_map = {"按行提取": "row", "按列提取": "column",
                            "提取浮动字幕": "float"}
                mode = mode_map.get(self._extract_mode_combo.currentText(), "row")
                results = extractor.extract(sample_interval=1, mode=mode)

                if results:
                    # 左侧 Tab "字幕文本" → SRT 格式（带时间轴）
                    srt_out = extractor.results_to_srt(results)
                    QMetaObject.invokeMethod(self.subtitle_text, "setPlainText",
                        Qt.QueuedConnection, Q_ARG(str, srt_out))
                    # 右侧预览 → 纯文本（无时间轴）
                    text_out = extractor.results_to_text(results)
                    QMetaObject.invokeMethod(self._subtitle_preview, "setPlainText",
                        Qt.QueuedConnection, Q_ARG(str, text_out))
                    QMetaObject.invokeMethod(self.output_text, "appendPlainText",
                        Qt.QueuedConnection,
                        Q_ARG(str, f"✅ 提取完成: {len(results)} 条字幕"))
                else:
                    QMetaObject.invokeMethod(self.output_text, "appendPlainText",
                        Qt.QueuedConnection, Q_ARG(str, "未识别到字幕文本"))
            except Exception as e:
                QMetaObject.invokeMethod(self.output_text, "appendPlainText",
                    Qt.QueuedConnection, Q_ARG(str, f"❌ 提取失败: {e}"))
                import traceback
                traceback.print_exc()
            finally:
                self._btn_enable_signal.emit(self.extract_btn, True)
                self._btn_text_signal.emit(self.extract_btn, "一键提取")

        import threading
        threading.Thread(target=_run, daemon=True).start()

    def _on_export_srt(self):
        """导出字幕为 SRT 格式"""
        txt = self._subtitle_preview.toPlainText()
        if not txt.strip():
            InfoBar.warning("无内容", "没有字幕可导出", duration=2000, parent=self)
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "导出字幕", "subtitles.srt", "SRT 文件 (*.srt)")
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(txt)
                InfoBar.success("已导出", f"字幕已保存到 {path}", duration=3000, parent=self)
            except Exception as e:
                InfoBar.error("导出失败", str(e), duration=3000, parent=self)

    def _on_export_txt(self):
        """导出字幕为纯文本文件"""
        txt = self._subtitle_preview.toPlainText()
        if not txt.strip():
            InfoBar.warning("无内容", "没有字幕可导出", duration=2000, parent=self)
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "导出文本", "subtitles.txt", "文本文件 (*.txt)")
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(txt)
                InfoBar.success("已导出", f"文本已保存到 {path}", duration=3000, parent=self)
            except Exception as e:
                InfoBar.error("导出失败", str(e), duration=3000, parent=self)

    def _on_joint_execute(self):
        """执行联合校对：三个模型分别提取，取出现概率最高的结果"""
        if not self.video_path:
            self._append_output("请先打开一个视频文件")
            return
        models = [c.currentText() for c in self._joint_model_combos]
        if len(set(models)) < 3:
            self._append_output("⚠️ 联合校对需要三个不同的模型")
            return
        self._append_output(f"联合校对启动: {', '.join(models)}")
        self.joint_exec_btn.setEnabled(False)
        self.joint_exec_btn.setText("校对中…")
        log = lambda msg: QMetaObject.invokeMethod(
            self.output_text, "appendPlainText",
            Qt.QueuedConnection, Q_ARG(str, msg))

        def _run():
            try:
                from backend.tools.subtitle_extractor import SubtitleExtractor
                from backend.config import config
                from backend.tools.constant import SubtitleDetectMode
                all_results = {}
                for model_name in models:
                    log(f"  ▶ 运行模型: {model_name}…")
                    # 匹配 SubtitleDetectMode：显示名如 "PP-OCRv4 Server" → 枚举值 "PP-OCRv4-Server"
                    target_mode = None
                    for m in SubtitleDetectMode:
                        display = _SUBTITLE_MODEL_NAMES.get(m, m.value)
                        if display == model_name or m.value == model_name:
                            target_mode = m
                            break
                    if target_mode is None:
                        log(f"  ⚠️ 未知模型: {model_name}，跳过")
                        continue
                    old_mode = config.subtitleDetectMode.value
                    config.set(config.subtitleDetectMode, target_mode)
                    try:
                        ext = SubtitleExtractor(self.video_path, log_callback=lambda msg: None)
                        mode_map = {"按行提取": "row", "按列提取": "column",
                                    "提取浮动字幕": "float"}
                        jm = mode_map.get(self._extract_mode_combo.currentText(), "row")
                        all_results[model_name] = ext.extract(sample_interval=3, mode=jm)
                    finally:
                        config.set(config.subtitleDetectMode, old_mode)

                merged = []
                seen = set()
                for r in sorted(
                    [r for res in all_results.values() for r in res],
                    key=lambda x: x.get("start_frame", 0)
                ):
                    if r["text"] not in seen:
                        seen.add(r["text"])
                        merged.append(r)

                if merged:
                    ext = SubtitleExtractor(self.video_path)
                    # 左侧 Tab → SRT
                    srt_out = ext.results_to_srt(merged)
                    QMetaObject.invokeMethod(self.subtitle_text, "setPlainText",
                        Qt.QueuedConnection, Q_ARG(str, srt_out))
                    # 右侧预览 → 纯文本
                    text_out = ext.results_to_text(merged)
                    QMetaObject.invokeMethod(self._subtitle_preview, "setPlainText",
                        Qt.QueuedConnection, Q_ARG(str, text_out))
                log(f"✅ 联合校对完成: 共 {len(merged)} 条字幕")
            except Exception as e:
                log(f"❌ 联合校对失败: {e}")
                import traceback
                traceback.print_exc()
            finally:
                self._btn_enable_signal.emit(self.joint_exec_btn, True)
                self._btn_text_signal.emit(self.joint_exec_btn, "▶ 执行校对")

        import threading
        threading.Thread(target=_run, daemon=True).start()

    def _validate_joint_models(self, changed_combo=None):
        selected = [c.currentData() for c in self._joint_model_combos]
        seen = {}
        for i, s in enumerate(selected):
            if s in seen:
                available = [m for m in _SUBTITLE_MODEL_LIST if m not in selected or m == s]
                for m in available:
                    if m != s:
                        self._joint_model_combos[i].setCurrentIndex(
                            _SUBTITLE_MODEL_LIST.index(m))
                        break
            seen[s] = i

    def _open_advanced_settings(self):
        parent = self.window()
        if hasattr(parent, 'advancedSettingInterface'):
            try:
                parent.switchTo(parent.advancedSettingInterface)
            except Exception:
                pass

    def on_scroll_change(self, value):
        """监控滚动条位置变化"""
        scrollbar = self.output_text.verticalScrollBar()
        if value == scrollbar.maximum():
            self.auto_scroll = True
        elif self.auto_scroll and value < scrollbar.maximum():
            self.auto_scroll = False

    def slider_changed(self, value):
        if self.video_cap is not None and self.video_cap.isOpened():
            frame_no = self.video_slider.value()
            self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
            ret, frame = self.video_cap.read()
            if ret:
                # 更新预览图像
                self.update_preview(frame)

    def ab_sections_changed(self, ab_sections):
        get_current_task_index = self.task_list_component.get_current_task_index()
        if get_current_task_index == -1:
            return
        self.task_list_component.update_task_option(get_current_task_index, TaskOptions.AB_SECTIONS, ab_sections)

    def selections_changed(self, selections):
        get_current_task_index = self.task_list_component.get_current_task_index()
        if get_current_task_index == -1:
            return
        self.task_list_component.update_task_option(get_current_task_index, TaskOptions.SUB_AREAS, selections)

    def on_task_selected(self, index, file_path):
        """处理任务被选中事件
        
        Args:
            index: 任务索引
            file_path: 文件路径
        """
        # 加载选中的视频进行预览
        self.load_video(file_path)
        ab_sections = self.task_list_component.get_task_option(index, TaskOptions.AB_SECTIONS, [])
        self.video_display_component.set_ab_sections(ab_sections)
        selections = self.task_list_component.get_task_option(index, TaskOptions.SUB_AREAS, [])
        if len(selections) <= 0:
            self.video_display_component.load_selections_from_config()
        else:
            self.video_display_component.set_selection_rects(selections)
    
    def on_task_deleted(self, index):
        """处理任务被删除事件
        
        Args:
            index: 任务索引
        """
        # 如果删除的是正在处理的任务，则需要更新状态
        if index == self.current_processing_task_index:
            self.current_processing_task_index = -1
        
        task = self.task_list_component.get_task(0)
        if task:
            # 如果还有任务，选中第一个
            self.task_list_component.select_task(0)

    def update_preview(self, frame):
        # 先缩放图像
        resized_frame = self._img_resize(frame)

        # 设置视频参数
        self.video_display_component.set_video_parameters(
            self.frame_width, self.frame_height, 
            self.scaled_width if hasattr(self, 'scaled_width') else None,
            self.scaled_height if hasattr(self, 'scaled_height') else None,
            self.border_left if hasattr(self, 'border_left') else 0,
            self.border_top if hasattr(self, 'border_top') else 0,
            self.fps if self.fps is not None else 30,
        )
        
        # 更新视频显示（这会同时保存current_pixmap）
        self.video_display_component.update_video_display(resized_frame)

    def _img_resize(self, image):
        height, width = image.shape[:2]
        
        video_preview_width = self.video_display_component.video_preview_width
        video_preview_height = self.video_display_component.video_preview_height
        # 计算等比缩放后的尺寸
        target_ratio = video_preview_width / video_preview_height
        image_ratio = width / height
        
        if image_ratio > target_ratio:
            # 宽度适配，高度按比例缩放
            new_width = video_preview_width
            new_height = int(new_width / image_ratio)
            top_border = (video_preview_height - new_height) // 2
            bottom_border = video_preview_height - new_height - top_border
            left_border = 0
            right_border = 0
        else:
            # 高度适配，宽度按比例缩放
            new_height = video_preview_height
            new_width = int(new_height * image_ratio)
            left_border = (video_preview_width - new_width) // 2
            right_border = video_preview_width - new_width - left_border
            top_border = 0
            bottom_border = 0
        
        # 先缩放图像
        resized = cv2.resize(image, (new_width, new_height))
        
        # 添加黑边以填充到目标尺寸
        padded = cv2.copyMakeBorder(
            resized, 
            top_border, bottom_border, 
            left_border, right_border, 
            cv2.BORDER_CONSTANT, 
            value=[0, 0, 0]
        )
        
        # 保存边框信息，用于坐标转换
        self.border_left = left_border / video_preview_width
        self.border_right = right_border / video_preview_width
        self.border_top = top_border / video_preview_height
        self.border_bottom = bottom_border / video_preview_height
        self.original_width = width
        self.original_height = height
        self.is_vertical = width < height
        self.scaled_width = new_width / video_preview_width
        self.scaled_height = new_height / video_preview_height
        
        return padded

    def _append_output(self, *args):
        """添加文本到输出区域并控制滚动（线程安全）"""
        text = ' '.join(str(arg) for arg in args).rstrip()
        self.output_text.appendPlainText(text)
        print(*args)
        if self.auto_scroll:
            scrollbar = self.output_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def _check_all_tasks_finished(self):
        """检查所有任务是否完成，若是则恢复按钮状态"""
        pending = self.task_list_component.get_pending_tasks()
        processing_exists = any(
            t.status == TaskStatus.PROCESSING 
            for t in self.task_list_component.tasks
        )
        if not pending and not processing_exists:
            self.run_button.setVisible(True)
            self.stop_button.setVisible(False)
            self.running_processes = []

    def append_output(self, *args):
        """兼容旧接口"""
        self._append_output(*args)

    def stop_button_clicked(self):
        try:
            self.running_task = False
            # 终止所有正在运行的子进程
            for proc in list(self.running_processes):
                try:
                    ProcessManager.instance().terminate_by_process(proc)
                except Exception:
                    pass
            # 将所有 PROCESSING 状态的任务恢复为 PENDING
            for i, t in enumerate(self.task_list_component.tasks):
                if t.status == TaskStatus.PROCESSING:
                    self.task_list_component.update_task_status(i, TaskStatus.PENDING)
        finally:
            self.running_processes = []
            self.run_button.setVisible(True)
            self.stop_button.setVisible(False)

    def _run_single_task(self, task_index, task):
        """
        在独立线程中执行单个任务（用于 ThreadPoolExecutor）
        
        Args:
            task_index: 任务在列表中的索引
            task: Task 对象
        """
        if not self.running_task:
            return
        
        process = None
        remote_caller = None
        try:
            # 获取字幕区域坐标
            subtitle_areas = self.task_list_component.get_task_option(task_index, TaskOptions.SUB_AREAS, [])
            if not subtitle_areas or len(subtitle_areas) <= 0:
                self._append_output(tr['SubtitleExtractorGUI']['SelectSubtitleArea'].format(task.path))
                self.task_list_component.update_task_status(task_index, TaskStatus.FAILED)
                return

            # 更新任务状态为处理中
            self.task_list_component.update_task_status(task_index, TaskStatus.PROCESSING)
            self.task_list_component.update_task_progress(task_index, 1)
            
            options = {}
            for key in task.options:
                value = task.options[key]
                if key == TaskOptions.SUB_AREAS.value:
                    value = self.video_display_component.preview_coordinates_to_video_coordinates(value)
                options[key] = value
            
            # 清理缓存, 使用动态路径
            task.output_path = None
            output_path = task.output_path
            
            # 为每个任务创建独立的 remote caller
            remote_caller = SubtitleRemoverRemoteCall()
            remote_caller.register_update_progress_callback(
                lambda progress, isFinished, ti=task_index: self.progress_signal.emit(ti, progress, isFinished)
            )
            remote_caller.register_log_callback(
                lambda *log_args, ti=task_index: self.append_log_signal.emit(ti, list(log_args))
            )
            remote_caller.register_update_preview_with_comp_callback(
                lambda *args, ti=task_index: self.update_preview_with_comp_signal.emit(ti, list(args))
            )
            remote_caller.register_error_callback(
                lambda e, ti=task_index: self.task_error_signal.emit(ti, e)
            )
            
            process = multiprocessing.Process(
                target=HomeInterface.remover_process,
                args=(remote_caller.queue, task.path, output_path, options)
            )
            
            if not self.running_task:
                return
                
            process.start()
            ProcessManager.instance().add_process(process)
            self.running_processes.append(process)
            
            process.join()
            
            # 任务完成处理
            task = self.task_list_component.get_task(task_index)
            if process.exitcode == 0 and task and task.status == TaskStatus.PROCESSING:
                # 任务正常完成
                task.output_path = output_path
                self.task_list_component.update_task_status(task_index, TaskStatus.COMPLETED)
                self.task_list_component.update_task_progress(task_index, 100)
                self._append_output(tr['Main']['FinishedProcessing'].format(output_path))
            elif task and task.status == TaskStatus.PROCESSING:
                # 非零退出码但状态仍为处理中，标记失败
                self.task_list_component.update_task_status(task_index, TaskStatus.FAILED)
                
        except Exception as e:
            traceback.print_exc()
            self.task_error_signal.emit(task_index, e)
        finally:
            # 从运行列表中移除
            if process is not None and process in self.running_processes:
                self.running_processes.remove(process)
            if remote_caller is not None:
                remote_caller.stop()
            self._check_all_tasks_finished()

    def run_button_clicked(self):
        if not self.task_list_component.get_pending_tasks():
            self._append_output(tr['SubtitleExtractorGUI']['OpenVideoFirst'])
            return
            
        try:
            pending_tasks = self.task_list_component.get_pending_tasks()
            if not pending_tasks:
                return
            
            self.run_button.setVisible(False)
            self.stop_button.setVisible(True)
            self.running_task = True
            self.running_processes = []
            
            # 保存当前选区到配置
            self.video_display_component.save_selections_to_config()
            
            # 释放预览视频
            if self.video_cap:
                self.video_cap.release()
                self.video_cap = None
            
            max_workers = min(config.maxConcurrentTasks.value, len(pending_tasks))
            self._append_output(f"启动 {max_workers} 个并发任务处理器（共 {len(pending_tasks)} 个待处理任务）")
            
            # 在后台线程中管理线程池
            def task_manager():
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {}
                    # 提交所有待处理任务
                    for task_index, task in pending_tasks:
                        future = executor.submit(self._run_single_task, task_index, task)
                        futures[future] = task_index
                    
                    # 等待所有任务完成
                    for future in as_completed(futures):
                        task_index = futures[future]
                        try:
                            future.result()
                        except Exception as e:
                            print(f"Task {task_index} failed: {e}")
                
                # 所有任务完成
                if self.running_task:
                    self._check_all_tasks_finished()

            threading.Thread(target=task_manager, daemon=True).start()
        except Exception as e:
            print(traceback.format_exc())
            self._append_output(f"Error: {e}")
            self.run_button.setVisible(True)
            self.stop_button.setVisible(False)

    @staticmethod
    def remover_process(queue, video_path, output_path, options):
        """
        在子进程中执行字幕提取的函数
        
        Args:
            video_path: 视频文件路径
            output_path: 输出文件路径
            options: 选项
        """
        sr = None
        try:
            from backend.main import SubtitleRemover
            sr = SubtitleRemover(video_path, True)
            sr.video_out_path = output_path
            for key in options:
                setattr(sr, key, options[key])
            sr.add_progress_listener(lambda progress, isFinished: SubtitleRemoverRemoteCall.remote_call_update_progress(queue, progress, isFinished))
            sr.append_output = lambda *args: SubtitleRemoverRemoteCall.remote_call_append_log(queue, args)
            sr.manage_process = lambda pid: SubtitleRemoverRemoteCall.remote_call_manage_process(queue, pid)
            sr.update_preview_with_comp = lambda ori, comp: SubtitleRemoverRemoteCall.remote_call_update_preview_with_comp(queue, ori, comp)
            sr.run()
        except Exception as e:
            traceback.print_exc()
            SubtitleRemoverRemoteCall.remote_call_catch_error(queue, e)
        finally:
            if sr:
                sr.isFinished = True
                sr.vsf_running = False
            SubtitleRemoverRemoteCall.remote_call_finish(queue)
            
    @Slot()
    def processing_finished(self):
        """已废弃 - 使用 _check_all_tasks_finished 替代"""
        pass

    @Slot(int, int, bool)
    def update_progress(self, task_index, progress_total, isFinished):
        try:
            # 始终更新任务列表中的进度
            self.task_list_component.update_task_progress(task_index, progress_total)
            
            # 仅当前选中任务更新滑块和预览
            if task_index == self.task_list_component.get_current_task_index():
                if self.frame_count and self.frame_count > 0:
                    pos = min(self.frame_count - 1, int(progress_total / 100 * self.frame_count))
                    if pos != self.video_slider.value():
                        self.video_slider.blockSignals(True)
                        self.video_slider.setValue(pos)
                        self.video_slider.blockSignals(False)
            
            # 检查是否完成
            if isFinished:
                task = self.task_list_component.get_task(task_index)
                if task and task.status == TaskStatus.PROCESSING:
                    self.task_list_component.update_task_status(task_index, TaskStatus.COMPLETED)
                self._check_all_tasks_finished()
        except Exception as e:
            print(f"更新进度时出错: {str(e)}")

    @Slot(int, list)
    def append_log(self, task_index, log):
        # 日志记录到任务对应的输出（仅当前选中任务打印到 UI）
        if task_index == self.task_list_component.get_current_task_index():
            self._append_output(*log)
        # 所有任务的日志也打印到控制台
        task = self.task_list_component.get_task(task_index)
        task_name = task.name if task else f"Task#{task_index}"
        print(f"[{task_name}]", *log)

    @Slot(int, list)
    def update_preview_with_comp(self, task_index, args):
        """更新执行时预览 - 仅当前选中任务"""
        if task_index != self.task_list_component.get_current_task_index():
            return
        frame_ori, frame_comp = args
        subtitle_areas = self.task_list_component.get_task_option(task_index, TaskOptions.SUB_AREAS, [])
        if len(subtitle_areas) > 0:
            subtitle_areas = self.video_display_component.preview_coordinates_to_video_coordinates(subtitle_areas)
            if frame_ori is frame_comp:
                frame_ori = frame_ori.copy()
            for rect in subtitle_areas:
                ymin, ymax, xmin, xmax = rect
                cv2.rectangle(frame_ori, (xmin, ymin), (xmax, ymax), (0, 255, 0), 2)
        preview_frame = cv2.hconcat([frame_ori, frame_comp])
        resized_frame = self._img_resize(preview_frame)
        self.video_display_component.update_video_display(resized_frame, draw_selection=False)
        self.video_display_component.set_dragger_enabled(False)

    @Slot(int, object)
    def on_task_error(self, task_index, e):
        self._append_output(tr['SubtitleExtractorGUI']['ErrorDuringProcessing'].format(str(e)))
        self.task_list_component.update_task_status(task_index, TaskStatus.FAILED)
        self._check_all_tasks_finished()

    def load_video(self, video_path):
        self.video_path = video_path
        if self.video_cap:
            self.video_cap.release()
            self.video_cap = None
        self.video_cap = cv2.VideoCapture(get_readable_path(self.video_path))
        if not self.video_cap.isOpened():
            return self.load_as_picture(video_path)
        ret, frame = self.video_cap.read()
        if not ret:
            return self.load_as_picture(video_path)
        self.frame_count = int(self.video_cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.frame_height = int(self.video_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.frame_width = int(self.video_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.fps = self.video_cap.get(cv2.CAP_PROP_FPS)
        
        self.update_preview(frame)
        self.video_slider.setMaximum(self.frame_count)
        self.video_slider.setValue(1)
        self.video_display_component.set_dragger_enabled(True)
        return True

    def load_as_picture(self, path):
        if not is_image_file(path):
            return False
        self.video_path = path
        self.video_cap = None
        frame = read_image(get_readable_path(path))
        if frame is None:
            return False
        self.frame_count = 1
        self.frame_height = frame.shape[0]
        self.frame_width = frame.shape[1]
        self.fps = 1
        self.update_preview(frame)
        self.video_slider.setMaximum(self.frame_count)
        self.video_slider.setValue(1)
        self.video_display_component.set_dragger_enabled(True)
        return True


    def open_file(self):
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            tr['SubtitleExtractorGUI']['Open'],
            "",
            "All Files (*.*);;MP4 Files (*.mp4);;FLV Files (*.flv);;WMV Files (*.wmv);;AVI Files (*.avi)"
        )
        if files:
            files_loaded = []
            # 倒序打开, 确保第一个视频截图显示在屏幕上
            for path in reversed(files):
                if self.load_video(path):
                    self.append_output(f"{tr['SubtitleExtractorGUI']['OpenVideoSuccess']}: {path}")
                    files_loaded.append(path)
                else:
                    self.append_output(f"{tr['SubtitleExtractorGUI']['OpenVideoFailed']}: {path}")
            # 正序添加, 确保任务列表顺序一致
            for path in reversed(files_loaded):
                # 添加到任务列表
                self.task_list_component.add_task(path)
                index = max(0, self.task_list_component.find_task_index_by_path(path))
                self.task_list_component.select_task(index)

    def closeEvent(self, event):
        """窗口关闭时断开信号连接"""
        try:
            # 断开信号连接
            self.progress_signal.disconnect(self.update_progress)
            self.append_log_signal.disconnect(self.append_log)
            self.update_preview_with_comp_signal.disconnect(self.update_preview_with_comp)
            self.task_error_signal.disconnect(self.on_task_error)
            self.video_display_component.video_slider.valueChanged.disconnect(self.slider_changed)
            self.video_display_component.ab_sections_changed.disconnect(self.ab_sections_changed)
            self.video_display_component.selections_changed.disconnect(self.selections_changed)
            # 释放视频资源
            if self.video_cap:
                self.video_cap.release()
                self.video_cap = None
                
            # 确保所有子进程都已终止
            ProcessManager.instance().terminate_all()
        except Exception as e:
            print(f"Error during close window:", e)
        super().closeEvent(event)
    