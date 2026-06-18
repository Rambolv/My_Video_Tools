"""
启动弹窗 — 显示项目信息、硬件依赖、推荐设置、捐赠二维码
"""
import os
import cv2
import numpy as np
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt
from qfluentwidgets import (CardWidget, BodyLabel, StrongBodyLabel,
                           PushButton, CheckBox, qconfig)
from backend.config import config, tr, VERSION, BASE_DIR


def _load_qr_pixmap(size=160) -> QtGui.QPixmap:
    """加载捐赠二维码，尝试多个路径"""
    candidates = [
        # 相对于项目根目录
        os.path.join(os.path.dirname(os.path.dirname(BASE_DIR)),
                     'wechat_20260618155959_91_1.jpg'),
        # 相对于 CWD (resources/)
        os.path.join(os.getcwd(), '..', 'wechat_20260618155959_91_1.jpg'),
        # 绝对路径直接尝试
        r'c:\AI\AITOOLS\vsr_removecharacter_windows_gpu_v1.1.0\vsr-v1.4.0-windows-nvidia-cuda-12.6-release_test\wechat_20260618155959_91_1.jpg',
    ]
    for path in candidates:
        path = os.path.normpath(path)
        if os.path.exists(path):
            # 先试 QPixmap
            pm = QtGui.QPixmap(path)
            if not pm.isNull():
                return pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            # 回退 cv2 → QImage
            try:
                img = cv2.imread(path)
                if img is not None and img.size > 0:
                    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    h, w, ch = rgb.shape
                    qimg = QtGui.QImage(rgb.data, w, h, ch * w, QtGui.QImage.Format_RGB888)
                    pm = QtGui.QPixmap.fromImage(qimg)
                    if not pm.isNull():
                        return pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            except Exception:
                pass
    return QtGui.QPixmap()


class StartupDialog(QtWidgets.QDialog):
    """项目启动信息弹窗"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"关于 VSR魔改版 v{VERSION}")
        self.setFixedSize(540, 640)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet("""
            QDialog { background: #2a2a2a; }
            QLabel, BodyLabel, StrongBodyLabel { color: #f0e68c; }
        """)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        # ── 标题 ──
        title = StrongBodyLabel(f"VSR魔改版 - Video Subtitle Remover v{VERSION}")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffd700;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # ── 项目信息 ──
        info_card = CardWidget(self)
        info_layout = QtWidgets.QVBoxLayout(info_card)
        info_layout.setSpacing(6)
        info_layout.setContentsMargins(16, 12, 16, 12)

        info_lines = [
            ("📖 项目来源", "基于 YaoFANGUK/video-subtitle-remover 深度二次开发"),
            ("� 原版项目", "https://github.com/YaoFANGUK/video-subtitle-remover"),
            ("📄 许可证", "Apache License 2.0"),
            ("🔗 本仓库", "https://github.com/Rambolv/Video_Tools"),
        ]
        for icon_text, value in info_lines:
            row = QtWidgets.QHBoxLayout()
            row.setSpacing(8)
            lbl = BodyLabel(icon_text)
            lbl.setStyleSheet("font-size: 12px; font-weight: bold; min-width: 80px;")
            row.addWidget(lbl)
            # 超链接使用 QLabel + setOpenExternalLinks
            if value.startswith("http"):
                link = QtWidgets.QLabel(f'<a href="{value}" style="color:#4aa3df;">{value}</a>')
                link.setOpenExternalLinks(True)
                link.setStyleSheet("font-size: 12px;")
                row.addWidget(link, 1)
            else:
                val = BodyLabel(value)
                val.setStyleSheet("font-size: 12px; color: #f0e68c;")
                val.setWordWrap(True)
                row.addWidget(val, 1)
            info_layout.addLayout(row)

        # 提示可下载原版
        notice = BodyLabel("💡 如需原版 VSR，请访问上方原版项目链接下载")
        notice.setStyleSheet("font-size: 11px; color: #f5f5dc;")
        notice.setWordWrap(True)
        info_layout.addWidget(notice)

        layout.addWidget(info_card)

        # ── 硬件依赖与推荐设置 ──
        hw_card = CardWidget(self)
        hw_layout = QtWidgets.QVBoxLayout(hw_card)
        hw_layout.setSpacing(6)
        hw_layout.setContentsMargins(16, 12, 16, 12)

        hw_title = BodyLabel("⚙ 硬件依赖与推荐设置")
        hw_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #ffd700;")
        hw_layout.addWidget(hw_title)

        hw_items = [
            "• GPU: NVIDIA CUDA 11.8 / 12.6，建议 8GB+ VRAM",
            "• CPU: 支持 AVX2 指令集，4 核以上推荐",
            "• 内存: 建议 16GB+",
            "• 磁盘: 建议 20GB+ 可用空间（模型文件）",
            "• 系统: Windows 10/11 64位",
            "",
            "📌 推荐配置（1080p 视频）:",
            "• 显存 4-6GB: PP-OCRv4-Mobile + STTN-Auto, depth≤30",
            "• 显存 8-12GB: PP-OCRv4-Server + STTN-Auto, depth≤60",
            "• 显存 16-24GB: PP-OCRv5-Server + ProPainter, depth≤80",
            "• 显存 48GB+: E2FGVI (需 48GB+ VRAM)",
        ]
        for item in hw_items:
            lbl = BodyLabel(item)
            lbl.setStyleSheet("font-size: 11px; color: #f5f5dc;")
            lbl.setWordWrap(True)
            hw_layout.addWidget(lbl)

        layout.addWidget(hw_card)

        # ── 捐赠二维码 ──
        donate_card = CardWidget(self)
        donate_layout = QtWidgets.QVBoxLayout(donate_card)
        donate_layout.setSpacing(8)
        donate_layout.setContentsMargins(16, 12, 16, 12)

        donate_title = BodyLabel("❤️ 支持二次开发者")
        donate_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #ffd700;")
        donate_title.setAlignment(Qt.AlignCenter)
        donate_layout.addWidget(donate_title)

        # 二维码图片
        pixmap = _load_qr_pixmap(160)
        if not pixmap.isNull():
            qr_label = QtWidgets.QLabel()
            qr_label.setPixmap(pixmap)
            qr_label.setAlignment(Qt.AlignCenter)
            qr_label.setFixedHeight(170)
            donate_layout.addWidget(qr_label)

        tip = BodyLabel("Alipay 扫码捐赠，支持二次开发 ❤️")
        tip.setStyleSheet("font-size: 11px; color: #f0e68c;")
        tip.setAlignment(Qt.AlignCenter)
        donate_layout.addWidget(tip)

        layout.addWidget(donate_card)

        # ── 底部：不再显示 + 关闭按钮 ──
        bottom_row = QtWidgets.QHBoxLayout()
        bottom_row.setSpacing(12)

        self.skip_cb = CheckBox("我已捐助")
        self.skip_cb.setStyleSheet("font-size: 12px; color: #f0e68c;")
        self.skip_cb.setToolTip("勾选后累计 3 次不再显示此弹窗")
        bottom_row.addWidget(self.skip_cb)
        bottom_row.addStretch()

        close_btn = PushButton("我知道了")
        close_btn.setFixedWidth(120)
        close_btn.clicked.connect(self._on_close)
        bottom_row.addWidget(close_btn)

        layout.addLayout(bottom_row)

    def _on_close(self):
        if self.skip_cb.isChecked():
            # 累计捐助计数
            count = config.startupDonateCount.value + 1
            qconfig.set(config.startupDonateCount, count)
            if count >= 3:
                qconfig.set(config.skipStartupDialog, True)
        self.accept()
