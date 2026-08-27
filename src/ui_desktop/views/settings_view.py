from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.ui_desktop.controllers.settings_controller import SettingsController
from src.ui_desktop.state.preferences import QUIZ_PRESENTATION_LABELS
from src.ui_desktop.theming.metrics import SPACING
from src.ui_desktop.theming.theme_manager import Appearance

# M20 Local Windows Speech Provider / Installed Voice Binding (Release
# Contract § 7.3): the frozen v1.0 language scope, in the fixed display
# order Settings > Audio always shows it. Discovering other installed
# Windows voices never expands this set.
VOICE_BINDING_LANGUAGES: tuple[tuple[str, str], ...] = (
    ("en", "English"),
    ("fr", "French"),
    ("zh-CN", "Mandarin (zh-CN)"),
)
NOT_BOUND_VOICE_ID = ""

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
normal desktop window size. A first corrective pass raised the two
combos' QSS `min-width` (200px -> 300px), which measurably helped but
was a per-control workaround: it protected two specific combos without
addressing that the page as a whole has no vertical scroll area, so it
cannot grow taller than the available window -- any future growth of
the Settings/Storage content (M18 Phase C2 already added seven rows)
just re-creates the same squeeze somewhere else. Reverted that min-width
bump and wrapped the page's content in a native vertical `QScrollArea`
(`setWidgetResizable(True)`, horizontal scrolling disabled) instead: the
page can now grow taller through scrolling rather than by compressing
its controls, the body's width still tracks the available desktop width
responsively, and the Appearance/Quiz controls render at their natural,
comfortable size.
"""


class SettingsView(QWidget):
    def __init__(self, controller: SettingsController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("settings-root")
        self._controller = controller

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setObjectName("settings-scroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        outer.addWidget(scroll)

        body = QWidget(scroll)
        scroll.setWidget(body)

        root = QVBoxLayout(body)
        root.setContentsMargins(SPACING.xl, SPACING.xl, SPACING.xl, SPACING.xl)
        root.setSpacing(SPACING.lg)
        root.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("Settings", body)
        title.setObjectName("settings-page-title")
        root.addWidget(title)

        appearance_heading = QLabel("Appearance", body)
        appearance_heading.setObjectName("settings-section-heading")
        root.addWidget(appearance_heading)

        appearance_row = QWidget(body)
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

        quiz_heading = QLabel("Quiz", body)
        quiz_heading.setObjectName("settings-section-heading")
        root.addWidget(quiz_heading)

        row = QWidget(body)
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

        collections_heading = QLabel("Collections", body)
        collections_heading.setObjectName("settings-collections-heading")
        root.addWidget(collections_heading)

        progress_row = QWidget(body)
        progress_row.setObjectName("settings-row")
        progress_row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        progress_row_layout = QHBoxLayout(progress_row)
        progress_row_layout.setContentsMargins(SPACING.md, SPACING.md, SPACING.md, SPACING.md)
        progress_row_layout.setSpacing(SPACING.md)

        progress_row_label = QLabel("Learning progress", progress_row)
        progress_row_label.setObjectName("settings-collection-progress-label")
        progress_row_layout.addWidget(progress_row_label, 0)
        progress_row_layout.addStretch(1)

        self._collection_progress_bars_checkbox = QCheckBox("Show progress bars", progress_row)
        self._collection_progress_bars_checkbox.setObjectName("settings-collection-progress-bars-checkbox")
        self._collection_progress_bars_checkbox.toggled.connect(
            self._controller.set_collection_progress_bars_visible
        )
        progress_row_layout.addWidget(self._collection_progress_bars_checkbox, 0)
        root.addWidget(progress_row)

        audio_heading = QLabel("Audio", body)
        audio_heading.setObjectName("settings-section-heading")
        root.addWidget(audio_heading)

        # M20 Local Windows Speech Provider / Installed Voice Binding
        # (Release Contract § 2.3, § 7): Vocabulary App never bundles or
        # downloads a voice. A normal user binds an already-installed
        # Windows voice per language here; the environment variable
        # remains an advanced per-process override surfaced honestly in
        # each row's status text (state/tts_runtime.py resolution order).
        audio_note = QLabel(
            "Card Audio Export speaks using a voice already installed on this "
            "Windows system -- nothing is downloaded. Bind one per language below.",
            body,
        )
        audio_note.setObjectName("settings-section-note")
        audio_note.setWordWrap(True)
        root.addWidget(audio_note)

        refresh_row = QHBoxLayout()
        refresh_row.addStretch(1)
        self._voice_refresh_button = QPushButton("Refresh Voices", body)
        self._voice_refresh_button.setObjectName("settings-voice-refresh-button")
        self._voice_refresh_button.clicked.connect(self._on_voice_refresh)
        refresh_row.addWidget(self._voice_refresh_button)
        root.addLayout(refresh_row)

        self._voice_combos: dict[str, QComboBox] = {}
        self._voice_status_labels: dict[str, QLabel] = {}

        for language, display_name in VOICE_BINDING_LANGUAGES:
            voice_row = QWidget(body)
            voice_row.setObjectName("settings-row")
            voice_row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            voice_row_layout = QHBoxLayout(voice_row)
            voice_row_layout.setContentsMargins(SPACING.md, SPACING.md, SPACING.md, SPACING.md)
            voice_row_layout.setSpacing(SPACING.md)

            voice_row_label = QLabel(display_name, voice_row)
            voice_row_label.setObjectName("settings-row-label")
            voice_row_layout.addWidget(voice_row_label, 0)
            voice_row_layout.addStretch(1)

            combo = QComboBox(voice_row)
            combo.setObjectName("settings-voice-binding-combo")
            voice_row_layout.addWidget(combo, 0)
            self._voice_combos[language] = combo

            root.addWidget(voice_row)

            status_label = QLabel("", body)
            status_label.setObjectName("settings-section-note")
            status_label.setWordWrap(True)
            root.addWidget(status_label)
            self._voice_status_labels[language] = status_label

            # Connected after population below, so the initial
            # population doesn't fire a spurious "user changed this"
            # write.

        for language, _display_name in VOICE_BINDING_LANGUAGES:
            # Static population only (no PowerShell/WinRT call) --
            # opening Settings must never block the UI thread on a real
            # enumeration, the exact freeze the M19 Audio Export
            # corrective fixed for Card Audio Export. Real installed
            # voices only load when the user clicks "Refresh Voices".
            self._populate_voice_combo_static(language)
            self._voice_combos[language].currentIndexChanged.connect(
                lambda _index, lang=language: self._on_voice_binding_changed(lang)
            )

        storage_heading = QLabel("Storage", body)
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

    def _populate_voice_combo_static(self, language: str) -> None:
        """Cheap, no-subprocess-call population: "Not bound" plus (if a
        binding already exists) a placeholder item for it. Opening
        Settings must never block the UI thread on a real PowerShell/
        WinRT enumeration -- see the class-construction comment above."""
        combo = self._voice_combos[language]
        bound_voice_id = self._controller.voice_binding(language)

        combo.blockSignals(True)
        combo.clear()
        combo.addItem("Not bound", NOT_BOUND_VOICE_ID)
        if bound_voice_id:
            combo.addItem(f"{bound_voice_id} (click Refresh Voices for its name)", bound_voice_id)
        index = combo.findData(bound_voice_id)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

        self._update_voice_status_label(language)

    def _reload_voice_combo(self, language: str, installed: list | None = None) -> None:
        """Repopulates ``language``'s combo with real installed voices.
        ``installed`` lets a caller that already enumerated once (e.g.
        "Refresh Voices", across all languages) avoid repeating the
        PowerShell/WinRT call per language; a standalone caller may omit
        it to enumerate just this language."""
        combo = self._voice_combos[language]
        bound_voice_id = self._controller.voice_binding(language)
        voices = installed if installed is not None else self._controller.installed_voices(language)

        combo.blockSignals(True)
        combo.clear()
        combo.addItem("Not bound", NOT_BOUND_VOICE_ID)
        known_ids = {NOT_BOUND_VOICE_ID}
        for voice in voices:
            combo.addItem(voice.display_name, voice.voice_id)
            known_ids.add(voice.voice_id)
        if bound_voice_id and bound_voice_id not in known_ids:
            combo.addItem(f"{bound_voice_id} (not installed)", bound_voice_id)

        index = combo.findData(bound_voice_id)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

        self._update_voice_status_label(language)

    def _update_voice_status_label(self, language: str) -> None:
        status = self._controller.voice_binding_status(language)
        label = self._voice_status_labels[language]
        if status["voice_id"]:
            label.setText(f'{status["voice_id"]} — {status["source_label"]}')
        else:
            label.setText(status["source_label"])

    def _on_voice_binding_changed(self, language: str) -> None:
        combo = self._voice_combos[language]
        voice_id = combo.currentData()
        self._controller.set_voice_binding(language, voice_id or "")

    def _on_voice_refresh(self) -> None:
        all_voices = self._controller.all_installed_voices()
        for language, _display_name in VOICE_BINDING_LANGUAGES:
            matching = [voice for voice in all_voices if voice.canonical_language == language]
            self._reload_voice_combo(language, matching)

    def _sync_from_controller(self) -> None:
        progress_bars_visible = self._controller.collection_progress_bars_visible()
        if self._collection_progress_bars_checkbox.isChecked() != progress_bars_visible:
            self._collection_progress_bars_checkbox.blockSignals(True)
            self._collection_progress_bars_checkbox.setChecked(progress_bars_visible)
            self._collection_progress_bars_checkbox.blockSignals(False)

        for language, _display_name in VOICE_BINDING_LANGUAGES:
            combo = self._voice_combos[language]
            bound_voice_id = self._controller.voice_binding(language)
            index = combo.findData(bound_voice_id)
            if index < 0 and bound_voice_id:
                # A binding exists that this combo's current item list
                # doesn't know about yet (e.g. changed without a
                # "Refresh Voices" reload since). Add a cheap
                # placeholder rather than re-populating the whole combo
                # -- that would discard any real enumerated names
                # "Refresh Voices" already loaded.
                combo.blockSignals(True)
                combo.addItem(f"{bound_voice_id} (click Refresh Voices for its name)", bound_voice_id)
                combo.blockSignals(False)
                index = combo.findData(bound_voice_id)
            if index >= 0 and combo.currentIndex() != index:
                combo.blockSignals(True)
                combo.setCurrentIndex(index)
                combo.blockSignals(False)
            self._update_voice_status_label(language)

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
