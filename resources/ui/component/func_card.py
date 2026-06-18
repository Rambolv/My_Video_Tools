"""
可折叠功能卡片 + 帮助按钮组件
支持持久化折叠状态（保存到 config）
"""
from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtCore import Qt
from qfluentwidgets import CardWidget, BodyLabel, ToolTipFilter, ToolTipPosition


class HelpButton(QtWidgets.QPushButton):
    """圆形 ? 帮助按钮，点击弹出详细说明 + 长悬停显示工具提示"""

    def __init__(self, title, detail_text, parent=None):
        super().__init__("?", parent)
        self._help_title = title
        self._help_text = detail_text
        self.setFixedSize(22, 22)
        self.setCursor(Qt.PointingHandCursor)
        # 悬停工具提示显示简短说明
        short = detail_text.replace("<br>", "\n").replace("<b>", "").replace("</b>", "")
        if len(short) > 120:
            short = short[:117] + "..."
        self.setToolTip(short)
        # 鼠标悬停 0.6 秒后显示完整工具提示
        self.installEventFilter(ToolTipFilter(self, 600, ToolTipPosition.TOP))
        self.setStyleSheet("""
            QPushButton {
                border: 1px solid #888;
                border-radius: 11px;
                background: transparent;
                color: #888;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                border-color: #4aa3df;
                color: #4aa3df;
                background: rgba(74, 163, 223, 0.12);
            }
        """)
        self.clicked.connect(self._show_help)

    def _show_help(self):
        from qfluentwidgets import MessageBox
        w = MessageBox(self._help_title, self._help_text, self.window())
        w.yesButton.setText("知道了")
        w.cancelButton.hide()
        w.exec()


class CollapsibleFuncCard(CardWidget):
    """可折叠的功能大区卡片，支持持久化折叠状态"""

    def __init__(self, title, icon_emoji="⚙", config_item=None, parent=None,
                 subtitle=None):
        """
        Parameters
        ----------
        title : str
        icon_emoji : str
        config_item : ConfigItem or None
        subtitle : str or None  副标题/说明
        parent : QWidget
        """
        super().__init__(parent)
        self._config_item = config_item
        if config_item is not None:
            self._expanded = not config_item.value
        else:
            self._expanded = True

        self.setBorderRadius(8)

        self._main_layout = QtWidgets.QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        # 标题栏
        self._header = QtWidgets.QWidget()
        self._header.setFixedHeight(38)
        self._header.setCursor(Qt.PointingHandCursor)
        self._header.mousePressEvent = lambda e: self._toggle()
        header_layout = QtWidgets.QHBoxLayout(self._header)
        header_layout.setContentsMargins(12, 0, 12, 0)

        # 箭头 - 更大
        self._arrow_label = QtWidgets.QLabel("▼" if self._expanded else "▶")
        self._arrow_label.setStyleSheet("font-size: 13px; color: #666; font-weight: bold;")
        header_layout.addWidget(self._arrow_label)

        self._icon_label = QtWidgets.QLabel(icon_emoji)
        self._icon_label.setStyleSheet("font-size: 16px; margin-left: 6px;")
        header_layout.addWidget(self._icon_label)

        self._title_label = BodyLabel(title, self._header)
        self._title_label.setStyleSheet("font-size: 14px; font-weight: bold; padding-left: 6px;")
        header_layout.addWidget(self._title_label)
        if subtitle:
            sub = BodyLabel(subtitle, self._header)
            sub.setStyleSheet("font-size: 10px; color: #888; padding-left: 4px;")
            header_layout.addWidget(sub)
        header_layout.addStretch()

        self._main_layout.addWidget(self._header)

        # 内容容器
        self._content_container = QtWidgets.QWidget()
        self._content_layout = QtWidgets.QVBoxLayout(self._content_container)
        self._content_layout.setContentsMargins(12, 4, 12, 8)
        self._content_layout.setSpacing(6)
        self._main_layout.addWidget(self._content_container)
        self._content_container.setVisible(self._expanded)

    def addWidget(self, widget):
        self._content_layout.addWidget(widget)

    def addLayout(self, layout):
        self._content_layout.addLayout(layout)

    def addStretch(self, stretch=0):
        self._content_layout.addStretch(stretch)

    def _toggle(self):
        self._expanded = not self._expanded
        self._content_container.setVisible(self._expanded)
        self._arrow_label.setText("▼" if self._expanded else "▶")
        if self._config_item is not None:
            from qfluentwidgets import qconfig
            qconfig.set(self._config_item, not self._expanded)

    def collapse(self):
        self._expanded = False
        self._content_container.setVisible(False)
        self._arrow_label.setText("▶")
        if self._config_item is not None:
            from qfluentwidgets import qconfig
            qconfig.set(self._config_item, True)

    def expand(self):
        self._expanded = True
        self._content_container.setVisible(True)
        self._arrow_label.setText("▼")
        if self._config_item is not None:
            from qfluentwidgets import qconfig
            qconfig.set(self._config_item, False)

    @property
    def content_layout(self):
        return self._content_layout

    @property
    def is_expanded(self):
        return self._expanded


class SettingRow(QtWidgets.QWidget):
    """一行设置: 标签 + 控件 [+ 帮助按钮] - 自适应高度/自动换行"""

    def __init__(self, label_text, widget, help_title=None, help_text=None,
                 parent=None, tooltip=None):
        super().__init__(parent)
        self._label_text = label_text
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.label = BodyLabel(label_text, self)
        self.label.setFixedWidth(80)
        self.label.setStyleSheet("font-size: 12px;")
        self.label.setWordWrap(True)
        layout.addWidget(self.label)

        layout.addWidget(widget, 1)

        if help_title and help_text:
            self.help_btn = HelpButton(help_title, help_text, self)
            layout.addWidget(self.help_btn)
        else:
            self.help_btn = None

        # 工具提示
        if tooltip:
            self.setToolTip(tooltip)
            self.installEventFilter(ToolTipFilter(self, 600, ToolTipPosition.TOP))

        # 不固定高度，让内容决定
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                           QtWidgets.QSizePolicy.Preferred)


class SectionHeader(QtWidgets.QWidget):
    """子功能区块标题 — 视觉层次区分（粗体 + 缩进 + 分隔线）"""

    def __init__(self, title, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 0, 0)
        self.label = BodyLabel(title, self)
        self.label.setStyleSheet("""
            font-size: 12px; font-weight: bold; color: #4aa3df;
            padding: 2px 6px; border-left: 3px solid #4aa3df;
        """)
        layout.addWidget(self.label)
        layout.addStretch()
        self.setFixedHeight(26)
