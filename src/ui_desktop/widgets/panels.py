from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.ui_desktop.theming.metrics import SPACING

"""
Small reusable presentational widgets for the Today Command Center
(DESIGN.md § 6.1, `VR-TODAY-001`), established from genuine reuse needs
this checkpoint only: a compact summary stat, and a titled row with a
single action button used for both a Learning Queue item and the single
Suggested Next Action. Deliberately not a general-purpose component
library -- see theming/metrics.py and the M17 fresh-implementation
prompt § 7.

Both set ``Qt.WidgetAttribute.WA_StyledBackground``: a plain ``QWidget``
(unlike ``QLabel``/``QPushButton``, which descend from ``QFrame``/
``QAbstractButton`` and paint stylesheet backgrounds natively) silently
ignores a QSS ``background-color``/``border`` unless this attribute is
set -- discovered when the first native-window human visual acceptance
pass for this checkpoint showed these cards rendering as borderless,
backgroundless text despite the stylesheet rules existing and every
structural test passing (DESIGN.md § 2 Rule C: passing structural tests
is not evidence of visual completion).
"""


class _StyledContainer(QWidget):
    """A ``QWidget`` that actually paints its QSS background/border."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)


class SummaryStatCard(_StyledContainer):
    """One compact status metric (DESIGN.md § 6.1 dominance rule: the
    summary stays auxiliary -- a small value + label, never a KPI tile)."""

    def __init__(self, label: str, value: object, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("today-summary-card")

        caption = QLabel(label, self)
        caption.setObjectName("today-summary-caption")

        self._value_label = QLabel(str(value), self)
        self._value_label.setObjectName("today-summary-value")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING.md, SPACING.sm, SPACING.md, SPACING.sm)
        layout.setSpacing(2)
        layout.addWidget(caption)
        layout.addWidget(self._value_label)

    def set_value(self, value: object) -> None:
        self._value_label.setText(str(value))


class ActionRowCard(_StyledContainer):
    """A titled row with a subtitle and a single trailing action button.

    Used for both a Learning Queue item and the single Suggested Next
    Action card -- DESIGN.md § 6.1 groups the queue and Suggested Next
    Actions in the same central Command Workspace with shared grammar;
    only the data source differs.
    """

    action_triggered = Signal()

    def __init__(
        self,
        title: str,
        subtitle: str,
        button_text: str,
        *,
        button_enabled: bool,
        button_tooltip: str = "",
        object_name: str = "today-action-card",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)

        title_label = QLabel(title, self)
        title_label.setObjectName("today-action-title")

        subtitle_label = QLabel(subtitle, self)
        subtitle_label.setObjectName("today-action-subtitle")
        subtitle_label.setWordWrap(True)

        text_column = QVBoxLayout()
        text_column.setSpacing(1)
        text_column.addWidget(title_label)
        text_column.addWidget(subtitle_label)

        self._button = QPushButton(button_text, self)
        self._button.setObjectName("today-action-button")
        self._button.setEnabled(button_enabled)
        self._button.setMinimumWidth(96)
        if button_tooltip:
            self._button.setToolTip(button_tooltip)
        self._button.clicked.connect(self.action_triggered.emit)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACING.md, SPACING.sm, SPACING.md, SPACING.sm)
        layout.setSpacing(SPACING.md)
        layout.addLayout(text_column, 1)
        layout.addWidget(self._button, 0)

    @property
    def button_enabled(self) -> bool:
        return self._button.isEnabled()
