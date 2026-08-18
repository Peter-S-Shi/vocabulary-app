from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.ui_desktop.controllers.settings_controller import SettingsController
from src.ui_desktop.state.preferences import QUIZ_PRESENTATION_LABELS
from src.ui_desktop.theming.metrics import SPACING
from src.ui_desktop.theming.theme_manager import Appearance

"""
Settings -- Management Mode, P8 Settings Form (DESIGN.md § 8: "Management
Rail + categorized settings structure + comfortable form density. Settings
is not a dashboard..."). M17 Feature 3B built the minimum bounded vertical
slice that checkpoint's real preference needed -- Quiz presentation. M17
Theme Completion adds the second real preference this pattern was always
meant to hold: Appearance (DESIGN.md § 14 "Settings -> Appearance -- full
authoritative configuration surface"). Accent/Motion/language/storage/
backup/audio/privacy/database settings remain explicitly out of scope
(M17 Theme Completion prompt § 4's deferred-accent-family boundary) and
continue working exactly as they do today.

Design -> Implementation trace:

  shell/chrome        -> ordinary Management Mode workspace, reached
                          through the Management Rail like Today/Entries --
                          no Study-mode chrome swap, no transient
                          drawer/dialog.
  page structure       -> page title + one category heading per preference
                          group ("Appearance", "Quiz") + one settings row
                          each, per P8's "categorized settings structure"
                          formula.
  Appearance row        -> label + native QComboBox of System/Light/Dark
                          (DESIGN.md § 13.1); the ONE control this
                          checkpoint adds -- no separate Quick Theme
                          Control popover (DESIGN.md § 14's other access
                          level) is in scope here (M17 Theme Completion
                          prompt § 4/§ 21).
  Quiz presentation row -> label + native QComboBox showing the current
                          value; VR-STUDY-002 prompt § 6/§ 7: this is the
                          ONE control location for this preference -- no
                          second selector exists anywhere else (Review,
                          Choose Quiz Type, Quiz session bar, completion).
  persistence           -> SettingsController.set_appearance()/
                          set_quiz_presentation() write straight through to
                          the existing state/preferences.py file.
                          set_appearance() additionally re-applies the
                          live ThemeManager synchronously (M17 Theme
                          Completion prompt § 5: no restart required); the
                          next Quiz launched in this session (M17 Feature
                          3B prompt § 7) or after a restart (§ 5) uses the
                          saved presentation value.

M18 Phase C2 adds the third category this pattern was always meant to
hold: read-only "Storage" (DESIGN.md § 7.3 "Storage / data-location
information: B, P8") -- database/backup/audio-cache paths and path
source, read straight from `src.app_config.get_app_storage_summary()`
(the same function the Streamlit Settings/Data page already reads) via
`SettingsController.storage_summary()`. Each row reuses the existing
`settings-row`/`settings-row-label` grammar with a plain value label
instead of an editable control -- purely informational, never a second
path-resolution/configuration surface.

Human Gate 2 corrective (layout regression): native testing found the
Appearance/Quiz presentation combos horizontally compressed/clipped at a
normal desktop window size. `QComboBox`'s horizontal size policy permits
shrinking below its own size hint (not just growing), so once the page's
total layout demand exceeded the available width it was squeezed toward
whatever floor its QSS `min-width` declared. Tried protecting the two
combos directly in Python (`QSizePolicy`, explicit `setMinimumWidth`)
first, but confirmed empirically that an active stylesheet's `min-width`
is what Qt's layout actually honors as the floor under squeeze -- those
Python-side calls had no measurable effect and were removed rather than
left as misleading dead code. The real fix is in `theme_manager.py`:
raising `min-width` on `#settings-appearance-combo`/
`#settings-quiz-presentation-combo` measurably raises that floor even
when the row is squeezed (confirmed: floor moved from 222px to 322px in
a width sweep), keeping the selected value comfortably readable.
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

        appearance_heading = QLabel("Appearance", self)
        appearance_heading.setObjectName("settings-section-heading")
        root.addWidget(appearance_heading)

        appearance_row = QWidget(self)
        appearance_row.setObjectName("settings-row")
        appearance_row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        appearance_row_layout = QHBoxLayout(appearance_row)
        appearance_row_layout.setContentsMargins(SPACING.md, SPACING.md, SPACING.md, SPACING.md)
        appearance_row_layout.setSpacing(SPACING.md)

        appearance_row_label = QLabel("Appearance", appearance_row)
        appearance_row_label.setObjectName("settings-row-label")
        appearance_row_layout.addWidget(appearance_row_label, 0)
        appearance_row_layout.addStretch(1)

        self._appearance_combo = QComboBox(appearance_row)
        self._appearance_combo.setObjectName("settings-appearance-combo")
        for appearance in Appearance:
            self._appearance_combo.addItem(appearance.value, appearance.value)
        self._appearance_combo.currentIndexChanged.connect(self._on_appearance_changed)
        appearance_row_layout.addWidget(self._appearance_combo, 0)

        root.addWidget(appearance_row)

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

        storage_heading = QLabel("Storage", self)
        storage_heading.setObjectName("settings-section-heading")
        root.addWidget(storage_heading)

        storage = controller.storage_summary()
        for label_text, value in (
            ("App version", str(storage["app_version"])),
            ("Database path", str(storage["database_path"])),
            ("Database file exists", "Yes" if storage["database_exists"] else "No"),
            ("Data directory", str(storage["data_directory"])),
            ("Backup directory", str(storage["backup_directory"])),
            ("Audio cache directory", str(storage["audio_cache_directory"])),
            ("Path source", str(storage["path_source"])),
        ):
            root.addWidget(self._build_info_row(label_text, value))

        root.addStretch(1)

        controller.state_changed.connect(self._sync_from_controller)
        self._sync_from_controller()

    def _build_info_row(self, label_text: str, value: str) -> QWidget:
        """A read-only P8 settings row (DESIGN.md § 7.3 "Storage /
        data-location information: B, P8"): reuses the exact
        `settings-row`/`settings-row-label` grammar the Appearance/Quiz
        rows already established, with a plain value label in place of an
        editable control -- storage/data-location information is
        informational, not configurable, from this surface."""
        row = QWidget(self)
        row.setObjectName("settings-row")
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(SPACING.md, SPACING.md, SPACING.md, SPACING.md)
        layout.setSpacing(SPACING.md)

        label = QLabel(label_text, row)
        label.setObjectName("settings-row-label")
        layout.addWidget(label, 0)
        layout.addStretch(1)

        value_label = QLabel(value, row)
        value_label.setObjectName("settings-row-value")
        value_label.setWordWrap(True)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(value_label, 1)

        return row

    def _sync_from_controller(self) -> None:
        current_appearance = self._controller.appearance()
        appearance_index = self._appearance_combo.findData(current_appearance)
        if appearance_index >= 0 and self._appearance_combo.currentIndex() != appearance_index:
            self._appearance_combo.blockSignals(True)
            self._appearance_combo.setCurrentIndex(appearance_index)
            self._appearance_combo.blockSignals(False)

        current = self._controller.quiz_presentation()
        index = self._quiz_presentation_combo.findData(current)
        if index >= 0 and self._quiz_presentation_combo.currentIndex() != index:
            self._quiz_presentation_combo.blockSignals(True)
            self._quiz_presentation_combo.setCurrentIndex(index)
            self._quiz_presentation_combo.blockSignals(False)

    def _on_appearance_changed(self, index: int) -> None:
        value = self._appearance_combo.itemData(index)
        if value is not None:
            self._controller.set_appearance(value)

    def _on_quiz_presentation_changed(self, index: int) -> None:
        value = self._quiz_presentation_combo.itemData(index)
        if value is not None:
            self._controller.set_quiz_presentation(value)
