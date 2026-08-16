from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.ui_desktop.controllers.settings_controller import SettingsController
from src.ui_desktop.state.preferences import QUIZ_PRESENTATION_LABELS
from src.ui_desktop.theming.metrics import SPACING

"""
Settings -- Management Mode, P8 Settings Form (DESIGN.md § 8: "Management
Rail + categorized settings structure + comfortable form density. Settings
is not a dashboard..."). M17 Feature 3B builds ONLY the minimum bounded
vertical slice this checkpoint's real preference needs -- Quiz presentation
-- not the full future Settings product (M17 Feature 3B prompt § 6):
Appearance/Accent/Motion/language/storage/backup/audio/privacy/database
settings are explicitly out of scope here and continue working exactly as
they do today (i.e. not yet exposed through any Settings UI).

Design -> Implementation trace:

  shell/chrome        -> ordinary Management Mode workspace, reached
                          through the Management Rail like Today/Entries --
                          no Study-mode chrome swap, no transient
                          drawer/dialog.
  page structure       -> page title + one category heading ("Quiz") +
                          one settings row, per P8's "categorized settings
                          structure" formula.
  Quiz presentation row -> label + native QComboBox showing the current
                          value; VR-STUDY-002 prompt § 6/§ 7: this is the
                          ONE control location for this preference -- no
                          second selector exists anywhere else (Review,
                          Choose Quiz Type, Quiz session bar, completion).
  persistence           -> SettingsController.set_quiz_presentation()
                          writes straight through to the existing
                          state/preferences.py file; the next Quiz launched
                          in this session (M17 Feature 3B prompt § 7) or
                          after a restart (§ 5) uses the saved value.
"""


class SettingsView(QWidget):
    def __init__(self, controller: SettingsController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("settings-root")
        self._controller = controller

        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING.xl, SPACING.xl, SPACING.xl, SPACING.xl)
        root.setSpacing(SPACING.lg)
        root.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("Settings", self)
        title.setObjectName("settings-page-title")
        root.addWidget(title)

        quiz_heading = QLabel("Quiz", self)
        quiz_heading.setObjectName("settings-section-heading")
        root.addWidget(quiz_heading)

        row = QWidget(self)
        row.setObjectName("settings-row")
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(SPACING.md, SPACING.md, SPACING.md, SPACING.md)
        row_layout.setSpacing(SPACING.md)

        row_label = QLabel("Quiz presentation", row)
        row_label.setObjectName("settings-row-label")
        row_layout.addWidget(row_label, 0)
        row_layout.addStretch(1)

        self._quiz_presentation_combo = QComboBox(row)
        self._quiz_presentation_combo.setObjectName("settings-quiz-presentation-combo")
        for value, label in QUIZ_PRESENTATION_LABELS.items():
            self._quiz_presentation_combo.addItem(label, value)
        self._quiz_presentation_combo.currentIndexChanged.connect(self._on_quiz_presentation_changed)
        row_layout.addWidget(self._quiz_presentation_combo, 0)

        root.addWidget(row)
        root.addStretch(1)

        controller.state_changed.connect(self._sync_from_controller)
        self._sync_from_controller()

    def _sync_from_controller(self) -> None:
        current = self._controller.quiz_presentation()
        index = self._quiz_presentation_combo.findData(current)
        if index >= 0 and self._quiz_presentation_combo.currentIndex() != index:
            self._quiz_presentation_combo.blockSignals(True)
            self._quiz_presentation_combo.setCurrentIndex(index)
            self._quiz_presentation_combo.blockSignals(False)

    def _on_quiz_presentation_changed(self, index: int) -> None:
        value = self._quiz_presentation_combo.itemData(index)
        if value is not None:
            self._controller.set_quiz_presentation(value)
