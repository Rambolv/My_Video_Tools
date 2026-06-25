"""
@desc: 声音自由生成修改大师 — AI克隆声音/音乐/换声
集成本地部署项目：ACE-Step 1.5（音乐生成）、VoxCPM2（声音克隆）
"""
import os
import webbrowser
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt
from qfluentwidgets import (CardWidget, BodyLabel, StrongBodyLabel,
                            PrimaryPushButton, PushButton, FluentIcon,
                            InfoBar)
from backend.config import config, tr
from backend.tools.external_launcher import (
    launch_project, stop_project, open_project_url
)
from ui.component.donation_dialog import show_donation_dialog


class _AudioFeatureCard(CardWidget):
    """音频功能卡片 — 横向布局，支持启动外部项目"""

    def __init__(self, icon_emoji, title, desc, project_key=None,
                 external_url=None, parent=None):
        super().__init__(parent)
        self._project_key = project_key
        self._external_url = external_url
        self.setBorderRadius(12)
        self.setMinimumHeight(110)
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

        # 右侧按钮区
        btn_layout = QtWidgets.QVBoxLayout()
        btn_layout.setSpacing(4)

        if project_key:
            self._launch_btn = PrimaryPushButton("🚀 启动")
            self._launch_btn.setFixedSize(80, 32)
            self._launch_btn.clicked.connect(self._on_launch)
            btn_layout.addWidget(self._launch_btn, 0, Qt.AlignRight)

            self._open_btn = PushButton("🌐 打开")
            self._open_btn.setFixedSize(80, 28)
            self._open_btn.clicked.connect(self._on_open)
            self._open_btn.setVisible(False)
            btn_layout.addWidget(self._open_btn, 0, Qt.AlignRight)

            self._stop_btn = PushButton("⏹ 停止")
            self._stop_btn.setFixedSize(80, 28)
            self._stop_btn.clicked.connect(self._on_stop)
            self._stop_btn.setVisible(False)
            btn_layout.addWidget(self._stop_btn, 0, Qt.AlignRight)
        elif external_url:
            btn = PrimaryPushButton("了解详情")
            btn.setFixedSize(80, 32)
            btn.clicked.connect(lambda: webbrowser.open(external_url))
            btn_layout.addWidget(btn, 0, Qt.AlignRight)
        else:
            btn = PrimaryPushButton("体验")
            btn.setFixedSize(72, 32)
            btn.clicked.connect(lambda: show_donation_dialog(self.window()))
            btn_layout.addWidget(btn, 0, Qt.AlignRight)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def _on_launch(self):
        if not self._project_key:
            return
        success, msg = launch_project(self._project_key)
        if success:
            InfoBar.success(title="启动成功", content=msg, duration=5000,
                           parent=self.window())
            self._launch_btn.setVisible(False)
            self._open_btn.setVisible(True)
            self._stop_btn.setVisible(True)
            QtCore.QTimer.singleShot(3000, self._on_open)
        else:
            InfoBar.error(title="启动失败", content=msg, duration=5000,
                         parent=self.window())

    def _on_open(self):
        if self._project_key:
            url = open_project_url(self._project_key)
            if url:
                webbrowser.open(url)

    def _on_stop(self):
        if not self._project_key:
            return
        success, msg = stop_project(self._project_key)
        if success:
            InfoBar.info(title="已停止", content=msg, duration=3000,
                        parent=self.window())
            self._launch_btn.setVisible(True)
            self._open_btn.setVisible(False)
            self._stop_btn.setVisible(False)


class AudioAIPage(QtWidgets.QWidget):
    """声音自由生成修改大师页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AudioAIPage")

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        title = StrongBodyLabel("🎵 声音自由生成修改大师")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #ffd700;")
        main_layout.addWidget(title)

        subtitle = BodyLabel(
            "AI音频全栈套件 — 声音克隆、AI音乐创作、智能变声，一站式音频工作站\n"
            "💡 已集成本地项目：VoxCPM2（声音克隆）、ACE-Step 1.5（音乐生成）")
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

        features = [
            ("🎙", "AI 声音克隆",
             "🎛️ 可控克隆 & 极致克隆：上传参考音频 → 保留原始音色灵活控制\n"
             "🎨 声音设计：无需参考音频，自然语言描述生成全新音色\n"
             "💻 已部署 VoxCPM2 (48kHz无损)，支持30+语言、9种中文方言",
             "voxcpm2", None),
            ("🎼", "AI 音乐生成",
             "🎵 ACE-Step 1.5：开源最强音乐生成，质量接近Suno\n"
             "📝 输入歌词+风格 → 完整编曲\n"
             "🎸 支持续写、局部重绘、人声伴奏分离",
             "ace_step", None),
            ("🔄", "AI 换声音 (语音转换)",
             "🎤 RVC v2：社区最强，10-30分钟训练样本即可克隆目标音色\n"
             "⚡ 实时变声延迟<100ms，支持歌声转换/跨语言音色迁移",
             None, "https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI"),
            ("📝", "AI 语音合成 (TTS)",
             "🗣 GPT-SoVITS v3：中文最强，5秒零样本克隆\n"
             "🌊 CosyVoice 3.0：流式方案，首包延迟<300ms\n"
             "⚡ F5-TTS：Flow Matching极速方案，显存仅~2GB",
             None, "https://github.com/RVC-Boss/GPT-SoVITS"),
        ]

        for icon, name, desc, proj_key, ext_url in features:
            card = _AudioFeatureCard(icon, name, desc,
                                     project_key=proj_key,
                                     external_url=ext_url,
                                     parent=content)
            content_layout.addWidget(card)

        content_layout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    w = AudioAIPage()
    w.show()
    app.exec()
