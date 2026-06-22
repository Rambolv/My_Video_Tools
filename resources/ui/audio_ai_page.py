"""
@desc: 声音自由生成修改大师 — AI克隆声音/音乐/换声
"""
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt
from qfluentwidgets import (CardWidget, BodyLabel, StrongBodyLabel,
                            PrimaryPushButton, FluentIcon)
from ui.component.donation_dialog import show_donation_dialog


class _AudioFeatureCard(CardWidget):
    """音频功能卡片 — 横向布局"""

    def __init__(self, icon_emoji, title, desc, parent=None):
        super().__init__(parent)
        self.setBorderRadius(12)
        self.setMinimumHeight(100)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)

        # 左侧图标
        icon = QtWidgets.QLabel(icon_emoji)
        icon.setStyleSheet("font-size: 40px;")
        icon.setFixedWidth(56)
        icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon)

        # 中间文字
        text_w = QtWidgets.QVBoxLayout()
        t = StrongBodyLabel(title)
        t.setStyleSheet("font-size: 15px; font-weight: bold; color: #e0e0e0;")
        text_w.addWidget(t)
        d = BodyLabel(desc)
        d.setWordWrap(True)
        d.setStyleSheet("font-size: 12px; color: #999;")
        text_w.addWidget(d)
        layout.addLayout(text_w, 1)

        # 右侧按钮
        btn = PrimaryPushButton("体验")
        btn.setFixedSize(72, 32)
        btn.clicked.connect(lambda: show_donation_dialog(self.window()))
        btn.setStyleSheet("PrimaryPushButton { border-radius: 6px; font-weight: bold; }")
        layout.addWidget(btn)


class AudioAIPage(QtWidgets.QWidget):
    """声音自由生成修改大师页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AudioAIPage")

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # ── 标题 ──
        title = StrongBodyLabel("🎵 声音自由生成修改大师")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #ffd700;")
        main_layout.addWidget(title)

        subtitle = BodyLabel("AI音频全栈套件 — 声音克隆、AI音乐创作、智能变声，一站式音频工作站")
        subtitle.setStyleSheet("font-size: 13px; color: #aaa; padding-bottom: 8px;")
        subtitle.setWordWrap(True)
        main_layout.addWidget(subtitle)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content)
        content_layout.setSpacing(10)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # ── 功能列表 ──
        features = [
            ("🎙", "AI 声音克隆",
             "上传任意人声样本（≥30秒）→ AI学习音色特征 → 输入文字即可生成以假乱真的语音，支持中英日韩多语种"),
            ("🎼", "AI 音乐生成",
             "输入歌词 + 选择风格（流行/古典/电子/嘻哈/国风）→ AI创作原创编曲 → 一键导出高品质音频文件"),
            ("🔄", "AI 换声音",
             "替换视频/音频中的人声为指定目标音色，保持语气、语速、情感不变，支持实时预览与批量处理"),
            ("📝", "AI 语音合成 (TTS)",
             "高质量文字转语音引擎，数十种音色可选，支持语速/音调/情感调节，适合配音、旁白、有声书"),
        ]

        for icon, name, desc in features:
            card = _AudioFeatureCard(icon, name, desc, content)
            content_layout.addWidget(card)

        content_layout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)
