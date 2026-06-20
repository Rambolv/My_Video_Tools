"""
@desc: GPU 实时监控弹出对话框
显示 GPU 整体状态、所有占用 GPU 的进程实时排名（包括隐藏进程）
"""
from __future__ import annotations
import time

from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QThread
from PySide6.QtGui import QColor
from qfluentwidgets import (BodyLabel, PushButton, PrimaryPushButton,
                            FluentIcon)

from backend.tools.gpu_process_monitor import get_gpu_info, GpuOverallInfo, GpuProcessInfo


class _ProcessTableWidget(QtWidgets.QWidget):
    """GPU 进程表格组件（自绘，无需第三方表格控件）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._processes: list[GpuProcessInfo] = []
        self._header_height = 30
        self._row_height = 28

        self.setMinimumHeight(300)
        self.setStyleSheet("""
            _ProcessTableWidget { background: transparent; }
        """)

    def set_processes(self, processes: list[GpuProcessInfo]):
        self._processes = processes
        self.update()

    def paintEvent(self, event):
        """自绘表格（全部行绘制，由 ScrollArea 控制视口）"""
        from PySide6.QtGui import QPainter, QPen, QBrush, QFont, QColor

        painter = QPainter(self)
        painter.setRenderHint(painter.RenderHint.Antialiasing)

        w = self.width()
        col_widths = [65, 50, 50, 40, 40, 45, 75, 0]  # PID, GPU%, MEM%, ENC, DEC, 类型, 系统内存, Name(stretch)
        fixed_width = sum(col_widths[:-1])
        name_width = w - fixed_width - 20

        # 背景
        painter.fillRect(self.rect(), QColor(30, 30, 30))

        # ── 表头 ──
        headers = ["PID", "GPU%", "MEM%", "ENC", "DEC", "类型", "系统内存", "进程名"]
        painter.setPen(QColor(180, 180, 180))
        header_font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        painter.setFont(header_font)

        x = 10
        for i, h in enumerate(headers):
            cw = col_widths[i] if i < len(headers) - 1 else name_width
            align = Qt.AlignmentFlag.AlignLeft if i == len(headers) - 1 else Qt.AlignmentFlag.AlignCenter
            painter.drawText(x + (4 if i == len(headers) - 1 else 0), 0,
                             cw - (4 if i == len(headers) - 1 else 0), self._header_height,
                             align | Qt.AlignmentFlag.AlignVCenter, h)
            x += cw

        # 表头分隔线
        painter.setPen(QColor(60, 60, 60))
        painter.drawLine(10, self._header_height, w - 10, self._header_height)

        # ── 数据行（全部绘制，不再 break）──
        data_font = QFont("Consolas", 9)
        painter.setFont(data_font)

        y = self._header_height + 4
        for idx, proc in enumerate(self._processes):
            row_y = y + idx * self._row_height

            # 交替行背景
            if idx % 2 == 1:
                painter.fillRect(10, row_y, w - 20, self._row_height, QColor(38, 38, 38))

            # GPU% 颜色
            sm_color = QColor(255, 100, 100) if proc.gpu_sm_pct > 50 else (
                QColor(255, 200, 100) if proc.gpu_sm_pct > 20 else QColor(140, 200, 140))

            x = 10
            values = [
                (str(proc.pid), QColor(200, 200, 200)),
                (f"{proc.gpu_sm_pct:.0f}%", sm_color),
                (f"{proc.gpu_mem_pct:.0f}%", QColor(140, 200, 200)),
                (f"{proc.gpu_enc_pct:.0f}%" if proc.gpu_enc_pct > 0 else "-", QColor(180, 180, 180)),
                (f"{proc.gpu_dec_pct:.0f}%" if proc.gpu_dec_pct > 0 else "-", QColor(180, 180, 180)),
                (proc.gpu_type, QColor(180, 140, 255)),
                (f"{proc.system_mem_mb:.0f} MB" if proc.system_mem_mb > 0 else "N/A", QColor(200, 200, 200)),
                (proc.process_name, QColor(220, 220, 220)),
            ]

            for i, (text, color) in enumerate(values):
                painter.setPen(color)
                cw = col_widths[i] if i < len(values) - 1 else name_width
                align = Qt.AlignmentFlag.AlignLeft if i == len(values) - 1 else Qt.AlignmentFlag.AlignCenter
                painter.drawText(x + (4 if i == len(values) - 1 else 0), row_y,
                                 cw - (4 if i == len(values) - 1 else 0), self._row_height,
                                 align | Qt.AlignmentFlag.AlignVCenter, text)
                x += cw

        painter.end()

    def minimumSizeHint(self):
        total_h = self._header_height + len(self._processes) * self._row_height + 8
        return QtCore.QSize(620, total_h)

    def sizeHint(self):
        total_h = self._header_height + len(self._processes) * self._row_height + 8
        return QtCore.QSize(680, total_h)


class GpuMonitorDialog(QtWidgets.QDialog):
    """GPU 实时监控弹出对话框"""

    _refresh_interval = 2000  # 刷新间隔（毫秒）

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GPU 实时监控")
        self.setMinimumSize(720, 480)
        self.resize(760, 550)
        self.setAttribute(Qt.WA_DeleteOnClose)

        # 主布局
        self._main_layout = QtWidgets.QVBoxLayout(self)
        self._main_layout.setContentsMargins(20, 16, 20, 16)
        self._main_layout.setSpacing(8)

        # ── 标题 ──
        self._title_label = BodyLabel("GPU 实时监控")
        self._title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #e0e0e0; padding: 4px 0;")
        self._main_layout.addWidget(self._title_label)

        # ── GPU 状态概览 ──
        self._gpu_header = BodyLabel("正在获取 GPU 信息...")
        self._gpu_header.setStyleSheet("font-size: 14px; font-weight: bold; color: #4aa3df; padding: 4px 0;")
        self._main_layout.addWidget(self._gpu_header)

        self._gpu_stats = BodyLabel("")
        self._gpu_stats.setStyleSheet("font-size: 12px; color: #bbb; padding: 0 0 4px 0;")
        self._gpu_stats.setWordWrap(True)
        self._main_layout.addWidget(self._gpu_stats)

        # ── 分隔线 ──
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.HLine)
        sep.setStyleSheet("background: #333; max-height: 1px;")
        self._main_layout.addWidget(sep)

        # ── 进程表格 ──
        self._table_widget = _ProcessTableWidget()
        self._main_layout.addWidget(self._table_widget, 1)

        # ── 底部控制栏 ──
        self._control_layout = QtWidgets.QHBoxLayout()
        self._control_layout.setContentsMargins(0, 4, 0, 0)

        self._refresh_label = BodyLabel("自动刷新中 (2s)")
        self._refresh_label.setStyleSheet("font-size: 11px; color: #888;")
        self._control_layout.addWidget(self._refresh_label)

        self._control_layout.addStretch()

        self._refresh_now_btn = PushButton(FluentIcon.SYNC, "立即刷新")
        self._refresh_now_btn.clicked.connect(self._refresh_data)
        self._control_layout.addWidget(self._refresh_now_btn)

        self._auto_refresh_btn = PushButton("暂停刷新")
        self._auto_refresh_btn.clicked.connect(self._toggle_auto_refresh)
        self._control_layout.addWidget(self._auto_refresh_btn)

        self._close_btn = PrimaryPushButton(FluentIcon.CLOSE, "关闭")
        self._close_btn.clicked.connect(self.close)
        self._control_layout.addWidget(self._close_btn)

        self._main_layout.addLayout(self._control_layout)

        # 整体样式
        self.setStyleSheet("""
            GpuMonitorDialog {
                background: #1e1e1e;
            }
        """)

        # ── 后台线程和数据抓取器 ──
        self._thread = QThread(self)
        self._fetcher = _GpuDataFetcher()
        self._fetcher.moveToThread(self._thread)
        self._fetcher.finished.connect(self._on_data_ready)
        self._fetcher.error.connect(self._on_error)
        self._thread.start()

        # ── 定时器（UI 线程触发，取数据在后台） ──
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._request_refresh)
        self._timer.start(self._refresh_interval)
        self._auto_refresh_enabled = True
        self._pending = False

        # 初始数据加载
        QTimer.singleShot(100, self._request_refresh)

    def _request_refresh(self):
        """触发后台取数据"""
        if self._pending:
            return
        self._pending = True
        self._refresh_label.setText("刷新中...")
        QtCore.QMetaObject.invokeMethod(
            self._fetcher, "fetch", Qt.ConnectionType.QueuedConnection)

    def _on_data_ready(self, info):
        """后台数据到达，安全更新 UI"""
        self._pending = False
        try:
            if info is None:
                self._gpu_header.setText("⚠️ 无法获取 GPU 信息（nvidia-smi 不可用或无 NVIDIA GPU）")
                self._gpu_stats.setText("")
                self._table_widget.set_processes([])
                if self._auto_refresh_enabled:
                    self._refresh_label.setText("自动刷新中 (2s) | 无数据")
                return

            vram_pct = info.used_vram_mb / info.total_vram_mb * 100 if info.total_vram_mb > 0 else 0
            vram_color = "#e81123" if vram_pct > 90 else ("#ff8c00" if vram_pct > 70 else "#16ab39")

            self._gpu_header.setText(f"🖥 {info.name}")
            self._gpu_stats.setText(
                f"显存: <span style='color:{vram_color}'><b>{info.used_vram_mb} MiB</b></span> / {info.total_vram_mb} MiB"
                f" ({vram_pct:.1f}%)"
                f" &nbsp;|&nbsp; GPU: <b>{info.gpu_util_pct}%</b>"
                f" &nbsp;|&nbsp; 显存控制器: {info.mem_util_pct}%"
                f" &nbsp;|&nbsp; 温度: {info.temperature}℃"
                f" &nbsp;|&nbsp; 进程数: {len(info.processes)}"
            )
            self._gpu_stats.setTextFormat(Qt.RichText)
            self._table_widget.set_processes(info.processes)

            now_str = time.strftime("%H:%M:%S")
            if self._auto_refresh_enabled:
                self._refresh_label.setText(f"自动刷新中 (2s) | 上次: {now_str}")
            else:
                self._refresh_label.setText(f"已暂停 | 上次: {now_str}")
        except Exception as e:
            self._gpu_header.setText(f"⚠️ 显示错误: {e}")

    def _on_error(self, err_msg):
        self._pending = False
        self._gpu_header.setText(f"⚠️ 获取 GPU 信息出错: {err_msg}")

    def _toggle_auto_refresh(self):
        """切换自动刷新开关"""
        self._auto_refresh_enabled = not self._auto_refresh_enabled
        if self._auto_refresh_enabled:
            self._timer.start(self._refresh_interval)
            self._auto_refresh_btn.setText("暂停刷新")
            self._refresh_label.setText("自动刷新中 (2s)")
            self._request_refresh()
        else:
            self._timer.stop()
            self._auto_refresh_btn.setText("恢复刷新")
            self._refresh_label.setText("已暂停")

    def closeEvent(self, event):
        """关闭时清理后台线程"""
        self._timer.stop()
        if hasattr(self, '_thread') and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)
        super().closeEvent(event)


class _GpuDataFetcher(QtCore.QObject):
    """后台工作对象：在独立线程中获取 GPU 数据，通过信号返回结果"""
    finished = Signal(object)  # GpuOverallInfo or None
    error = Signal(str)

    @Slot()
    def fetch(self):
        """在工作线程中执行（不阻塞 UI）"""
        try:
            from backend.tools.gpu_process_monitor import get_gpu_info
            info = get_gpu_info()
            self.finished.emit(info)
        except Exception as e:
            self.error.emit(str(e))


class GpuMonitorWidget(QtWidgets.QWidget):
    """可嵌入的 GPU 实时监控组件（用于 Tab 嵌入），自动刷新（后台线程取数据）"""

    _refresh_interval = 3000  # 3秒刷新一次

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GpuMonitorWidget")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        # ── 功能说明 ──
        self._desc_label = BodyLabel(
            "💡 实时监控所有占用 GPU 的进程（含系统隐藏进程），按 GPU 计算负载降序排列，每 3 秒自动刷新一次"
        )
        self._desc_label.setStyleSheet("font-size: 11px; color: #888; padding: 2px 0;")
        self._desc_label.setWordWrap(True)
        layout.addWidget(self._desc_label)

        # ── GPU 状态概览行 ──
        self._gpu_header = BodyLabel("正在获取 GPU 信息...")
        self._gpu_header.setStyleSheet("font-size: 13px; font-weight: bold; color: #4aa3df;")
        layout.addWidget(self._gpu_header)

        self._gpu_stats = BodyLabel("")
        self._gpu_stats.setStyleSheet("font-size: 11px; color: #bbb;")
        self._gpu_stats.setWordWrap(True)
        layout.addWidget(self._gpu_stats)

        # ── 列说明 ──
        self._legend_label = BodyLabel(
            "列说明: PID=进程ID | GPU%=计算核心占用 | MEM%=显存控制器占用 | ENC/DEC=编解码器 | 系统内存=进程占用RAM"
        )
        self._legend_label.setStyleSheet("font-size: 10px; color: #666; padding: 2px 0;")
        layout.addWidget(self._legend_label)

        # ── 表格（放入 ScrollArea）──
        self._table_widget = _ProcessTableWidget()
        self._table_widget.setMinimumWidth(620)

        self._scroll_area = QtWidgets.QScrollArea()
        self._scroll_area.setWidgetResizable(False)  # 表格自己管理大小
        self._scroll_area.setWidget(self._table_widget)
        self._scroll_area.setStyleSheet("""
            QScrollArea { border: none; background: #1e1e1e; }
            QScrollBar:vertical { width: 8px; background: #2a2a2a; }
            QScrollBar::handle:vertical { background: #555; border-radius: 4px; min-height: 30px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        layout.addWidget(self._scroll_area, 1)

        # ── 底部控制栏 ──
        bottom_row = QtWidgets.QHBoxLayout()
        self._refresh_label = BodyLabel("")
        self._refresh_label.setStyleSheet("font-size: 10px; color: #666;")
        bottom_row.addWidget(self._refresh_label)
        bottom_row.addStretch()

        self._pause_btn = PushButton("暂停")
        self._pause_btn.setFixedWidth(60)
        self._pause_btn.clicked.connect(self._toggle_pause)
        bottom_row.addWidget(self._pause_btn)

        self._refresh_btn = PushButton(FluentIcon.SYNC, "刷新")
        self._refresh_btn.clicked.connect(self._request_refresh)
        bottom_row.addWidget(self._refresh_btn)

        layout.addLayout(bottom_row)

        # ── 后台线程和数据抓取器 ──
        self._thread = QThread(self)
        self._fetcher = _GpuDataFetcher()
        self._fetcher.moveToThread(self._thread)
        self._fetcher.finished.connect(self._on_data_ready)
        self._fetcher.error.connect(self._on_error)
        self._thread.start()

        # ── 定时器（UI 线程触发，实际取数据在后台线程） ──
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._request_refresh)
        self._timer.start(self._refresh_interval)
        self._paused = False
        self._pending = False
        self._first_run = True

        # ── 注册到资源管理器 ──
        try:
            from backend.tools.resource_manager import ResourceManager
            rm = ResourceManager.instance()
            rm.bind_gpu_monitor(self)
            rm.register_listener(self._on_profile_changed)
            # 应用当前等级
            interval = rm.gpu_monitor_interval_ms
            self._refresh_interval = interval
            self._timer.setInterval(interval)
        except Exception:
            pass

        # 初次刷新
        QTimer.singleShot(200, self._request_refresh)

    def _request_refresh(self):
        """触发后台取数据（不阻塞 UI）"""
        if self._pending:
            return
        self._pending = True
        self._refresh_label.setText("刷新中...")
        QtCore.QMetaObject.invokeMethod(
            self._fetcher, "fetch", Qt.ConnectionType.QueuedConnection)

    def _on_data_ready(self, info):
        """后台数据到达（主线程回调，安全更新 UI）"""
        self._pending = False
        try:
            if info is None:
                if self._first_run:
                    self._gpu_header.setText("⚠️ 无法获取 GPU 信息（nvidia-smi 不可用或无 NVIDIA GPU）")
                self._gpu_stats.setText("")
                self._table_widget.set_processes([])
                self._refresh_label.setText("N/A")
                self._first_run = False
                return

            self._first_run = False
            vram_pct = info.used_vram_mb / info.total_vram_mb * 100 if info.total_vram_mb > 0 else 0
            vram_color = "#e81123" if vram_pct > 90 else ("#ff8c00" if vram_pct > 70 else "#16ab39")

            self._gpu_header.setText(f"🖥 {info.name}")
            self._gpu_stats.setText(
                f"显存: <span style='color:{vram_color}'><b>{info.used_vram_mb} MiB</b></span> / {info.total_vram_mb} MiB"
                f" ({vram_pct:.1f}%)"
                f" &nbsp;|&nbsp; GPU: <b>{info.gpu_util_pct}%</b>"
                f" &nbsp;|&nbsp; 显存控制器: {info.mem_util_pct}%"
                f" &nbsp;|&nbsp; 温度: {info.temperature}℃"
                f" &nbsp;|&nbsp; 进程: {len(info.processes)}"
            )
            self._gpu_stats.setTextFormat(Qt.RichText)

            # 更新表格数据并刷新表格大小以适应 ScrollArea
            self._table_widget.set_processes(info.processes)
            self._table_widget.updateGeometry()

            self._refresh_label.setText(f"上次刷新: {time.strftime('%H:%M:%S')}")
        except Exception as e:
            self._refresh_label.setText(f"解析出错: {e}")

    def _on_error(self, err_msg):
        """后台取数据出错"""
        self._pending = False
        self._gpu_header.setText(f"⚠️ 错误: {err_msg}")
        self._refresh_label.setText("出错")

    def _toggle_pause(self):
        self._paused = not self._paused
        if self._paused:
            self._timer.stop()
            self._pause_btn.setText("恢复")
        else:
            self._timer.start(self._refresh_interval)
            self._pause_btn.setText("暂停")
            self._request_refresh()

    def _on_profile_changed(self, new_profile, old_profile):
        """ResourceManager 回调：等级变更时调整刷新率"""
        try:
            from backend.tools.resource_manager import ResourceManager
            rm = ResourceManager.instance()
            interval = rm.gpu_monitor_interval_ms
            self._refresh_interval = interval
            if not self._paused and self._timer.isActive():
                self._timer.setInterval(interval)
        except Exception:
            pass

    # ──────────────────────────────────────────
    # 资源管理器接口
    # ──────────────────────────────────────────

    def set_refresh_interval(self, interval_ms: int):
        """由 ResourceManager 调用：动态调整刷新间隔"""
        self._refresh_interval = interval_ms
        if not self._paused and self._timer.isActive():
            self._timer.setInterval(interval_ms)

    def pause_if_needed(self):
        """由 ResourceManager 调用：节能模式暂停自动刷新"""
        if not self._paused and self._timer.isActive():
            self._timer.stop()
            self._paused = True
            self._pause_btn.setText("恢复")
            self._refresh_label.setText("⚡ 资源节能已暂停")

    def resume_if_paused(self):
        """由 ResourceManager 调用：恢复自动刷新"""
        if self._paused:
            self._paused = False
            self._timer.start(self._refresh_interval)
            self._pause_btn.setText("暂停")
            self._request_refresh()

    def start(self):
        """启动自动刷新"""
        if not self._paused:
            self._timer.start(self._refresh_interval)

    def stop(self):
        """停止自动刷新"""
        self._timer.stop()

    def cleanup(self):
        """清理后台线程（退出时调用）"""
        self._timer.stop()
        # 取消注册资源管理器监听
        try:
            from backend.tools.resource_manager import ResourceManager
            ResourceManager.instance().unregister_listener(self._on_profile_changed)
        except Exception:
            pass
        if hasattr(self, '_thread') and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)

    def __del__(self):
        """析构时清理"""
        self.cleanup()


def show_gpu_monitor_dialog(parent=None):
    """便捷函数：显示 GPU 监控对话框"""
    dialog = GpuMonitorDialog(parent)
    dialog.exec()
