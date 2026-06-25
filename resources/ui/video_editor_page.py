"""
@desc: 视频自由修改大师 — AI换脸/换装/换背景/物品替换删除
"""
import os
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt
from qfluentwidgets import (CardWidget, BodyLabel, StrongBodyLabel,
                            PushButton, PrimaryPushButton, FluentIcon)
from backend.config import config, tr, VERSION, BASE_DIR
from ui.component.donation_dialog import show_donation_dialog


class _FeatureCard(CardWidget):
    """单个功能卡片"""

    def __init__(self, icon_emoji, title, desc, parent=None):
        super().__init__(parent)
        self.setBorderRadius(12)
        self.setMinimumHeight(140)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        # 图标+标题行
        header = QtWidgets.QHBoxLayout()
        icon = QtWidgets.QLabel(icon_emoji)
        icon.setStyleSheet("font-size: 32px;")
        icon.setFixedWidth(48)
        header.addWidget(icon)
        title_lbl = StrongBodyLabel(title)
        title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #e0e0e0;")
        header.addWidget(title_lbl)
        header.addStretch()
        layout.addLayout(header)

        # 描述
        desc_lbl = BodyLabel(desc)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("font-size: 12px; color: #999; padding: 2px 0;")
        layout.addWidget(desc_lbl)

        layout.addStretch()

        # 按钮
        btn = PrimaryPushButton("立即体验")
        btn.setIcon(FluentIcon.PLAY)
        btn.clicked.connect(lambda: show_donation_dialog(self.window()))
        btn.setFixedHeight(32)
        btn.setStyleSheet("""
            PrimaryPushButton {
                border-radius: 6px;
                font-weight: bold;
            }
        """)
        layout.addWidget(btn, 0, Qt.AlignRight)


class VideoEditorPage(QtWidgets.QWidget):
    """视频自由修改大师页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("VideoEditorPage")

        # 主布局
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # ── 标题 ──
        title = StrongBodyLabel("🎬 视频自由修改大师")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #ffd700;")
        main_layout.addWidget(title)

        subtitle = BodyLabel("AI驱动的视频编辑套件 — 换脸、换装、换背景、物品替换，一键完成")
        subtitle.setStyleSheet("font-size: 13px; color: #aaa; padding-bottom: 8px;")
        subtitle.setWordWrap(True)
        main_layout.addWidget(subtitle)

        # ── 滚动区域 ──
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content)
        content_layout.setSpacing(12)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # ── 功能网格 ──
        features = [
            ("👤", "AI 换脸", "精准替换视频中任意人物面部，支持多人脸检测与替换，\n保持表情、光照、角度自然融合"),
            ("👗", "AI 换服装", "一键更换视频人物着装风格，从休闲到正装，\n保持布料物理运动真实感"),
            ("🏞", "AI 换背景", "智能抠图 + 背景替换，绿幕级精度无需绿幕，\n支持任意场景背景图/视频"),
            ("🔄", "AI 换人物", "整体替换视频中指定人物为其他角色，\n保持动作、遮挡、光影一致性"),
            ("🖌", "自由框选替换", "手动框选任意区域 → AI理解语义 → 替换为\n指定物品或智能填充背景"),
            ("🗑", "智能删除物品", "框选视频中不需要的物体/人物/水印 →\nAI自动擦除并填充背景"),
        ]

        # 2列网格
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(12)
        for i, (icon, name, desc) in enumerate(features):
            card = _FeatureCard(icon, name, desc, content)
            row, col = divmod(i, 2)
            grid.addWidget(card, row, col)
        content_layout.addLayout(grid)

        content_layout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    w = VideoEditorPage()
    w.show()
    app.exec()
