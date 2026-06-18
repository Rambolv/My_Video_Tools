from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap, QPainter, QColor, QPen, QBrush
from qfluentwidgets import (ScrollArea, CardWidget, SettingCardGroup,
                          ComboBoxSettingCard, SwitchSettingCard, RangeSettingCard, FluentIcon,
                          StrongBodyLabel, PushButton, InfoBar, InfoBarPosition)
from backend.config import config, tr, HARDWARD_ACCELERATION_OPTION
from backend.tools.vram_estimator import (estimate_model_vram, get_vram_status_color,
                                           has_real_data, get_model_danger_flags)
from backend.tools.hardware_accelerator import HardwareAccelerator
from ui.component.watermark_template_widget import WatermarkTemplateWidget


class _CollapsibleSection(CardWidget):
    """可折叠的面板区块"""

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self._expanded = True
        self._content_widgets = []

        self.setBorderRadius(8)

        # 主布局
        self._main_layout = QtWidgets.QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        # 标题栏（可点击）
        self._header = QtWidgets.QWidget()
        self._header.setFixedHeight(36)
        self._header.setCursor(Qt.PointingHandCursor)
        self._header.mousePressEvent = lambda e: self._toggle()
        header_layout = QtWidgets.QHBoxLayout(self._header)
        header_layout.setContentsMargins(16, 0, 16, 0)

        self._arrow_label = QtWidgets.QLabel("▼")
        self._arrow_label.setStyleSheet("font-size: 10px; color: #888;")
        header_layout.addWidget(self._arrow_label)

        self._title_label = StrongBodyLabel(title, self._header)
        header_layout.addWidget(self._title_label)
        header_layout.addStretch()

        self._main_layout.addWidget(self._header)

        # 内容容器
        self._content_container = QtWidgets.QWidget()
        self._content_layout = QtWidgets.QVBoxLayout(self._content_container)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)
        self._main_layout.addWidget(self._content_container)

    def addWidget(self, widget):
        """向内容区域添加组件"""
        self._content_layout.addWidget(widget)
        self._content_widgets.append(widget)

    def addStretch(self, stretch=0):
        self._content_layout.addStretch(stretch)

    def _toggle(self):
        """切换展开/折叠状态"""
        self._expanded = not self._expanded
        self._content_container.setVisible(self._expanded)
        self._arrow_label.setText("▼" if self._expanded else "▶")

    def collapse(self):
        """折叠"""
        self._expanded = False
        self._content_container.setVisible(False)
        self._arrow_label.setText("▶")

    def expand(self):
        """展开"""
        self._expanded = True
        self._content_container.setVisible(True)
        self._arrow_label.setText("▼")


