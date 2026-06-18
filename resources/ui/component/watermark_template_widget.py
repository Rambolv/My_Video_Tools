"""
水印模板管理组件

提供图形化界面让用户可以：
1. 从视频画面中截取水印模板（框选区域 → 确认即可）
2. 从文件加载水印模板图片
3. 预览当前模板
4. 一键启用/禁用模板匹配检测
"""

import os
import cv2
import numpy as np
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                QFileDialog, QComboBox, QDoubleSpinBox,
                                QSlider)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap, QImage
from qfluentwidgets import (
    CardWidget, PushButton, SwitchButton, FluentIcon, InfoBar, InfoBarPosition,
    BodyLabel, StrongBodyLabel, CaptionLabel
)

from backend.config import config, tr


class WatermarkTemplateWidget(CardWidget):
    """
    水印模板管理卡片
    """

    template_changed = Signal(str)  # new template path

    # 模板保存目录 (resources/backend/models/watermark_templates/)
    TEMPLATE_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "backend", "models", "watermark_templates"
    )
    PREVIEW_SIZE = QSize(160, 90)

    def __init__(self, video_display_component=None, parent=None):
        super().__init__(parent)
        self._video_display = video_display_component  # 直接持有VideoDisplayComponent引用
        self._capture_mode = False
        self._current_template_path = None
        self._init_ui()
        self._load_current_config()
        self._update_dependent_features()

    def _init_ui(self):
        """初始化界面"""
        self.setMinimumWidth(200)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        # --- 标题行 ---
        title_layout = QHBoxLayout()
        title_label = StrongBodyLabel("🎯 自定义水印")
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        # 启用开关
        self.enable_switch = SwitchButton()
        self.enable_switch.setChecked(config.enableWatermarkDetection.value)
        self.enable_switch.checkedChanged.connect(self._on_enable_changed)
        title_layout.addWidget(self.enable_switch)
        main_layout.addLayout(title_layout)

        # --- 模板预览区域 ---
        preview_layout = QHBoxLayout()
        preview_layout.setAlignment(Qt.AlignCenter)

        self.template_preview = QLabel()
        self.template_preview.setFixedSize(self.PREVIEW_SIZE)
        self.template_preview.setAlignment(Qt.AlignCenter)
        self.template_preview.setStyleSheet("""
            QLabel {
                background-color: #1a1a1a;
                border: 2px dashed #555;
                border-radius: 6px;
                color: #888;
                font-size: 12px;
            }
        """)
        self.template_preview.setText("暂无模板")
        preview_layout.addWidget(self.template_preview)
        main_layout.addLayout(preview_layout)

        # --- 模板路径提示 ---
        self.path_label = CaptionLabel("")
        self.path_label.setWordWrap(True)
        self.path_label.setStyleSheet("color: #888; font-size: 10px;")
        main_layout.addWidget(self.path_label)

        # --- 检测灵敏度 ---
        sensitivity_layout = QHBoxLayout()
        sensitivity_label = BodyLabel("检测灵敏度:")
        sensitivity_layout.addWidget(sensitivity_label)
        self.sensitivity_combo = QComboBox()
        self.sensitivity_combo.addItems(["低 (严格)", "中 (默认)", "高 (宽松)"])
        sens_map = {"low": 0, "medium": 1, "high": 2}
        current_sens = config.watermarkDetectionSensitivity.value
        self.sensitivity_combo.setCurrentIndex(sens_map.get(current_sens, 1))
        self.sensitivity_combo.currentIndexChanged.connect(self._on_sensitivity_changed)
        self.sensitivity_combo.setFixedHeight(24)
        sensitivity_layout.addWidget(self.sensitivity_combo)
        main_layout.addLayout(sensitivity_layout)

        # --- 邻近帧窗口 ---
        proximity_layout = QHBoxLayout()
        proximity_label = BodyLabel("邻近扫描(秒):")
        proximity_layout.addWidget(proximity_label)
        self.proximity_spin = QDoubleSpinBox()
        self.proximity_spin.setRange(0.0, 10.0)
        self.proximity_spin.setSingleStep(0.5)
        self.proximity_spin.setDecimals(1)
        self.proximity_spin.setSuffix(" 秒")
        self.proximity_spin.setValue(config.watermarkProximityWindowSeconds.value)
        self.proximity_spin.valueChanged.connect(self._on_proximity_changed)
        self.proximity_spin.setFixedHeight(24)
        self.proximity_spin.setToolTip("检测到文字时前后N秒内的帧执行全策略水印检测, 0=禁用")
        proximity_layout.addWidget(self.proximity_spin)
        main_layout.addLayout(proximity_layout)

        # --- 颜色传播检测开关 ---
        color_layout = QHBoxLayout()
        color_label = BodyLabel("水印推测:")
        color_layout.addWidget(color_label)
        self.color_propagation_switch = SwitchButton()
        self.color_propagation_switch.setChecked(config.watermarkColorPropagationEnabled.value)
        self.color_propagation_switch.checkedChanged.connect(self._on_color_propagation_changed)
        self.color_propagation_switch.setToolTip(
            "提取文字颜色, 在邻近帧中自动查找同色块作为水印一同去除"
        )
        color_layout.addWidget(self.color_propagation_switch)
        color_layout.addStretch()
        main_layout.addLayout(color_layout)

        # --- 水印强力清扫开关 ---
        sweep_layout = QHBoxLayout()
        sweep_label = BodyLabel("水印强力清扫:")
        sweep_layout.addWidget(sweep_label)
        self.power_sweep_switch = SwitchButton()
        self.power_sweep_switch.setChecked(config.watermarkPowerSweepEnabled.value)
        self.power_sweep_switch.checkedChanged.connect(self._on_power_sweep_changed)
        self.power_sweep_switch.setToolTip(
            "每1帧对文字区域做差分比较, 检测快速变化的图形作为水印目标"
        )
        sweep_layout.addWidget(self.power_sweep_switch)
        sweep_layout.addStretch()
        main_layout.addLayout(sweep_layout)

        # --- 变化程度滑块（仅强力清扫开启时可调） ---
        change_layout = QHBoxLayout()
        change_label = BodyLabel("变化程度:")
        change_layout.addWidget(change_label)
        self.change_level_slider = QSlider(Qt.Horizontal)
        self.change_level_slider.setObjectName("changeLevelSlider")
        self.change_level_slider.setRange(10, 200)
        self.change_level_slider.setValue(config.watermarkPowerSweepChangeLevel.value)
        self.change_level_slider.valueChanged.connect(self._on_change_level_changed)
        self.change_level_slider.setFixedHeight(24)
        self.change_level_slider.setMinimumWidth(80)
        change_layout.addWidget(self.change_level_slider, 1)
        self.change_level_value_label = CaptionLabel(str(config.watermarkPowerSweepChangeLevel.value))
        self.change_level_value_label.setFixedWidth(28)
        self.change_level_value_label.setAlignment(Qt.AlignCenter)
        self.change_level_value_label.setStyleSheet("font-weight: bold;")
        change_layout.addWidget(self.change_level_value_label)
        main_layout.addLayout(change_layout)

        # --- 水印区域全部清扫开关 ---
        region_sweep_layout = QHBoxLayout()
        region_sweep_label = BodyLabel("区域全部清扫:")
        region_sweep_layout.addWidget(region_sweep_label)
        self.region_full_sweep_switch = SwitchButton()
        self.region_full_sweep_switch.setChecked(config.watermarkRegionFullSweepEnabled.value)
        self.region_full_sweep_switch.checkedChanged.connect(self._on_region_full_sweep_changed)
        self.region_full_sweep_switch.setToolTip(
            "文字帧前后N秒内, 将整个文字区域直接标记为水印全部去除"
        )
        region_sweep_layout.addWidget(self.region_full_sweep_switch)
        region_sweep_layout.addStretch()
        main_layout.addLayout(region_sweep_layout)

        # --- 强制清理区域水印开关 ---
        force_layout = QHBoxLayout()
        force_label = BodyLabel("强制清理区域:")
        force_layout.addWidget(force_label)
        self.force_region_switch = SwitchButton()
        self.force_region_switch.setChecked(config.watermarkForceRegionInpaintEnabled.value)
        self.force_region_switch.checkedChanged.connect(self._on_force_region_changed)
        self.force_region_switch.setToolTip(
            "文字帧前后N秒内, 将文字框所在区域原样复制到邻近帧强制重绘"
        )
        force_layout.addWidget(self.force_region_switch)
        force_layout.addStretch()
        main_layout.addLayout(force_layout)

        # --- 跟踪浮动水印开关 ---
        track_layout = QHBoxLayout()
        track_label = BodyLabel("跟踪浮动水印:")
        track_layout.addWidget(track_label)
        self.track_floating_switch = SwitchButton()
        self.track_floating_switch.setChecked(config.watermarkTrackFloating.value)
        self.track_floating_switch.checkedChanged.connect(self._on_track_floating_changed)
        self.track_floating_switch.setToolTip(
            "开启后自动跟踪并在每一帧中清理视频中的浮动/移动水印"
        )
        track_layout.addWidget(self.track_floating_switch)
        track_layout.addStretch()
        main_layout.addLayout(track_layout)

        # --- 子功能依赖提示 ---
        self.dep_hint = CaptionLabel("")
        self.dep_hint.setWordWrap(True)
        self.dep_hint.setStyleSheet("color: #e88; font-size: 10px; padding: 2px 0;")
        main_layout.addWidget(self.dep_hint)

        # --- 操作按钮 ---
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        self.capture_btn = PushButton("手动截取视频中水印")
        self.capture_btn.setIcon(FluentIcon.PHOTO)
        self.capture_btn.setFixedHeight(28)
        self.capture_btn.clicked.connect(self._on_capture_clicked)
        btn_layout.addWidget(self.capture_btn)

        self.load_btn = PushButton("加载水印图片")
        self.load_btn.setIcon(FluentIcon.FOLDER)
        self.load_btn.setFixedHeight(28)
        self.load_btn.clicked.connect(self._on_load_clicked)
        btn_layout.addWidget(self.load_btn)

        main_layout.addLayout(btn_layout)

        # 清除按钮
        self.clear_btn = PushButton("清除模板")
        self.clear_btn.setIcon(FluentIcon.DELETE)
        self.clear_btn.setFixedHeight(28)
        self.clear_btn.clicked.connect(self._on_clear_clicked)
        main_layout.addWidget(self.clear_btn)

        main_layout.addStretch()

    def _load_current_config(self):
        """从配置加载当前模板状态"""
        template_path = config.watermarkTemplatePath.value
        if template_path and os.path.exists(template_path):
            self._set_template(template_path)
        else:
            self._clear_template_display()

    # ==================== 公共方法 ====================

    def is_capture_mode(self) -> bool:
        return self._capture_mode

    def get_template_path(self) -> str:
        return self._current_template_path

    def set_capture_result(self, template_image: np.ndarray):
        """
        接收从视频画面截取的水印模板图像

        Args:
            template_image: BGR numpy array (截取的ROI区域)
        """
        if template_image is None or template_image.size == 0:
            self._exit_capture_mode()
            InfoBar.warning(
                "截取失败",
                "未获取到有效的模板图像",
                duration=3000,
                parent=self.window(),
            )
            return

        # 保存模板到固定目录
        os.makedirs(self.TEMPLATE_DIR, exist_ok=True)
        template_path = os.path.join(
            self.TEMPLATE_DIR, "watermark_template.png"
        )
        cv2.imwrite(template_path, template_image)

        # 更新显示和配置
        self._set_template(template_path)
        config.set(config.watermarkTemplatePath, template_path)

        self._exit_capture_mode()

        InfoBar.success(
            "模板已保存",
            f"水印模板已保存到: {os.path.basename(template_path)}",
            duration=3000,
            position=InfoBarPosition.TOP,
            parent=self.window(),
        )

    # ==================== 内部方法 ====================

    def _set_template(self, path: str):
        """设置并预览模板"""
        self._current_template_path = path
        self._update_preview(path)
        self.path_label.setText(f"模板: ...{os.path.sep}{os.path.basename(path)}")
        self.clear_btn.setEnabled(True)
        self.template_changed.emit(path)

    def _clear_template_display(self):
        """清除模板显示"""
        self._current_template_path = None
        self.template_preview.setText("暂无模板")
        self.template_preview.setPixmap(QPixmap())
        self.path_label.setText("")
        self.clear_btn.setEnabled(False)

    def _update_preview(self, image_path: str):
        """更新模板预览缩略图"""
        try:
            img = cv2.imread(image_path)
            if img is None:
                self.template_preview.setText("加载失败")
                return

            h, w = img.shape[:2]
            preview_w = self.PREVIEW_SIZE.width()
            preview_h = self.PREVIEW_SIZE.height()

            # 保持宽高比缩放
            scale = min(preview_w / w, preview_h / h)
            new_w = int(w * scale)
            new_h = int(h * scale)
            resized = cv2.resize(img, (new_w, new_h))

            # 转为 RGB 再转 QPixmap
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            bytes_per_line = ch * w
            qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)

            self.template_preview.setPixmap(pixmap)
            self.template_preview.setStyleSheet("""
                QLabel {
                    background-color: #1a1a1a;
                    border: 2px solid #4a9;
                    border-radius: 6px;
                }
            """)
        except Exception:
            self.template_preview.setText("预览失败")

    def _enter_capture_mode(self):
        """进入截取模式"""
        self._capture_mode = True
        self.capture_btn.setText("取消截取")
        self.capture_btn.setStyleSheet("""
            PushButton {
                background-color: #d44;
                color: white;
            }
            PushButton:hover {
                background-color: #f55;
            }
        """)
        # 直接调用 VideoDisplayComponent 的方法
        if self._video_display is not None:
            try:
                self._video_display.enter_watermark_capture_mode()
            except Exception as e:
                print(f"[WatermarkTemplate] enter_watermark_capture_mode failed: {e}")
        else:
            print("[WatermarkTemplate] _video_display is None!")

    def _exit_capture_mode(self):
        """退出截取模式"""
        self._capture_mode = False
        self.capture_btn.setText("截取模板")
        self.capture_btn.setStyleSheet("")
        if self._video_display is not None:
            try:
                self._video_display.exit_watermark_capture_mode()
            except Exception as e:
                print(f"[WatermarkTemplate] exit_watermark_capture_mode failed: {e}")

    # ==================== 事件处理 ====================

    def _on_enable_changed(self, checked: bool):
        """启用/禁用水印检测开关"""
        config.set(config.enableWatermarkDetection, checked)
        if checked and not self._current_template_path:
            InfoBar.info(
                "提示",
                "请先截取或加载水印模板图片",
                duration=3000,
                position=InfoBarPosition.TOP,
                parent=self.window(),
            )

    def _on_capture_clicked(self):
        """截取模板按钮点击"""
        if self._capture_mode:
            self._exit_capture_mode()
        else:
            if self._video_display is None:
                InfoBar.warning(
                    "无法截取",
                    "视频显示组件未初始化",
                    duration=3000,
                    position=InfoBarPosition.TOP,
                    parent=self.window(),
                )
                return
            self._enter_capture_mode()

    def _on_load_clicked(self):
        """加载模板图片"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择水印模板图片",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.tiff);;所有文件 (*.*)",
        )
        if file_path and os.path.exists(file_path):
            self._set_template(file_path)
            config.set(config.watermarkTemplatePath, file_path)
            if not self.enable_switch.isChecked():
                self.enable_switch.setChecked(True)
            InfoBar.success(
                "模板已加载",
                f"已加载: {os.path.basename(file_path)}",
                duration=2000,
                position=InfoBarPosition.TOP,
                parent=self.window(),
            )

    def _on_sensitivity_changed(self, index: int):
        """灵敏度变更"""
        sens_map = {0: "low", 1: "medium", 2: "high"}
        config.set(config.watermarkDetectionSensitivity, sens_map.get(index, "medium"))

    def _on_proximity_changed(self, value: float):
        """邻近窗口变更"""
        config.set(config.watermarkProximityWindowSeconds, value)

    def _update_dependent_features(self):
        """
        管理子功能依赖关系：
        水印推测(颜色传播)关闭时，所有依赖它的子功能自动关闭且禁用
        """
        parent_enabled = config.watermarkColorPropagationEnabled.value
        children = [
            (self.power_sweep_switch, config.watermarkPowerSweepEnabled, "水印强力清扫"),
            (self.region_full_sweep_switch, config.watermarkRegionFullSweepEnabled, "区域全部清扫"),
            (self.force_region_switch, config.watermarkForceRegionInpaintEnabled, "强制清理区域"),
        ]
        if parent_enabled:
            for sw, cfg, name in children:
                sw.setEnabled(True)
                sw.setChecked(cfg.value)
            self.dep_hint.setText("")
        else:
            for sw, cfg, name in children:
                if cfg.value:
                    config.set(cfg, False)
                sw.setChecked(False)
                sw.setEnabled(False)
            self.dep_hint.setText("⚠ 子功能需开启「水印推测」后才可启用")

        # 变化程度滑块：仅强力清扫开启时可调
        power_sweep_enabled = parent_enabled and config.watermarkPowerSweepEnabled.value
        self.change_level_slider.setEnabled(power_sweep_enabled)
        self.change_level_value_label.setEnabled(power_sweep_enabled)

    def _on_power_sweep_changed(self, checked: bool):
        """水印强力清扫开关"""
        config.set(config.watermarkPowerSweepEnabled, checked)
        self._update_power_sweep_controls()

    def _update_power_sweep_controls(self):
        """更新变化程度控件的启用状态"""
        power_sweep_on = config.watermarkPowerSweepEnabled.value
        parent_on = config.watermarkColorPropagationEnabled.value
        enabled = parent_on and power_sweep_on
        self.change_level_slider.setEnabled(enabled)
        self.change_level_value_label.setEnabled(enabled)

    def _on_change_level_changed(self, value: int):
        """变化程度变更"""
        config.set(config.watermarkPowerSweepChangeLevel, value)
        self.change_level_value_label.setText(str(value))

    def _on_color_propagation_changed(self, checked: bool):
        """颜色传播检测开关"""
        config.set(config.watermarkColorPropagationEnabled, checked)
        self._update_dependent_features()

    def _on_power_sweep_changed(self, checked: bool):
        """水印强力清扫开关"""
        config.set(config.watermarkPowerSweepEnabled, checked)

    def _on_region_full_sweep_changed(self, checked: bool):
        """水印区域全部清扫开关"""
        config.set(config.watermarkRegionFullSweepEnabled, checked)

    def _on_force_region_changed(self, checked: bool):
        """强制清理区域水印开关"""
        config.set(config.watermarkForceRegionInpaintEnabled, checked)

    def _on_track_floating_changed(self, checked: bool):
        """跟踪浮动水印开关"""
        config.set(config.watermarkTrackFloating, checked)

    def _on_clear_clicked(self):
        """清除模板"""
        self._clear_template_display()
        config.set(config.watermarkTemplatePath, "")
        config.set(config.enableWatermarkDetection, False)
        config.set(config.watermarkColorPropagationEnabled, False)
        config.set(config.watermarkPowerSweepEnabled, False)
        config.set(config.watermarkRegionFullSweepEnabled, False)
        config.set(config.watermarkForceRegionInpaintEnabled, False)
        config.set(config.watermarkTrackFloating, False)
        self.enable_switch.setChecked(False)
        self.color_propagation_switch.setChecked(False)
        self.power_sweep_switch.setChecked(False)
        self.region_full_sweep_switch.setChecked(False)
        self.force_region_switch.setChecked(False)
        self.track_floating_switch.setChecked(False)
        InfoBar.info(
            "模板已清除",
            "水印模板检测已禁用",
            duration=2000,
            position=InfoBarPosition.TOP,
            parent=self.window(),
        )

    def _find_home_interface(self):
        """查找 HomeInterface 实例（已废弃）"""
        return None
