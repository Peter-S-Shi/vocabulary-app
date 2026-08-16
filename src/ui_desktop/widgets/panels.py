from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

"""
Small reusable presentational widgets for the Today Command Center
(DESIGN.md § 6.1, `VR-TODAY-001`), established from genuine reuse needs
this checkpoint only: a compact summary stat, and a titled row with a
single action button used for both a Learning Queue item and the single
Suggested Next Action. Deliberately not a general-purpose component
library -- see theming/metrics.py and the M17 fresh-implementation
prompt § 7.
"""


class SummaryStatCard(QWidget):
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
        layout.addWidget(caption)
        layout.addWidget(self._value_label)

    def set_value(self, value: object) -> None:
        self._value_label.setText(str(value))


class ActionRowCard(QWidget):
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
        text_column.setSpacing(2)
        text_column.addWidget(title_label)
        text_column.addWidget(subtitle_label)

        self._button = QPushButton(button_text, self)
        self._button.setObjectName("today-action-button")
        self._button.setEnabled(button_enabled)
        if button_tooltip:
            self._button.setToolTip(button_tooltip)
        self._button.clicked.connect(self.action_triggered.emit)

        layout = QHBoxLayout(self)
        layout.addLayout(text_column, 1)
        layout.addWidget(self._button, 0)

    @property
    def button_enabled(self) -> bool:
        return self._button.isEnabled()
