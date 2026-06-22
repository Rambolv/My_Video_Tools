"""
@desc: AI视频生成 — 文生视频/图生视频/动作模仿
"""
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt
from qfluentwidgets import (CardWidget, BodyLabel, StrongBodyLabel,
                            PrimaryPushButton, FluentIcon, ImageLabel)
from ui.component.donation_dialog import show_donation_dialog


class _GenFeatureCard(CardWidget):
    """生成功能卡片 — 垂直布局 + 大图标区"""

    def __init__(self, icon_emoji, title, desc, tags=None, parent=None):
        super().__init__(parent)
        self.setBorderRadius(12)
        self.setMinimumHeight(180)
        self.setFixedWidth(260)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(10)

        # 图标
        icon = QtWidgets.QLabel(icon_emoji)
        icon.setStyleSheet("font-size: 44px;")
        icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon)

        # 标题
        t = StrongBodyLabel(title)
        t.setStyleSheet("font-size: 16px; font-weight: bold; color: #e0e0e0;")
        t.setAlignment(Qt.AlignCenter)
        layout.addWidget(t)

        # 标签
        if tags:
            tag_row = QtWidgets.QHBoxLayout()
            tag_row.setSpacing(6)
            for tag_text in tags:
                tag = QtWidgets.QLabel(tag_text)
                tag.setStyleSheet("""
                    background: #333; color: #4aa3df; border-radius: 4px;
                    font-size: 10px; padding: 2px 8px;
                """)
                tag.setFixedHeight(20)
                tag_row.addWidget(tag)
            tag_row.addStretch()
            layout.addLayout(tag_row)

        # 描述
        d = BodyLabel(desc)
        d.setWordWrap(True)
        d.setStyleSheet("font-size: 11px; color: #888;")
        d.setAlignment(Qt.AlignCenter)
        layout.addWidget(d)

        layout.addStretch()

        # 按钮
        btn = PrimaryPushButton("立即生成")
        btn.setIcon(FluentIcon.PLAY)
        btn.clicked.connect(lambda: show_donation_dialog(self.window()))
        btn.setFixedHeight(32)
        btn.setStyleSheet("PrimaryPushButton { border-radius: 6px; font-weight: bold; }")
        layout.addWidget(btn)


class AIVideoGenPage(QtWidgets.QWidget):
    """AI视频生成页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AIVideoGenPage")

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # ── 标题 ──
        title = StrongBodyLabel("🤖 AI 视频生成")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #ffd700;")
        main_layout.addWidget(title)

        subtitle = BodyLabel("本地AI视频创作引擎 — 文生视频 · 图生视频 · 动作模仿，保护隐私，无需联网")
        subtitle.setStyleSheet("font-size: 13px; color: #aaa; padding-bottom: 8px;")
        subtitle.setWordWrap(True)
        main_layout.addWidget(subtitle)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content)
        content_layout.setSpacing(0)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # ── 三列功能卡片（水平排列）──
        cards_row = QtWidgets.QHBoxLayout()
        cards_row.setSpacing(16)

        features = [
            ("📝", "文生视频",
             "输入文字描述 → AI生成视频片段\n支持中文/English提示词\n多种风格：写实/动漫/油画/3D",
             ["# 文本驱动", "# CogVideoX", "# 本地推理"]),
            ("🖼", "图生视频",
             "上传图片 → AI让静态画面动起来\n支持首尾帧控制运动轨迹\n可指定运动幅度与方向",
             ["# 图片驱动", "# SVD/img2vid", "# 运动控制"]),
            ("🕺", "动作模仿",
             "上传驱动视频 + 目标人物 → AI迁移动作\n保持人物外观不变，仅复制运动姿态\n适合虚拟主播/数字人驱动",
             ["# 姿态迁移", "# AnimateAnyone", "# 数字人"]),
        ]

        for icon, name, desc, tags in features:
            card = _GenFeatureCard(icon, name, desc, tags, content)
            cards_row.addWidget(card)

        content_layout.addLayout(cards_row)

        # ── 使用说明 ──
        tip_card = CardWidget(content)
        tip_card.setBorderRadius(12)
        tl = QtWidgets.QVBoxLayout(tip_card)
        tl.setContentsMargins(20, 16, 20, 16)
        tl.setSpacing(6)

        tip_title = StrongBodyLabel("💡 使用说明")
        tip_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #4aa3df;")
        tl.addWidget(tip_title)

        tips = [
            "• 所有AI模型均本地运行，视频数据不会上传到任何服务器",
            "• 推荐 NVIDIA GPU 8GB+ VRAM，首次运行需下载模型（约20-50GB）",
            "• 生成速度取决于视频长度和分辨率，10秒 1080p 约需 5-15 分钟",
            "• 支持中途暂停/继续，自动保存生成进度",
        ]
        for t in tips:
            lbl = BodyLabel(t)
            lbl.setStyleSheet("font-size: 11px; color: #999;")
            lbl.setWordWrap(True)
            tl.addWidget(lbl)

        content_layout.addSpacing(16)
        content_layout.addWidget(tip_card)
        content_layout.addStretch()

        scroll.setWidget(content)
        main_layout.addWidget(scroll)
