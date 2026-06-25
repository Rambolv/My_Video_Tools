"""
倒计时对话框 — 用于任务完成后自动关机/自动关程序时的倒计时提示
用户可点击取消按钮中止操作
"""
import sys
import subprocess
from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import Qt, QTimer
from qfluentwidgets import (CardWidget, BodyLabel, StrongBodyLabel,
                           PushButton, PrimaryPushButton)


class CountdownDialog(QtWidgets.QDialog):
    """倒计时对话框，显示倒计时并提供取消按钮"""

    # 信号：倒计时取消
    cancelled = QtCore.Signal()
    # 信号：倒计时完成
    finished = QtCore.Signal()

    # 操作类型
    ACTION_SHUTDOWN = "shutdown"
    ACTION_CLOSE_PROGRAM = "close_program"

    def __init__(self, action_type, countdown_seconds=5, parent=None):
        """
        Args:
            action_type: 操作类型，ACTION_SHUTDOWN 或 ACTION_CLOSE_PROGRAM
            countdown_seconds: 倒计时秒数
            parent: 父窗口
        """
        super().__init__(parent)
        self.action_type = action_type
        self.countdown = countdown_seconds
        self._is_cancelled = False

        self.setWindowTitle("任务完成提醒")
        self.setFixedSize(420, 200)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowContextHelpButtonHint |
            Qt.WindowStaysOnTopHint
        )
        self.setStyleSheet("""
            QDialog { background: #2a2a2a; }
            QLabel, BodyLabel, StrongBodyLabel { color: #f0e68c; }
        """)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        # ── 图标 + 标题 ──
        title_text = "系统将在倒计时结束后自动关机！" if action_type == self.ACTION_SHUTDOWN else "程序将在倒计时结束后自动关闭！"
        self.title_label = StrongBodyLabel(f"⚠️ {title_text}")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #ff6b6b;")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        # ── 倒计时显示 ──
        self.countdown_label = BodyLabel(f"{self.countdown} 秒")
        self.countdown_label.setStyleSheet(
            "font-size: 48px; font-weight: bold; color: #ffd700;")
        self.countdown_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.countdown_label)

        # ── 提示文字 ──
        hint_text = "点击「取消」中止关机操作" if action_type == self.ACTION_SHUTDOWN else "点击「取消」中止关闭程序"
        hint = BodyLabel(hint_text)
        hint.setStyleSheet("font-size: 12px; color: #aaa;")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

        # ── 取消按钮 ──
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()
        self.cancel_btn = PrimaryPushButton("取消")
        self.cancel_btn.setFixedWidth(120)
        self.cancel_btn.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # ── 启动倒计时定时器 ──
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)  # 每秒触发一次

    def _tick(self):
        """每秒更新倒计时"""
        self.countdown -= 1
        self.countdown_label.setText(f"{self.countdown} 秒")
        if self.countdown <= 0:
            self.timer.stop()
            self.finished.emit()
            self.accept()

    def _on_cancel(self):
        """用户点击取消"""
        self._is_cancelled = True
        self.timer.stop()
        self.cancelled.emit()
        self.reject()

    def is_cancelled(self):
        return self._is_cancelled

    @staticmethod
    def shutdown_system():
        """执行系统关机（Windows）"""
        try:
            if sys.platform == "win32":
                # 使用 shutdown 命令，延时 3 秒让程序有时间退出
                subprocess.run(
                    ["shutdown", "/s", "/t", "3", "/c", "VSR 任务完成自动关机"],
                    check=False, creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                subprocess.run(["shutdown", "-h", "+1"], check=False)
        except Exception as e:
            print(f"关机失败: {e}")

    @staticmethod
    def cancel_shutdown():
        """取消已计划的关机"""
        try:
            if sys.platform == "win32":
                subprocess.run(
                    ["shutdown", "/a"],
                    check=False, creationflags=subprocess.CREATE_NO_WINDOW
                )
        except Exception:
            pass
