from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.ui_desktop.controllers.settings_controller import SettingsController
from src.ui_desktop.state.preferences import QUIZ_PRESENTATION_LABELS
from src.ui_desktop.theming.color_math import contrast_ratio, is_valid_hex, normalize_hex
from src.ui_desktop.theming.metrics import SPACING
from src.ui_desktop.theming.theme_manager import Appearance
from src.ui_desktop.theming.tokens import (
    PRESET_CALM_BLUE,
    PRESET_NAMES,
    ModeCustomization,
    build_resolved_theme_tokens,
)

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

        # -- Appearance & Global Mode ---------------------------------------
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

        # -- Theme Customization (Phase D) ----------------------------------
        theme_heading = QLabel("Theme Customization", body)
        theme_heading.setObjectName("settings-section-heading")
        root.addWidget(theme_heading)

        theme_note = QLabel(
            "Select presets and customize colors for Light and Dark modes independently. "
            "Switching tabs previews the mode in real time. Changes are only saved when you click Apply.",
            body,
        )
        theme_note.setObjectName("settings-section-note")
        theme_note.setWordWrap(True)
        root.addWidget(theme_note)

        self._theme_tabs = QTabWidget(body)
        self._theme_tabs.setObjectName("settings-theme-tabs")
        self._theme_tabs.tabBar().setObjectName("settings-theme-tabbar")

        self._preset_combos: dict[str, QComboBox] = {}
        self._accent_swatches: dict[str, QLabel] = {}
        self._bg_swatches: dict[str, QLabel] = {}
        self._surf_swatches: dict[str, QLabel] = {}
        self._text_swatches: dict[str, QLabel] = {}
        self._contrast_badges: dict[str, QLabel] = {}

        for mode in ("Light", "Dark"):
            tab_page = self._build_theme_mode_tab(mode)
            self._theme_tabs.addTab(tab_page, f"{mode} Mode")

        self._theme_tabs.currentChanged.connect(self._on_theme_tab_switched)
        root.addWidget(self._theme_tabs)

        # Theme Action Bar & Feedback
        action_bar = QWidget(body)
        action_bar.setObjectName("settings-theme-action-bar")
        action_bar_layout = QVBoxLayout(action_bar)
        action_bar_layout.setContentsMargins(0, SPACING.xs, 0, SPACING.sm)
        action_bar_layout.setSpacing(SPACING.xs)

        action_buttons_row = QHBoxLayout()
        action_buttons_row.setSpacing(SPACING.sm)

        self._theme_reset_mode_btn = QPushButton("Reset to Preset", action_bar)
        self._theme_reset_mode_btn.setObjectName("settings-theme-reset-btn")
        self._theme_reset_mode_btn.setToolTip("Clear custom colors for the currently active tab mode")
        self._theme_reset_mode_btn.clicked.connect(self._on_reset_mode)
        action_buttons_row.addWidget(self._theme_reset_mode_btn)

        self._theme_reset_all_btn = QPushButton("Reset All to Default", action_bar)
        self._theme_reset_all_btn.setObjectName("settings-theme-reset-btn")
        self._theme_reset_all_btn.setToolTip("Restore default Calm Blue preset for both Light and Dark modes")
        self._theme_reset_all_btn.clicked.connect(self._on_reset_all)
        action_buttons_row.addWidget(self._theme_reset_all_btn)

        action_buttons_row.addStretch(1)

        self._theme_undo_btn = QPushButton("Undo", action_bar)
        self._theme_undo_btn.setObjectName("settings-theme-undo-btn")
        self._theme_undo_btn.setToolTip("Undo the last applied or reset theme snapshot")
        self._theme_undo_btn.clicked.connect(self._on_undo)
        action_buttons_row.addWidget(self._theme_undo_btn)

        self._theme_cancel_btn = QPushButton("Cancel", action_bar)
        self._theme_cancel_btn.setObjectName("settings-theme-cancel-btn")
        self._theme_cancel_btn.setToolTip("Discard unstaged changes and exit live preview")
        self._theme_cancel_btn.clicked.connect(self._on_cancel)
        action_buttons_row.addWidget(self._theme_cancel_btn)

        self._theme_apply_btn = QPushButton("Apply", action_bar)
        self._theme_apply_btn.setObjectName("settings-theme-apply-btn")
        self._theme_apply_btn.setToolTip("Save theme changes to preferences")
        self._theme_apply_btn.clicked.connect(self._on_apply)
        action_buttons_row.addWidget(self._theme_apply_btn)

        action_bar_layout.addLayout(action_buttons_row)

        self._theme_feedback_label = QLabel("", action_bar)
        self._theme_feedback_label.setObjectName("settings-theme-feedback-label")
        action_bar_layout.addWidget(self._theme_feedback_label)

        root.addWidget(action_bar)

        # -- Quiz Section ---------------------------------------------------
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

        # -- Collections Section --------------------------------------------
        collections_heading = QLabel("Collections", body)
        collections_heading.setObjectName("settings-section-heading")
        root.addWidget(collections_heading)

        progress_row = QWidget(body)
        progress_row.setObjectName("settings-row")
        progress_row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        progress_row_layout = QHBoxLayout(progress_row)
        progress_row_layout.setContentsMargins(SPACING.md, SPACING.md, SPACING.md, SPACING.md)
        progress_row_layout.setSpacing(SPACING.md)

        progress_row_label = QLabel("Learning progress", progress_row)
        progress_row_label.setObjectName("settings-row-label")
        progress_row_layout.addWidget(progress_row_label, 0)
        progress_row_layout.addStretch(1)

        self._collection_progress_bars_checkbox = QCheckBox("Show progress bars", progress_row)
        self._collection_progress_bars_checkbox.setObjectName("settings-collection-progress-bars-checkbox")
        self._collection_progress_bars_checkbox.toggled.connect(
            self._controller.set_collection_progress_bars_visible
        )
        progress_row_layout.addWidget(self._collection_progress_bars_checkbox, 0)
        root.addWidget(progress_row)

        # -- Audio Section --------------------------------------------------
        audio_heading = QLabel("Audio", body)
        audio_heading.setObjectName("settings-section-heading")
        root.addWidget(audio_heading)

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

        for language, _display_name in VOICE_BINDING_LANGUAGES:
            self._populate_voice_combo_static(language)
            self._voice_combos[language].currentIndexChanged.connect(
                lambda _index, lang=language: self._on_voice_binding_changed(lang)
            )

        # -- Storage Section ------------------------------------------------
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

    # -- Theme Mode Tab Builder ---------------------------------------------

    def _build_theme_mode_tab(self, mode: str) -> QWidget:
        panel = QWidget(self)
        panel.setObjectName("settings-theme-tab-panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(SPACING.md, SPACING.md, SPACING.md, SPACING.md)
        layout.setSpacing(SPACING.sm)

        # Preset row
        preset_row = QWidget(panel)
        preset_row.setObjectName("settings-row")
        preset_row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        preset_layout = QHBoxLayout(preset_row)
        preset_layout.setContentsMargins(SPACING.md, SPACING.sm, SPACING.md, SPACING.sm)
        preset_layout.setSpacing(SPACING.md)

        preset_label = QLabel("Preset", preset_row)
        preset_label.setObjectName("settings-row-label")
        preset_layout.addWidget(preset_label, 0)
        preset_layout.addStretch(1)

        preset_combo = QComboBox(preset_row)
        preset_combo.setObjectName("settings-preset-combo")
        for preset_name in PRESET_NAMES:
            preset_combo.addItem(preset_name, preset_name)
        preset_combo.currentIndexChanged.connect(
            lambda _idx, m=mode: self._on_preset_selected(m)
        )
        preset_layout.addWidget(preset_combo, 0)
        self._preset_combos[mode] = preset_combo
        layout.addWidget(preset_row)

        # Accent Color row
        accent_row, accent_swatch = self._build_color_row(
            panel,
            label="Accent Color",
            mode=mode,
            field_name="accent_color",
            reset_text="Use Preset",
        )
        self._accent_swatches[mode] = accent_swatch
        layout.addWidget(accent_row)

        # App Background row
        bg_row, bg_swatch = self._build_color_row(
            panel,
            label="Background",
            mode=mode,
            field_name="background_color",
            reset_text="Use Preset",
        )
        self._bg_swatches[mode] = bg_swatch
        layout.addWidget(bg_row)

        # Surface Primary row
        surf_row, surf_swatch = self._build_color_row(
            panel,
            label="Surfaces",
            mode=mode,
            field_name="surface_color",
            reset_text="Use Preset",
        )
        self._surf_swatches[mode] = surf_swatch
        layout.addWidget(surf_row)

        # Text Color row
        text_row, text_swatch, contrast_badge = self._build_text_color_row(
            panel,
            label="Text",
            mode=mode,
        )
        self._text_swatches[mode] = text_swatch
        self._contrast_badges[mode] = contrast_badge
        layout.addWidget(text_row)

        return panel

    def _build_color_row(
        self,
        parent: QWidget,
        label: str,
        mode: str,
        field_name: str,
        reset_text: str,
    ) -> tuple[QWidget, QLabel]:
        row = QWidget(parent)
        row.setObjectName("settings-row")
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(SPACING.md, SPACING.xs, SPACING.md, SPACING.xs)
        row_layout.setSpacing(SPACING.md)

        row_label = QLabel(label, row)
        row_label.setObjectName("settings-row-label")
        row_layout.addWidget(row_label, 0)
        row_layout.addStretch(1)

        swatch = QLabel(row)
        swatch.setObjectName("settings-row-value")
        swatch.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row_layout.addWidget(swatch, 0)

        pick_btn = QPushButton("Pick...", row)
        pick_btn.setObjectName("settings-color-pick-btn")
        pick_btn.clicked.connect(lambda: self._on_pick_color(mode, field_name))
        row_layout.addWidget(pick_btn, 0)

        reset_btn = QPushButton(reset_text, row)
        reset_btn.setObjectName("settings-color-reset-btn")
        reset_btn.clicked.connect(lambda: self._on_clear_color(mode, field_name))
        row_layout.addWidget(reset_btn, 0)

        return row, swatch

    def _build_text_color_row(
        self,
        parent: QWidget,
        label: str,
        mode: str,
    ) -> tuple[QWidget, QLabel, QLabel]:
        row = QWidget(parent)
        row.setObjectName("settings-row")
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(SPACING.md, SPACING.xs, SPACING.md, SPACING.xs)
        row_layout.setSpacing(SPACING.md)

        row_label = QLabel(label, row)
        row_label.setObjectName("settings-row-label")
        row_layout.addWidget(row_label, 0)

        contrast_badge = QLabel("Contrast AA", row)
        contrast_badge.setObjectName("settings-contrast-badge")
        row_layout.addWidget(contrast_badge, 0)

        row_layout.addStretch(1)

        swatch = QLabel(row)
        swatch.setObjectName("settings-row-value")
        swatch.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row_layout.addWidget(swatch, 0)

        pick_btn = QPushButton("Pick...", row)
        pick_btn.setObjectName("settings-color-pick-btn")
        pick_btn.clicked.connect(lambda: self._on_pick_color(mode, "text_color"))
        row_layout.addWidget(pick_btn, 0)

        reset_btn = QPushButton("Auto Guard", row)
        reset_btn.setObjectName("settings-color-reset-btn")
        reset_btn.setToolTip("Automatically pick the highest-contrast readable text color")
        reset_btn.clicked.connect(lambda: self._on_clear_color(mode, "text_color"))
        row_layout.addWidget(reset_btn, 0)

        return row, swatch, contrast_badge

    # -- Theme Event Handlers -----------------------------------------------

    def _get_active_tab_mode(self) -> str:
        return "Dark" if self._theme_tabs.currentIndex() == 1 else "Light"

    def _on_theme_tab_switched(self, index: int) -> None:
        mode = "Dark" if index == 1 else "Light"
        self._controller.preview_tab_mode(mode)

    def _on_preset_selected(self, mode: str) -> None:
        combo = self._preset_combos[mode]
        preset_name = combo.currentData() or PRESET_CALM_BLUE
        staged = self._controller.staged_custom_theme()
        current_custom = staged.dark if mode.lower() == "dark" else staged.light
        if current_custom.preset != preset_name:
            new_custom = ModeCustomization(
                preset=preset_name,
                accent_color=current_custom.accent_color,
                background_color=current_custom.background_color,
                surface_color=current_custom.surface_color,
                text_color=current_custom.text_color,
            )
            self._controller.stage_mode_customization(mode, new_custom)

    def _on_pick_color(self, mode: str, field_name: str) -> None:
        import copy
        staged = self._controller.staged_custom_theme()
        custom = staged.dark if mode.lower() == "dark" else staged.light
        current_hex = getattr(custom, field_name) or "#3E6690"
        initial_qcolor = QColor(current_hex)
        pre_pick_custom = copy.deepcopy(custom)

        dialog = QColorDialog(initial_qcolor, self)
        dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, False)

        def _on_live_picker_color_changed(color: QColor) -> None:
            if color.isValid():
                hex_val = color.name().upper()
                preview_custom = ModeCustomization(
                    preset=pre_pick_custom.preset,
                    accent_color=hex_val if field_name == "accent_color" else pre_pick_custom.accent_color,
                    background_color=hex_val if field_name == "background_color" else pre_pick_custom.background_color,
                    surface_color=hex_val if field_name == "surface_color" else pre_pick_custom.surface_color,
                    text_color=hex_val if field_name == "text_color" else pre_pick_custom.text_color,
                )
                self._controller.stage_mode_customization(mode, preview_custom)

        dialog.currentColorChanged.connect(_on_live_picker_color_changed)

        if dialog.exec():
            selected = dialog.selectedColor()
            if selected.isValid():
                hex_val = selected.name().upper()
                final_custom = ModeCustomization(
                    preset=pre_pick_custom.preset,
                    accent_color=hex_val if field_name == "accent_color" else pre_pick_custom.accent_color,
                    background_color=hex_val if field_name == "background_color" else pre_pick_custom.background_color,
                    surface_color=hex_val if field_name == "surface_color" else pre_pick_custom.surface_color,
                    text_color=hex_val if field_name == "text_color" else pre_pick_custom.text_color,
                )
                self._controller.stage_mode_customization(mode, final_custom)
                self._set_theme_feedback(f"Selected {field_name.replace('_', ' ')}: {hex_val}")
        else:
            # Revert preview back to pre-picker state
            self._controller.stage_mode_customization(mode, pre_pick_custom)

    def _on_clear_color(self, mode: str, field_name: str) -> None:
        staged = self._controller.staged_custom_theme()
        custom = staged.dark if mode.lower() == "dark" else staged.light
        new_custom = ModeCustomization(
            preset=custom.preset,
            accent_color=None if field_name == "accent_color" else custom.accent_color,
            background_color=None if field_name == "background_color" else custom.background_color,
            surface_color=None if field_name == "surface_color" else custom.surface_color,
            text_color=None if field_name == "text_color" else custom.text_color,
        )
        self._controller.stage_mode_customization(mode, new_custom)
        self._set_theme_feedback(f"Reset {field_name.replace('_', ' ')} to preset default.")

    def _on_reset_mode(self) -> None:
        mode = self._get_active_tab_mode()
        combo = self._preset_combos[mode]
        current_preset = combo.currentData() or PRESET_CALM_BLUE
        self._controller.reset_staged_mode_to_preset(mode, current_preset)
        self._set_theme_feedback(f"Reset {mode} Mode to {current_preset} preset. Click Undo to revert.")

    def _on_reset_all(self) -> None:
        active_mode = self._get_active_tab_mode()
        self._controller.reset_staged_all_to_default(active_mode)
        self._set_theme_feedback("Reset all modes to default Calm Blue. Click Undo to revert.")

    def _on_undo(self) -> None:
        self._controller.undo()
        self._set_theme_feedback("Restored previous theme snapshot.")

    def _on_cancel(self) -> None:
        self._controller.cancel_staged_custom_theme()
        self._set_theme_feedback("Cancelled unstaged changes.")

    def _on_apply(self) -> None:
        self._controller.apply_staged_custom_theme()
        self._set_theme_feedback("Theme changes applied. Click Undo to revert.")

    def _set_theme_feedback(self, message: str) -> None:
        self._theme_feedback_label.setText(message)

    # -- General Helpers & Sync ---------------------------------------------

    def _build_info_row(self, label_text: str, value: str) -> QWidget:
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

        # -- Sync Theme Customization Controls --
        staged = self._controller.staged_custom_theme()
        for mode in ("Light", "Dark"):
            custom = staged.dark if mode == "Dark" else staged.light
            tokens = build_resolved_theme_tokens(mode, custom)

            # Sync preset combo
            combo = self._preset_combos[mode]
            preset_idx = combo.findData(custom.preset)
            if preset_idx >= 0 and combo.currentIndex() != preset_idx:
                combo.blockSignals(True)
                combo.setCurrentIndex(preset_idx)
                combo.blockSignals(False)

            # Sync swatches
            accent_val = custom.accent_color or f"{tokens.accent.primary.background} (Preset)"
            self._accent_swatches[mode].setText(f"■  {accent_val}")

            bg_val = custom.background_color or f"{tokens.neutral.app_background} (Preset)"
            self._bg_swatches[mode].setText(f"■  {bg_val}")

            surf_val = custom.surface_color or f"{tokens.neutral.surface_primary} (Preset)"
            self._surf_swatches[mode].setText(f"■  {surf_val}")

            text_val = custom.text_color or f"{tokens.neutral.text_primary} (Auto)"
            self._text_swatches[mode].setText(f"■  {text_val}")

            # Calculate and display WCAG contrast badge
            cr = contrast_ratio(tokens.neutral.surface_primary, tokens.neutral.text_primary)
            if cr >= 7.0:
                self._contrast_badges[mode].setText(f"Contrast {cr:.1f}:1  (AAA)")
            elif cr >= 4.5:
                self._contrast_badges[mode].setText(f"Contrast {cr:.1f}:1  (AA)")
            else:
                self._contrast_badges[mode].setText(f"Contrast {cr:.1f}:1  (Low)")

        # Sync Action Bar Button States
        is_dirty = self._controller.is_staged_dirty()
        self._theme_apply_btn.setEnabled(is_dirty)
        self._theme_cancel_btn.setEnabled(is_dirty)
        self._theme_undo_btn.setEnabled(self._controller.can_undo())

    def _on_appearance_changed(self, index: int) -> None:
        value = self._appearance_combo.itemData(index)
        if value is not None:
            self._controller.set_appearance(value)

    def _on_quiz_presentation_changed(self, index: int) -> None:
        value = self._quiz_presentation_combo.itemData(index)
        if value is not None:
            self._controller.set_quiz_presentation(value)
