from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.audio_export import CONFLICT_OVERWRITE, SCOPE_SELECTED_CARDS, SCOPE_SINGLE_CARD
from src.ui_desktop.controllers.audio_export_controller import (
    CONFLICT_LABELS,
    REPETITION_MODE_LABELS,
    SCOPE_LABELS,
    AudioExportController,
)
from src.ui_desktop.theming.metrics import SPACING

"""
Card Audio Export (DESIGN.md § 7.4 "Audio Export configuration: B,
VR-UTILITY-001"; § 4.3 Utility/Dialog context: "belongs to and returns
to its parent workflow"; § 12.5 "For Card Audio Export preserve
M15.3"). Design Derivation Record per § 9 (VR-UTILITY-001 is a PATTERN
board, following the same textual-grammar resolution `_BackupRestoreDialog`
and `_ImportDialog`/`_ExportDialog` already used for the Data Tools hub's
other P6 workflows, § 12):

  1. Interaction Mode        -> Utility/Dialog launched from Management
                                 (Data Tools hub), same family as Import/
                                 Export/Backup.
  2. Parent Pattern          -> P6 Utility Workflow. Scope/voice/
                                 repetition/destination configuration ->
                                 Build Plan (a read-only preview of what
                                 will be produced, matching § 12.3's
                                 preview-before-commit grammar) -> explicit
                                 consent -> Start Export -> progress/cancel
                                 -> partial-success result -> optional
                                 Retry, never collapsing configuration and
                                 synthesis into one opaque action.
  3. Primary User Task       -> synthesize and publish one audio file per
                                 current Card, for a single Card, an
                                 explicit multi-Card selection, or an
                                 entire Collection.
  4. Spatial Composition     -> Data Tools hub gains a fourth action
                                 ("Audio Export…") opening this dialog,
                                 which stacks top to bottom: Collection +
                                 scope + Card selection -> read-only Voice
                                 Assignment panel -> repetition + conflict
                                 configuration -> destination folder ->
                                 Build Plan -> plan summary/table -> consent
                                 + Start Export -> progress/cancel -> result
                                 table -> optional Retry -> Close.
  5. Dominance Rule          -> the current step's controls/results
                                 dominate; earlier steps stay visible above,
                                 never hidden -- plan and result are always
                                 distinguishable (§ 12.3).
  6. Density Rule            -> inherits Management Mode density, matching
                                 every other M18 P6 dialog's tables.
  7. Surface Hierarchy       -> inherits the Data Tools/Backup dialog
                                 surface treatment verbatim (no new
                                 hierarchy invented for this surface).
  8. Action Hierarchy        -> primary = Build Plan / Start Export
                                 (accent-primary, bottom-right, § 12.1);
                                 Cancel is available only while a run is
                                 in flight and uses the same neutral-
                                 outlined treatment as every other
                                 secondary action here (never accent-
                                 primary -- stopping work is not the
                                 encouraged default); Close is always
                                 present and disabled only while a run is
                                 actually in flight, per § 12.2's
                                 "Cancel/Back predictable and easy to
                                 find" applied to the dialog's own exit.
  9. Editing Container       -> one P6 independent focused QDialog
                                 (matches `_BackupRestoreDialog`'s size
                                 class), not inline hub controls -- Card
                                 Audio Export is a genuinely multi-step
                                 configuration + long-running task.
 10. Navigation/Chrome       -> unchanged Management shell behind the hub;
                                 this dialog is a modal overlay.
 11. Motion/Transition       -> unchanged; no new motion.
 12. Canonical Visual Rel.   -> inherits `_BackupRestoreDialog`'s P6
                                 grammar (scrollable body, pinned action
                                 footer) plus Analytics' progress/error
                                 treatment (§ 12.4, `analytics-progress-bar`
                                 precedent) for the long-running step; no
                                 canonical VR-UTILITY-001 pixel mockup is
                                 required since it is a PATTERN board (§ 7.1).
 13. Native Human Acceptance -> the real native Data Tools hub, a real
                                 Collection/Card batch actually producing
                                 readable per-Card WAV files on disk, a
                                 cancelled run leaving completed files
                                 intact, and a Retry recovering the
                                 remainder, in Light and Dark Mode.

Voice configuration is deliberately READ-ONLY (module docstring of
``AudioExportController``): M15 froze provider/language routing, so this
view never offers a voice picker, only a confirmation of which frozen
voice each supported language uses.

This view owns no `src.audio_export`/`src.tts_providers` calls directly
-- every plan/execute/retry/voice-lookup goes through
``AudioExportController``, matching every other M18 P6 view's "no SQL,
no second engine" discipline.
"""


