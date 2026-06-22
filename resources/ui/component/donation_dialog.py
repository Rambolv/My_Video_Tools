"""
@desc: 功能开发中弹窗 — 显示打赏二维码和项目链接
"""
import os
import cv2
import numpy as np
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt
from qfluentwidgets import BodyLabel, StrongBodyLabel, PushButton, CardWidget

from backend.config import BASE_DIR


def _load_qr_pixmap(size=200) -> QtGui.QPixmap:
    """加载支付宝二维码"""
    candidates = [
        os.path.join(os.path.dirname(os.path.dirname(BASE_DIR)),
                     'wechat_20260618155959_91_1.jpg'),
        os.path.join(os.getcwd(), '..', 'wechat_20260618155959_91_1.jpg'),
        r'c:\AI\AITOOLS\vsr_removecharacter_windows_gpu_v1.1.0\vsr-v1.4.0-windows-nvidia-cuda-12.6-release_test\wechat_20260618155959_91_1.jpg',
    ]
    for path in candidates:
        path = os.path.normpath(path)
        if os.path.exists(path):
            pm = QtGui.QPixmap(path)
            if not pm.isNull():
                return pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
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


def show_donation_dialog(parent=None):
    """显示功能开发中 + 打赏弹窗"""
    dialog = QtWidgets.QDialog(parent)
    dialog.setWindowTitle("🚧 功能开发中")
    dialog.setFixedSize(440, 520)
    dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
    dialog.setStyleSheet("""
        QDialog { background: #1e1e1e; }
    """)

    layout = QtWidgets.QVBoxLayout(dialog)
    layout.setSpacing(14)
    layout.setContentsMargins(28, 24, 28, 24)

    # ── 标题 ──
    title = StrongBodyLabel("🚧 计划开发中")
    title.setStyleSheet("font-size: 20px; font-weight: bold; color: #ffd700;")
    title.setAlignment(Qt.AlignCenter)
    layout.addWidget(title)

    # ── 说明文字 ──
    info_card = CardWidget(dialog)
    info_card.setBorderRadius(8)
    il = QtWidgets.QVBoxLayout(info_card)
    il.setContentsMargins(16, 14, 16, 14)
    il.setSpacing(6)

    msg_lines = [
        "此功能正在全力开发中 🏗",
        "",
        "目前弹尽粮绝 💸，需要大家的支持才能继续完善。",
        "继续打赏 → 继续充值 → 复活完善功能！",
        "",
        "您的每一份支持，都是功能上线的加速器 ❤️",
    ]
    for line in msg_lines:
        lbl = BodyLabel(line)
        lbl.setStyleSheet("font-size: 13px; color: #ccc;")
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignCenter)
        il.addWidget(lbl)
    layout.addWidget(info_card)

    # ── 二维码 ──
    qr_card = CardWidget(dialog)
    qr_card.setBorderRadius(8)
    ql = QtWidgets.QVBoxLayout(qr_card)
    ql.setContentsMargins(16, 14, 16, 14)
    ql.setSpacing(8)

    qr_title = BodyLabel("📱 Alipay 扫码支持")
    qr_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #4aa3df;")
    qr_title.setAlignment(Qt.AlignCenter)
    ql.addWidget(qr_title)

    pixmap = _load_qr_pixmap(180)
    if not pixmap.isNull():
        qr_label = QtWidgets.QLabel()
        qr_label.setPixmap(pixmap)
        qr_label.setAlignment(Qt.AlignCenter)
        qr_label.setFixedHeight(190)
        ql.addWidget(qr_label)

    tip = BodyLabel("Alipay 扫码打赏，支持开发继续前行 ❤️")
    tip.setStyleSheet("font-size: 11px; color: #f0e68c;")
    tip.setAlignment(Qt.AlignCenter)
    ql.addWidget(tip)
    layout.addWidget(qr_card)

    # ── GitHub 链接 ──
    gh_btn = PushButton("⭐ Star 项目 on GitHub")
    gh_btn.setStyleSheet("""
        PushButton {
            background-color: #333;
            color: #4aa3df;
            border: 1px solid #4aa3df;
            border-radius: 6px;
            font-size: 13px;
            font-weight: bold;
            padding: 8px;
        }
        PushButton:hover {
            background-color: #3a3a3a;
        }
    """)
    gh_btn.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(
        QtCore.QUrl("https://github.com/Rambolv/My_Video_Tools")))
    layout.addWidget(gh_btn)

    # ── 关闭按钮 ──
    close_btn = PushButton("知道了，期待上线！")
    close_btn.setStyleSheet("""
        PushButton {
            background-color: #2d7d2d;
            color: white;
            border-radius: 6px;
            font-size: 13px;
            font-weight: bold;
            padding: 8px;
        }
        PushButton:hover {
            background-color: #3a9a3a;
        }
    """)
    close_btn.clicked.connect(dialog.accept)
    layout.addWidget(close_btn)

    dialog.exec()
