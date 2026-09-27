"""Collapsible export sections and screen-bounded dialog sizing."""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QScrollArea, QSizePolicy, QToolButton, QVBoxLayout, QWidget


class ExportCodeSection(QFrame):
    def __init__(self, body, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(7, 3, 7, 4)
        self.toggle = QToolButton(self)
        self.toggle.setText("Code")
        self.toggle.setCheckable(True)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.clicked.connect(self.set_expanded)
        layout.addWidget(self.toggle, 0, Qt.AlignmentFlag.AlignLeft)
        self.body = body
        body.setMinimumHeight(260)
        layout.addWidget(body)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.set_expanded(True)

    def set_expanded(self, expanded):
        self.toggle.setChecked(expanded)
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        self.body.setVisible(expanded)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred if expanded else QSizePolicy.Policy.Maximum)


def configure_export_layout(dialog, compact):
    """Keep controls reachable on small screens without clipping the preview."""
    content = QWidget()
    content.setLayout(dialog.layout())
    scroll = QScrollArea(dialog)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setWidgetResizable(True)
    scroll.setWidget(content)
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(scroll)
    dialog.setMinimumSize(680, 0)
    dialog.export_scroll = scroll

    def fit_window():
        content.layout().activate()
        available = dialog.screen().availableGeometry()
        height = min(content.sizeHint().height() + 4, available.height() - 60)
        # Only the open code editor benefits from additional vertical space.
        dialog.setMaximumHeight(16777215 if dialog.code_section.toggle.isChecked() else height)
        dialog.setMinimumHeight(height)
        if dialog.isMaximized():
            return
        width = min(max(dialog.width(), content.minimumSizeHint().width() + 24), available.width() - 30)
        dialog.resize(width, height)
        if dialog.isVisible():
            dialog.move(max(available.left(), min(dialog.x(), available.right() - dialog.width())),
                        max(available.top(), min(dialog.y(), available.bottom() - dialog.height() - 35)))

    sections = ((dialog.settings_panel.options_toggle, dialog.settings_panel.set_options_expanded),
                (dialog.fb_preview_panel.toggle, dialog.fb_preview_panel.set_expanded),
                (dialog.code_section.toggle, dialog.code_section.set_expanded))
    for toggle, setter in sections:
        setter(not compact)
        toggle.clicked.connect(lambda _checked: QTimer.singleShot(0, fit_window))
    dialog.fb_preview_panel.toggle.clicked.connect(
        lambda expanded: QTimer.singleShot(
            0, lambda: scroll.ensureWidgetVisible(dialog.fb_preview_panel, 0, 0)
        ) if expanded else None
    )
    QTimer.singleShot(0, fit_window)