STATUS_LABELS = {
    "succeeded": "Succeeded",
    "skipped": "Skipped (already exists)",
    "failed": "Failed",
    "unresolved": "Unresolved",
    "cancelled": "Cancelled",
}


class AudioExportDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("audio-export-dialog")
        self.setWindowTitle("Card Audio Export")
        self.setMinimumSize(680, 680)
        self._controller = AudioExportController()

        outer = QVBoxLayout(self)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget(scroll)
        layout = QVBoxLayout(body)
        layout.setSpacing(SPACING.md)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        caption = QLabel(
            "Synthesize one audio file per current Card. Frozen voices "
            "(DESIGN.md § 5) are used automatically per language.",
            self,
        )
        caption.setObjectName("audio-export-caption")
        caption.setWordWrap(True)
        layout.addWidget(caption)

        # -- Collection / scope / Card selection -------------------------
        scope_form = QFormLayout()
        self._collection_combo = QComboBox(self)
        self._collection_combo.currentIndexChanged.connect(self._on_collection_changed)
        scope_form.addRow("Collection", self._collection_combo)

        self._scope_combo = QComboBox(self)
        for value, label in SCOPE_LABELS:
            self._scope_combo.addItem(label, value)
        self._scope_combo.currentIndexChanged.connect(self._on_scope_changed)
        scope_form.addRow("Scope", self._scope_combo)
        layout.addLayout(scope_form)

        self._single_card_combo = QComboBox(self)
        self._single_card_combo.currentIndexChanged.connect(self._on_single_card_changed)
        layout.addWidget(self._single_card_combo)

        self._card_list = QListWidget(self)
        self._card_list.setObjectName("audio-export-card-list")
        self._card_list.setMaximumHeight(160)
        self._card_list.itemChanged.connect(self._on_card_item_changed)
        layout.addWidget(self._card_list)

        # -- Voice assignment (read-only) ---------------------------------
        voice_heading = QLabel("Voice Assignment (frozen)", self)
        voice_heading.setObjectName("audio-export-section-heading")
        layout.addWidget(voice_heading)
        self._voice_table = QTableWidget(self)
        self._voice_table.setObjectName("audio-export-voice-table")
        self._voice_table.setColumnCount(3)
        self._voice_table.setHorizontalHeaderLabels(["Language", "Provider", "Voice"])
        self._voice_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._voice_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._voice_table.verticalHeader().setVisible(False)
        self._voice_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._voice_table.setMaximumHeight(120)
        layout.addWidget(self._voice_table)

        # -- Repetition / conflict configuration --------------------------
        config_form = QFormLayout()
        self._repetition_mode_combo = QComboBox(self)
        for value, label in REPETITION_MODE_LABELS:
            self._repetition_mode_combo.addItem(label, value)
        self._repetition_mode_combo.currentIndexChanged.connect(self._on_repetition_mode_changed)
        config_form.addRow("Repetition mode", self._repetition_mode_combo)

        self._repetition_count_input = QSpinBox(self)
        self._repetition_count_input.setRange(1, 20)
        self._repetition_count_input.setValue(1)
        self._repetition_count_input.valueChanged.connect(self._controller.set_repetition_count)
        config_form.addRow("Repetition count", self._repetition_count_input)

        self._conflict_combo = QComboBox(self)
        for value, label in CONFLICT_LABELS:
            self._conflict_combo.addItem(label, value)
        self._conflict_combo.currentIndexChanged.connect(self._on_conflict_changed)
        config_form.addRow("If a file already exists", self._conflict_combo)
        layout.addLayout(config_form)

        dest_row = QHBoxLayout()
        self._destination_label = QLabel("No destination folder selected.", self)
        dest_row.addWidget(self._destination_label, 1)
        choose_folder_button = QPushButton("Choose Folder…", self)
        choose_folder_button.setObjectName("audio-export-choose-folder-button")
        choose_folder_button.clicked.connect(self._on_choose_folder)
        dest_row.addWidget(choose_folder_button, 0)
        layout.addLayout(dest_row)

        # -- Build Plan ----------------------------------------------------
        plan_row = QHBoxLayout()
        plan_row.addStretch(1)
        self._build_plan_button = QPushButton("Build Plan", self)
        self._build_plan_button.setObjectName("audio-export-build-plan-button")
        self._build_plan_button.clicked.connect(self._on_build_plan)
        plan_row.addWidget(self._build_plan_button)
        layout.addLayout(plan_row)

        self._plan_error_label = QLabel("", self)
        self._plan_error_label.setObjectName("audio-export-plan-error")
        self._plan_error_label.setWordWrap(True)
        layout.addWidget(self._plan_error_label)

        self._plan_summary_label = QLabel("", self)
        self._plan_summary_label.setObjectName("audio-export-summary-label")
        self._plan_summary_label.setWordWrap(True)
        layout.addWidget(self._plan_summary_label)

        # -- Consent + Start Export -----------------------------------------
        self._consent_checkbox = QCheckBox("", self)
        self._consent_checkbox.toggled.connect(self._update_start_enabled)
        layout.addWidget(self._consent_checkbox)

        start_row = QHBoxLayout()
        start_row.addStretch(1)
        self._start_button = QPushButton("Start Export", self)
        self._start_button.setObjectName("audio-export-start-button")
        self._start_button.setEnabled(False)
        self._start_button.clicked.connect(self._on_start)
        start_row.addWidget(self._start_button)
        layout.addLayout(start_row)

        # -- Progress -------------------------------------------------------
        self._progress_bar = QProgressBar(self)
        self._progress_bar.setObjectName("audio-export-progress-bar")
        self._progress_bar.setRange(0, 1)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        self._status_label = QLabel("", self)
        self._status_label.setObjectName("audio-export-status-label")
        layout.addWidget(self._status_label)

        cancel_row = QHBoxLayout()
        cancel_row.addStretch(1)
        self._cancel_button = QPushButton("Cancel", self)
        self._cancel_button.setObjectName("audio-export-cancel-button")
        self._cancel_button.setVisible(False)
        self._cancel_button.clicked.connect(self._controller.cancel)
        cancel_row.addWidget(self._cancel_button)
        layout.addLayout(cancel_row)

        # -- Result -----------------------------------------------------------
        result_heading = QLabel("Result", self)
        result_heading.setObjectName("audio-export-section-heading")
        layout.addWidget(result_heading)
        self._result_summary_label = QLabel("", self)
        self._result_summary_label.setObjectName("audio-export-summary-label")
        self._result_summary_label.setWordWrap(True)
        layout.addWidget(self._result_summary_label)

        self._result_table = QTableWidget(self)
        self._result_table.setObjectName("audio-export-result-table")
        self._result_table.setColumnCount(4)
        self._result_table.setHorizontalHeaderLabels(["Card", "Name", "Status", "Detail"])
        self._result_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._result_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._result_table.verticalHeader().setVisible(False)
        self._result_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._result_table.setMaximumHeight(220)
        layout.addWidget(self._result_table)

        retry_row = QHBoxLayout()
        retry_row.addStretch(1)
        self._retry_button = QPushButton("Retry Failed / Unresolved / Cancelled", self)
        self._retry_button.setObjectName("audio-export-retry-button")
        self._retry_button.setVisible(False)
        self._retry_button.clicked.connect(self._on_retry)
        retry_row.addWidget(self._retry_button)
        layout.addLayout(retry_row)

        layout.addStretch(1)

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        self._close_button = QPushButton("Close", self)
        close_button = self._close_button
        close_button.clicked.connect(self.close)
        close_row.addWidget(close_button)
        outer.addLayout(close_row)

        controller = self._controller
        controller.state_changed.connect(self._reload)
        controller.run_started.connect(self._on_run_started)
        controller.run_progress.connect(self._on_run_progress)
        controller.run_failed.connect(self._on_run_failed)

        self._populate_voice_table()
        controller.refresh()
        self._reload_collections()
        self._reload()

    # -- collection / scope / card selection ----------------------------

    def _reload_collections(self) -> None:
        self._collection_combo.blockSignals(True)
        self._collection_combo.clear()
        self._collection_combo.addItem("Choose a Collection…", None)
        for collection in self._controller.collections:
            self._collection_combo.addItem(str(collection["name"]), int(collection["id"]))
        self._collection_combo.blockSignals(False)

    def _on_collection_changed(self, index: int) -> None:
        self._controller.set_collection(self._collection_combo.itemData(index))

    def _on_scope_changed(self, index: int) -> None:
        value = self._scope_combo.itemData(index)
        if value is not None:
            self._controller.set_scope(value)

    def _on_single_card_changed(self, index: int) -> None:
        self._controller.set_single_card_number(self._single_card_combo.itemData(index))

    def _on_card_item_changed(self, _item: QListWidgetItem) -> None:
        selected = set()
        for row in range(self._card_list.count()):
            item = self._card_list.item(row)
            if item.checkState() == Qt.CheckState.Checked:
                selected.add(int(item.data(Qt.ItemDataRole.UserRole)))
        self._controller.set_selected_card_numbers(selected)

    def _reload_card_selectors(self) -> None:
        cards = self._controller.cards
        self._single_card_combo.blockSignals(True)
        self._single_card_combo.clear()
        for card_number in sorted(cards):
            name = cards[card_number]["name"] or f"Card {card_number}"
            self._single_card_combo.addItem(f"Card {card_number} — {name}", card_number)
        self._single_card_combo.blockSignals(False)

        self._card_list.blockSignals(True)
        self._card_list.clear()
        for card_number in sorted(cards):
            name = cards[card_number]["name"] or f"Card {card_number}"
            item = QListWidgetItem(f"Card {card_number} — {name}")
            item.setData(Qt.ItemDataRole.UserRole, card_number)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked
                if card_number in self._controller.selected_card_numbers
                else Qt.CheckState.Unchecked
            )
            self._card_list.addItem(item)
        self._card_list.blockSignals(False)

    def _update_scope_visibility(self) -> None:
        scope = self._controller.scope
        self._single_card_combo.setVisible(scope == SCOPE_SINGLE_CARD)
        self._card_list.setVisible(scope == SCOPE_SELECTED_CARDS)

    # -- voice assignment --------------------------------------------------

    def _populate_voice_table(self) -> None:
        rows = self._controller.voice_assignment_rows()
        self._voice_table.setRowCount(len(rows))
        for row_index, (language, provider_id, voice_id) in enumerate(rows):
            self._voice_table.setItem(row_index, 0, QTableWidgetItem(language))
            self._voice_table.setItem(row_index, 1, QTableWidgetItem(provider_id))
            self._voice_table.setItem(row_index, 2, QTableWidgetItem(voice_id))

    # -- configuration -----------------------------------------------------

    def _on_repetition_mode_changed(self, index: int) -> None:
        value = self._repetition_mode_combo.itemData(index)
        if value is not None:
            self._controller.set_repetition_mode(value)

    def _on_conflict_changed(self, index: int) -> None:
        value = self._conflict_combo.itemData(index)
        if value is not None:
            self._controller.set_conflict_policy(value)

    def _on_choose_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose an Export Folder")
        if not path:
            return
        self._controller.set_destination_root(path)
        self._destination_label.setText(path)

    # -- plan ----------------------------------------------------------------

    def _on_build_plan(self) -> None:
        if not self._controller.can_build_plan():
            self._plan_error_label.setText(
                "Choose a Collection, a Card/selection matching the chosen scope, and a destination folder."
            )
            return
        self._controller.build_plan()

    def _plan_summary_text(self) -> str:
        plan = self._controller.plan
        if plan is None:
            return ""
        ready = plan.ready_count
        total = len(plan.items)
        text = f"{ready} of {total} Card(s) ready to export."
        if plan.issues:
            text += " " + "; ".join(issue.detail for issue in plan.issues)
        return text

    # -- consent / start ------------------------------------------------------

    def _consent_text(self) -> str:
        if self._controller.conflict_policy == CONFLICT_OVERWRITE:
            return "I understand this will overwrite any existing audio files with the same name."
        return "I understand this will write new audio files to the selected folder."

    def _update_start_enabled(self) -> None:
        can_start = (
            bool(self._controller.plan and self._controller.plan.ready_count)
            and self._consent_checkbox.isChecked()
            and not self._controller.is_running
        )
        self._start_button.setEnabled(can_start)

    def _on_start(self) -> None:
        self._consent_checkbox.setChecked(False)
        self._controller.run()

    def _on_retry(self) -> None:
        self._controller.retry()

    # -- run / progress --------------------------------------------------------

    def _on_run_started(self) -> None:
        self._progress_bar.setVisible(True)
        self._progress_bar.setRange(0, 0)
        self._cancel_button.setVisible(True)
        self._start_button.setEnabled(False)
        self._retry_button.setVisible(False)
        self._close_button.setEnabled(False)
        self._status_label.setText("Starting export…")

    def _on_run_progress(self, completed: int, total: int, kind: str) -> None:
        if total > 0:
            self._progress_bar.setRange(0, total)
            self._progress_bar.setValue(completed)
        self._status_label.setText(f"{kind.replace('_', ' ').capitalize()} ({completed}/{total})")

    def _on_run_failed(self, message: str) -> None:
        self._progress_bar.setVisible(False)
        self._cancel_button.setVisible(False)
        self._close_button.setEnabled(True)
        self._status_label.setText(f"Export failed: {message}")
        self._update_start_enabled()

    def _reload_result(self) -> None:
        result = self._controller.result
        self._progress_bar.setVisible(False)
        self._cancel_button.setVisible(False)
        self._close_button.setEnabled(True)
        if result is None:
            self._result_summary_label.setText("")
            self._result_table.setRowCount(0)
            self._retry_button.setVisible(False)
            self._status_label.setText("")
            return
        self._status_label.setText("Export finished.")
        self._result_summary_label.setText(
            f"Succeeded {result.succeeded_count} · Skipped {result.skipped_count} · "
            f"Failed {result.failed_count} · Unresolved {result.unresolved_count} · "
            f"Cancelled {result.cancelled_count}"
        )
        self._result_table.setRowCount(len(result.items))
        for row_index, item in enumerate(result.items):
            self._result_table.setItem(row_index, 0, QTableWidgetItem(str(item.plan.card_number)))
            self._result_table.setItem(row_index, 1, QTableWidgetItem(item.plan.card_name))
            self._result_table.setItem(row_index, 2, QTableWidgetItem(STATUS_LABELS.get(item.status, item.status)))
            self._result_table.setItem(row_index, 3, QTableWidgetItem(item.error_detail))
        self._retry_button.setVisible(self._controller.can_retry())

    # -- reload -----------------------------------------------------------------

    def _reload(self) -> None:
        self._reload_card_selectors()
        self._update_scope_visibility()

        index = self._collection_combo.findData(self._controller.collection_id)
        if index >= 0 and self._collection_combo.currentIndex() != index:
            self._collection_combo.blockSignals(True)
            self._collection_combo.setCurrentIndex(index)
            self._collection_combo.blockSignals(False)

        if self._controller.plan_error:
            self._plan_error_label.setText(self._controller.plan_error)
        else:
            self._plan_error_label.setText("")
        self._plan_summary_label.setText(self._plan_summary_text())
        self._consent_checkbox.setText(self._consent_text())
        # Every state change this reacts to means whatever Start would now
        # do has changed since the checkbox was last ticked (Import
        # Dialog's independent-review precedent, data_tools_view.py's
        # ``_reload()``): without this, a stale checked box could re-arm
        # Start against a just-changed scope/config/plan with no fresh
        # per-run consent.
        self._consent_checkbox.setChecked(False)
        self._update_start_enabled()
        self._reload_result()

    # -- lifecycle ---------------------------------------------------------------

    def closeEvent(self, event) -> None:
        if self._controller.is_running:
            answer = QMessageBox.question(
                self,
                "Export in progress",
                "An export is still running. Cancel it and close this window?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self._controller.shutdown()
        super().closeEvent(event)