class SettingInterface(ScrollArea):
    """可滚动、可折叠的设置面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.__init_widgets()

    def __init_widgets(self):
        # 滚动内容容器
        self.scrollWidget = QtWidgets.QWidget(self)
        self.scrollLayout = QtWidgets.QVBoxLayout(self.scrollWidget)
        self.scrollLayout.setSpacing(8)
        self.scrollLayout.setContentsMargins(8, 8, 8, 16)

        # 滚动区域属性
        self.setWidget(self.scrollWidget)
        self.enableTransparentBackground()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.setAttribute(QtCore.Qt.WA_StyledBackground)

        # ---- 基础设置组（可折叠） ----
        self.basic_section = _CollapsibleSection("基础设置", self.scrollWidget)
        self.interface_combo = ComboBoxSettingCard(
            configItem=config.interface,
            icon=FluentIcon.LANGUAGE,
            title=tr["SubtitleExtractorGUI"]["InterfaceLanguage"],
            content="",
            parent=self.basic_section,
            texts=config.intefaceTexts.keys(),
        )
        self.inpaint_mode_combo = ComboBoxSettingCard(
            configItem=config.inpaintMode,
            icon=FluentIcon.GLOBE,
            title=tr["SubtitleExtractorGUI"]["InpaintMode"],
            content="",
            parent=self.basic_section,
            texts=[tr["InpaintMode"].get(mode.value, mode.value) for mode in config.inpaintMode.validator.options],
        )
        self.inpaint_mode_combo.setToolTip(tr["SubtitleExtractorGUI"]["InpaintModeDesc"])
        self.subtitle_detect_model_combo = ComboBoxSettingCard(
            configItem=config.subtitleDetectMode,
            icon=FluentIcon.SEARCH,
            title=tr["SubtitleExtractorGUI"]["SubtitleDetectMode"],
            content="",
            parent=self.basic_section,
            texts=[mode.value for mode in config.subtitleDetectMode.validator.options],
        )
        self.basic_section.addWidget(self.interface_combo)
        self.basic_section.addWidget(self.inpaint_mode_combo)
        self.basic_section.addWidget(self.subtitle_detect_model_combo)
        self.scrollLayout.addWidget(self.basic_section)

        # ---- 性能设置组（可折叠） ----
        self.performance_section = _CollapsibleSection("性能设置", self.scrollWidget)
        self.hardware_acceleration = SwitchSettingCard(
            configItem=config.hardwareAcceleration,
            icon=FluentIcon.SPEED_HIGH,
            title=tr["Setting"]["HardwareAcceleration"],
            content=tr["Setting"]["HardwareAccelerationDesc"],
            parent=self.performance_section
        )
        if not HARDWARD_ACCELERATION_OPTION:
            self.hardware_acceleration.switchButton.setChecked(False)
            self.hardware_acceleration.switchButton.setEnabled(False)
            self.hardware_acceleration.setContent(tr["Setting"]["HardwareAccelerationNO"])
            config.set(config.hardwareAcceleration, False)
        self.max_concurrent_combo = ComboBoxSettingCard(
            configItem=config.maxConcurrentTasks,
            icon=FluentIcon.SYNC,
            title=tr["Setting"].get("MaxConcurrentTasks", "最大并发任务数"),
            content=tr["Setting"].get("MaxConcurrentTasksDesc", "同时处理多个视频以提高 GPU 利用率"),
            parent=self.performance_section,
            texts=["1", "2", "3", "4", "5", "6", "7", "8"],
        )
        self.processing_depth_card = RangeSettingCard(
            configItem=config.processingDepth,
            icon=FluentIcon.SPEED_HIGH,
            title=tr["Setting"].get("ProcessingDepth", "处理深度"),
            content=tr["Setting"].get("ProcessingDepthDesc", "0=极快低VRAM  →  100=极致效果/最大VRAM  拖动滑块实时调控所有模型参数"),
            parent=self.performance_section,
        )
        # 自适应滑块宽度，防止在窄面板中被裁剪
        self.processing_depth_card.slider.setMinimumWidth(120)

        # --- GPU 显存信息 & 占用估算 ---
        self._vram_info_label = QtWidgets.QLabel()
        self._vram_info_label.setWordWrap(True)
        self._vram_info_label.setStyleSheet("font-size: 12px; padding: 6px 12px; color: #bbb;")
        self._vram_est_label = QtWidgets.QLabel()
        self._vram_est_label.setWordWrap(True)
        self._vram_est_label.setStyleSheet("font-size: 12px; padding: 4px 12px;")

        self.performance_section.addWidget(self.hardware_acceleration)
        self.performance_section.addWidget(self.max_concurrent_combo)
        self.performance_section.addWidget(self.processing_depth_card)

        # ---- VRAM 被动监控开关 ----
        self.vram_monitor_switch = SwitchSettingCard(
            configItem=config.enableVramMonitoring,
            icon=FluentIcon.SPEED_HIGH,
            title="显存监控",
            content="开启后，每次处理视频时自动记录 GPU 显存峰值，用于推荐值和危险标记",
            parent=self.performance_section,
        )
        self.performance_section.addWidget(self.vram_monitor_switch)

        self.performance_section.addWidget(self._vram_info_label)
        self.performance_section.addWidget(self._vram_est_label)
        self.scrollLayout.addWidget(self.performance_section)

        # ---- 模型显存参考组（可折叠） ----
        self.vram_ref_section = _CollapsibleSection("模型显存参考 (1080p/标准深度)", self.scrollWidget)
        # 状态标签：显示已采集数据数
        self._vram_data_status = QtWidgets.QLabel()
        self._vram_data_status.setStyleSheet("font-size: 11px; padding: 4px 8px; color: #888;")
        self._vram_ref_table = QtWidgets.QTextEdit()
        self._vram_ref_table.setReadOnly(True)
        self._vram_ref_table.setMaximumHeight(260)
        self._vram_ref_table.setStyleSheet(
            "QTextEdit { background: transparent; border: none; font-size: 11px; color: #ccc; }")
        self.vram_ref_section.addWidget(self._vram_data_status)
        self.vram_ref_section.addWidget(self._vram_ref_table)
        self.vram_ref_section.collapse()  # 默认折叠
        self.scrollLayout.addWidget(self.vram_ref_section)

        # ---- 水印检测组（可折叠） ----
        self.watermark_section = _CollapsibleSection("水印检测", self.scrollWidget)
        self.watermark_template_widget = WatermarkTemplateWidget(parent=self.watermark_section)
        self.watermark_section.addWidget(self.watermark_template_widget)
        self.scrollLayout.addWidget(self.watermark_section)

        self.scrollLayout.addStretch()

        # --- 连接信号，更新显存估算 ---
        self._refresh_vram_display()
        self._build_vram_ref_table()
        self.inpaint_mode_combo.comboBox.currentIndexChanged.connect(self._on_config_changed)
        self.subtitle_detect_model_combo.comboBox.currentIndexChanged.connect(self._on_config_changed)
        self.max_concurrent_combo.comboBox.currentIndexChanged.connect(self._on_config_changed)
        config.processingDepth.valueChanged.connect(self._on_config_changed)

    def _on_config_changed(self):
        """配置变更时刷新显存估算并重绘并发选项颜色"""
        self._refresh_vram_display()
        self._color_concurrency_items()

    def _refresh_vram_display(self):
        """刷新显存信息和估算标签"""
        try:
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
            self._vram_info_label.setText(
                f"🖥 GPU 显存总量: {gpu_vram:.1f} GB{gpu_str}")

            # 估算当前配置的显存
            from backend.tools.constant import InpaintMode, SubtitleDetectMode
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
            self._vram_est_label.setTextFormat(Qt.RichText)
        except Exception:
            self._vram_info_label.setText("⚠️ 无法获取 GPU 显存信息")

    def _color_concurrency_items(self):
        """对并发任务数下拉框中超出显存的选项标红"""
        try:
            from backend.tools.constant import InpaintMode, SubtitleDetectMode
            combo = self.max_concurrent_combo.comboBox
            model = combo.model()
            if model is None:
                return
            # 对每一项分别估算
            for i in range(combo.count()):
                n = i + 1  # 并发数
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
                    item.setForeground(QColor("#e81123"))  # 红色
                    # 同时更新显示文本加上警告
                    current_text = item.text().replace(" ⚠️", "")
                    item.setText(f"{current_text} ⚠️")
                else:
                    item.setForeground(QColor("#ccc"))  # 正常色
                    current_text = item.text().replace(" ⚠️", "")
                    item.setText(current_text)
        except Exception:
            pass

    def _build_vram_ref_table(self):
        """构建各模型显存参考表（优先显示真实工作采集值 + 危险标记）"""
        from backend.tools.vram_estimator import _MODEL_VRAM_BASELINE_1080P, get_model_vram_baseline
        from backend.tools.constant import InpaintMode
        accel = HardwareAccelerator.instance()
        gpu_vram = accel.get_gpu_vram_gb()

        has_real = has_real_data()
        danger_flags = get_model_danger_flags()
        source_note = "🔬真实采集" if has_real else "📦预估值"

        # 更新状态标签
        if has_real:
            from backend.tools.vram_monitor import load_records
            records = load_records()
            self._vram_data_status.setText(
                f"✅ 已从 {len(records)} 次实际处理中采集显存数据 | 开启上方「显存监控」开关后，每次处理自动记录")
        else:
            self._vram_data_status.setText(
                "💡 尚未采集真实数据 | 开启上方「显存监控」开关，处理视频后自动记录 GPU 显存峰值")

        lines = [f"<table width='100%'><caption style='color:#888;font-size:10px'>{source_note} | GPU: {gpu_vram:.1f}GB</caption>",
                 "<tr><th>类别</th><th>模型</th><th>显存(GB)</th><th>安全并发</th><th></th></tr>"]
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

            # 危险标记：该模型组合曾经 OOM
            danger_tag = ""
            if model_key in danger_flags and danger_flags[model_key]:
                danger_tag = " <span style='color:#e81123;font-weight:bold'>⚠️爆显存</span>"
                vram_color = "#e81123"

            model_display = model_key[:28]
            lines.append(
                f"<tr style='color:{vram_color}'>"
                f"<td>{cat}</td><td>{model_display}</td>"
                f"<td>{vram:.1f}</td><td>{safe_n}</td>"
                f"<td>{danger_tag}</td></tr>")
        lines.append("</table>")
        self._vram_ref_table.setHtml("\n".join(lines))

    def set_video_display_component(self, vdc):
        """设置视频显示组件引用（用于水印截取）"""
        self.watermark_template_widget._video_display = vdc