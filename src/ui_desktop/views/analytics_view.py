from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.ui_desktop.controllers.analytics_controller import AnalyticsController
from src.ui_desktop.theming.metrics import SPACING

"""
Analytics Landing -- Learning Brief First (DESIGN.md § 6.5, CANONICAL,
`VR-ANALYTICS-001`). Frozen composition (not agent-derived -- DESIGN
controls spatial composition, hierarchy, and dominance; implementation
freedom is limited to concrete widget choices):

  DESIGN authority          | Requirement                    | Concrete decision
  -------------------------- | ------------------------------ | -------------------------------------------
  § 6.5 frozen composition   | title + scope/filter controls  | "Learning Analytics" title + a scope combo
                              | at top                          (All Entries / one Collection), matching
                              |                                  Entries/Review Calendar's toolbar grammar.
  § 6.5 dominance rule       | Learning Brief dominant, at    | a vertical list of up to 5 compact Finding
  "Interpretation first ->    | most 5 items, may be empty     cards (never a table -- DESIGN forbids
  evidence second ->          |                                 "Findings table first on the landing page"),
  drill-down third"           |                                 each showing priority + Finding category +
                              |                                  reason + a recommendation (text only, never
                              |                                  a button that mutates state).
  § 6.5 "supporting evidence  | Coverage/Scope Activity        a secondary "Supporting Evidence" section
  remains secondary"          | remains secondary; Touched vs   below the Brief: Coverage rows (only for a
                              |  Interpretable Coverage and     selected Collection -- there is no global
                              |  Content Knowledge vs Scope     Coverage function in src.analytics, so this
                              |  Activity stay distinct         section is honestly absent for "All
                              |                                  Entries" rather than inventing one),
                              |                                  labeled Touched/Interpretable/Scope
                              |                                  Activity/Never Quizzed as four distinct
                              |                                  rows, never merged into one metric.
  § 6.5 "drill-down third"    | Full Findings entry point       one "View Full Findings" action opening
                              |                                  `_FullFindingsDialog` (§ 6.6 P4A pattern)
                              |                                  -- never inline on the landing page.
  § 6.5 forbidden             | no rainbow severity dashboard, | priority is a single restrained left-
  substitutions                | no KPI tiles first              border accent per card (high/medium/low),
                              |                                  never a filled color badge grid; no chart
                              |                                  widgets anywhere on this page.

Full Findings (§ 6.6, `VR-ANALYTICS-002`, B "P4A") Design Derivation
Record per § 9, since the exact local composition is not fully obvious
from the parent pattern alone:

  1. Interaction Mode        -> Utility/Dialog (a drill-down from
                                 Management, not a second landing page).
  2. Parent Pattern          -> P4A Finding Inbox + Evidence Inspector:
                                 "Findings Table dominant, Evidence
                                 Inspector secondary."
  3. Primary User Task       -> browse every current Finding (not just
                                 the capped Brief) and inspect one
                                 Finding's full supporting evidence.
  4. Spatial Composition     -> compact scope/filter context (inherited
                                 from the Landing page's already-selected
                                 scope) -> dominant Findings table ->
                                 secondary Evidence Inspector detail pane
                                 below it, populated on row selection.
  5. Dominance Rule          -> the table dominates; the inspector
                                 explains the current selection only.
  6. Density Rule            -> Management Mode density, matching
                                 Entries/Templates/Review Calendar tables.
  7. Surface Hierarchy       -> table on `surface_primary`, matching
                                 every other M18 table.
  8. Action Hierarchy        -> no destructive/mutating actions exist
                                 here (read-only, like Review Calendar's
                                 historical evidence section);
                                 a "Show every current Entry" checkbox is
                                 the only control besides row selection.
  9. Editing Container       -> none; purely a read surface.
 10. Navigation/Chrome       -> modal dialog over the Analytics workspace,
                                 no chrome swap.
 11. Motion/Transition       -> none new.
 12. Canonical Visual Rel.   -> table/detail vocabulary inherited from
                                 Entries/Review Calendar rather than
                                 inventing new grammar.
 13. Native Human Acceptance -> the real native Full Findings dialog
                                 showing a populated Findings table and a
                                 selected row's Evidence Inspector detail,
                                 in Light and Dark Mode.

Human Gate 2 corrective (M18 Phase D, DESIGN.md § 12.4 "Long-running
work"): on a real production database, Analytics computation was slow
enough on the Qt UI thread to make the whole app stop responding.
``AnalyticsController`` now runs that computation on a background
``QThread`` (see its module docstring); this view reflects that with a
loading state -- a determinate, staged ``QProgressBar`` (truthful,
step-based progress; never a fabricated percentage within a step) plus a
status label naming the current stage -- shown in place of the Brief/
Coverage content while a load is in flight, and an actionable error state
(message + Retry) if the load fails. Exactly one of the loading row, the
error state, or the content scroll area is visible at a time.
"""

_FINDING_LABELS = {
    "never_quizzed": "Never Quizzed",
    "insufficient_evidence": "Insufficient Evidence",
    "stale_evidence": "Stale Evidence",
    "recovery": "Recovery",
    "needs_attention": "Needs Attention",
    "strength": "Strength",
    "none": "None",
    "coverage_gap": "Coverage Gap",
}
_PRIORITY_LABELS = {"high": "High", "medium": "Medium", "low": "Low"}


def _finding_label(item: dict) -> str:
    if item.get("coverage_gap_type"):
        gap = str(item["coverage_gap_type"]).replace("_", " ").title()
        return f"Coverage Gap — {gap}"
    return _FINDING_LABELS.get(str(item.get("primary_finding")), str(item.get("primary_finding") or ""))


def _scope_description(
    item: dict, collection_names: dict[int, str] | None = None, template_names: dict[int, str] | None = None
) -> str:
    """Independent-review finding: a bare "Collection"/"Template" string
    made multiple distinct Coverage Gap findings indistinguishable from
    each other -- resolve the actual name (falling back to the numeric
    id if the name lookup is stale/missing) the same way every other
    scope already carries its own identity (Entry #, Card #)."""
    collection_names = collection_names or {}
    template_names = template_names or {}
    scope_type = str(item.get("scope_type") or "")
    if scope_type == "entry":
        return f"Entry #{item.get('scope_id')}"
    if scope_type == "entry_cluster":
        count = (item.get("ranking_metadata") or {}).get("supporting_entry_count") or len(
            item.get("supporting_entry_ids") or []
        )
        return f"{count} related Entries"
    if scope_type == "card":
        card_text = f"Card #{item.get('card_number')}" if item.get("card_number") else "Card"
        collection_id = item.get("collection_id")
        if collection_id is not None and int(collection_id) in collection_names:
            return f"{card_text} — {collection_names[int(collection_id)]}"
        return card_text
    if scope_type == "collection":
        scope_id = item.get("scope_id")
        name = collection_names.get(int(scope_id)) if scope_id is not None else None
        return f"Collection: {name}" if name else f"Collection #{scope_id}"
    if scope_type == "template":
        scope_id = item.get("scope_id")
        name = template_names.get(int(scope_id)) if scope_id is not None else None
        return f"Template: {name}" if name else f"Template #{scope_id}"
    return scope_type.title()


def _reason_text(item: dict) -> str:
    codes = item.get("reason_codes") or []
    return "; ".join(str(code).replace("_", " ").capitalize() for code in codes)


def _suggested_action_text(item: dict) -> str:
    """Independent-review finding: src.insights sets action_type="none"
    for a Strength finding's suggested_action (a real, present dict
    signaling "no action needed", not the absence of one) -- rendering
    that literally as "Suggested: None" misrepresented it as an actual
    recommendation."""
    action = item.get("suggested_action")
    if not action:
        return ""
    raw_action_type = str(action.get("action_type") or "").strip().lower()
    if raw_action_type in ("", "none"):
        return ""
    action_type = raw_action_type.replace("_", " ").capitalize()
    return f"Suggested: {action_type}"


class AnalyticsView(QWidget):
    def __init__(self, controller: AnalyticsController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("analytics-root")
        self._controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING.lg, SPACING.lg, SPACING.lg, SPACING.lg)
        layout.setSpacing(SPACING.md)

        toolbar = QHBoxLayout()
        title = QLabel("Learning Analytics", self)
        title.setObjectName("analytics-title")
        toolbar.addWidget(title)
        toolbar.addStretch(1)
        scope_label = QLabel("Scope", self)
        scope_label.setObjectName("analytics-scope-label")
        toolbar.addWidget(scope_label)
        self._scope_combo = QComboBox(self)
        self._scope_combo.setObjectName("analytics-scope-combo")
        self._scope_combo.currentIndexChanged.connect(self._on_scope_changed)
        toolbar.addWidget(self._scope_combo)
        layout.addLayout(toolbar)

        # Long-running work loading state (DESIGN.md § 12.4; Human Gate 2
        # corrective). Determinate once a truthful stage/total is known
        # (a staged QProgressBar reflecting *completed steps*, never a
        # fabricated within-step percentage); indeterminate only in the
        # brief window before the first stage signal arrives. Exactly one
        # of this row, the error row below, or the content scroll area is
        # visible at a time.
        self._loading_widget = QWidget(self)
        self._loading_widget.setObjectName("analytics-loading-row")
        loading_layout = QHBoxLayout(self._loading_widget)
        loading_layout.setContentsMargins(0, 0, 0, 0)
        loading_layout.setSpacing(SPACING.sm)
        self._progress_bar = QProgressBar(self._loading_widget)
        self._progress_bar.setObjectName("analytics-progress-bar")
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setTextVisible(False)
        loading_layout.addWidget(self._progress_bar, 1)
        self._status_label = QLabel("Loading…", self._loading_widget)
        self._status_label.setObjectName("analytics-status-label")
        loading_layout.addWidget(self._status_label, 0)
        layout.addWidget(self._loading_widget)
        self._loading_widget.setVisible(False)

        # Actionable error state (DESIGN.md § 12.6 state language: what
        # happened, what was not changed, what the user can do next --
        # nothing was changed, since Analytics is read-only, and Retry is
        # the next action).
        self._error_widget = QWidget(self)
        self._error_widget.setObjectName("analytics-error-row")
        self._error_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        error_layout = QHBoxLayout(self._error_widget)
        error_layout.setContentsMargins(0, 0, 0, 0)
        error_layout.setSpacing(SPACING.sm)
        self._error_label = QLabel("", self._error_widget)
        self._error_label.setObjectName("analytics-error-label")
        self._error_label.setWordWrap(True)
        error_layout.addWidget(self._error_label, 1)
        self._retry_button = QPushButton("Retry", self._error_widget)
        self._retry_button.setObjectName("analytics-retry-button")
        self._retry_button.clicked.connect(self._on_retry)
        error_layout.addWidget(self._retry_button, 0)
        layout.addWidget(self._error_widget)
        self._error_widget.setVisible(False)

        self._scroll = QScrollArea(self)
        scroll = self._scroll
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget(scroll)
        body_layout = QVBoxLayout(body)
        body_layout.setSpacing(SPACING.md)
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)

        brief_heading = QLabel("Learning Brief", body)
        brief_heading.setObjectName("analytics-brief-heading")
        body_layout.addWidget(brief_heading)

        self._brief_container = QWidget(body)
        self._brief_layout = QVBoxLayout(self._brief_container)
        self._brief_layout.setContentsMargins(0, 0, 0, 0)
        self._brief_layout.setSpacing(SPACING.sm)
        body_layout.addWidget(self._brief_container)

        evidence_heading = QLabel("Supporting Evidence", body)
        evidence_heading.setObjectName("analytics-evidence-heading")
        body_layout.addWidget(evidence_heading)

        self._coverage_container = QWidget(body)
        self._coverage_layout = QVBoxLayout(self._coverage_container)
        self._coverage_layout.setContentsMargins(0, 0, 0, 0)
        self._coverage_layout.setSpacing(2)
        body_layout.addWidget(self._coverage_container)

        drill_down_row = QHBoxLayout()
        self._full_findings_button = QPushButton("View Full Findings", body)
        self._full_findings_button.setObjectName("analytics-full-findings-button")
        self._full_findings_button.clicked.connect(self._on_view_full_findings)
        drill_down_row.addWidget(self._full_findings_button)
        drill_down_row.addStretch(1)
        body_layout.addLayout(drill_down_row)

        body_layout.addStretch(1)

        controller.state_changed.connect(self._reload)
        controller.loading_started.connect(self._on_loading_started)
        controller.loading_stage.connect(self._on_loading_stage)
        controller.loading_failed.connect(self._on_loading_failed)

    def refresh(self) -> None:
        # controller.refresh() starts a background load and returns
        # immediately (Human Gate 2 corrective: this used to run
        # synchronously on the Qt UI thread and could freeze the app on a
        # large database) -- loading_started/loading_stage/state_changed/
        # loading_failed drive this view's loading/content/error states
        # from here on, so no explicit second reload call belongs here
        # (independent-review finding from the prior synchronous version).
        self._controller.refresh()
        self._reload_scope_combo()

    def _on_loading_started(self) -> None:
        self._error_widget.setVisible(False)
        self._scroll.setVisible(False)
        self._progress_bar.setRange(0, 0)
        self._status_label.setText("Loading…")
        self._loading_widget.setVisible(True)

    def _on_loading_stage(self, step: int, total: int, label: str) -> None:
        self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(step)
        self._status_label.setText(label)

    def _on_loading_failed(self, message: str) -> None:
        self._loading_widget.setVisible(False)
        self._scroll.setVisible(False)
        self._error_label.setText(f"Analytics couldn't finish loading: {message}. Nothing was changed.")
        self._error_widget.setVisible(True)

    def _on_retry(self) -> None:
        self._controller.refresh()

    def _reload_scope_combo(self) -> None:
        self._scope_combo.blockSignals(True)
        self._scope_combo.clear()
        self._scope_combo.addItem("All Entries", ("all", None))
        for collection in self._controller.collections:
            self._scope_combo.addItem(collection["name"], ("collection", int(collection["id"])))
        target = (self._controller.scope_type, self._controller.scope_id)
        index = self._scope_combo.findData(target)
        self._scope_combo.setCurrentIndex(index if index >= 0 else 0)
        self._scope_combo.blockSignals(False)

    def _on_scope_changed(self, index: int) -> None:
        data = self._scope_combo.itemData(index)
        if data is None:
            return
        scope_type, scope_id = data
        self._controller.set_scope(scope_type, scope_id)

    def _on_view_full_findings(self) -> None:
        dialog = _FullFindingsDialog(self._controller, parent=self)
        dialog.exec()

    def _reload(self) -> None:
        self._loading_widget.setVisible(False)
        self._error_widget.setVisible(False)
        self._scroll.setVisible(True)
        _clear_layout(self._brief_layout)
        brief = self._controller.brief
        if not brief:
            self._brief_layout.addWidget(
                _message_label("No urgent findings right now. This may mean evidence is still building.")
            )
        collection_names = self._controller.collection_names_by_id()
        template_names = self._controller.template_names_by_id()
        for item in brief:
            self._brief_layout.addWidget(
                _BriefCard(
                    item, self._brief_container, collection_names=collection_names, template_names=template_names
                )
            )

        _clear_layout(self._coverage_layout)
        coverage = self._controller.coverage
        if coverage is None:
            self._coverage_layout.addWidget(
                _message_label("Select a Collection above to see its Coverage.")
            )
        else:
            activity = coverage.get("scope_activity") or {}
            for label_text, value in (
                ("Touched Coverage", f"{_pct(coverage['touched_ratio'])} ({coverage['touched_count']}/{coverage['total_current_entries']})"),
                ("Interpretable Coverage", f"{_pct(coverage['interpretable_ratio'])} ({coverage['interpretable_count']}/{coverage['total_current_entries']})"),
                ("Never Quizzed", f"{_pct(coverage['never_quizzed_ratio'])} ({coverage['never_quizzed_count']}/{coverage['total_current_entries']})"),
                (
                    "Scope Activity (this Collection's Quiz context)",
                    f"{activity.get('eligible_attempts', 0)} attempts · "
                    f"{activity.get('distinct_entries', 0)} Entries · {activity.get('distinct_sessions', 0)} sessions",
                ),
            ):
                self._coverage_layout.addWidget(_coverage_row(label_text, value, self._coverage_container))


def _pct(ratio: float | None) -> str:
    return "—" if ratio is None else f"{ratio * 100:.0f}%"


def _coverage_row(label_text: str, value: str, parent: QWidget) -> QWidget:
    row = QWidget(parent)
    row.setObjectName("analytics-coverage-row")
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 2, 0, 2)
    label = QLabel(label_text, row)
    label.setObjectName("analytics-coverage-label")
    layout.addWidget(label, 1)
    value_label = QLabel(value, row)
    value_label.setObjectName("analytics-coverage-value")
    layout.addWidget(value_label, 0)
    return row


class _BriefCard(QWidget):
    """One Learning Brief item: a restrained priority-colored left
    border (never a filled color badge -- DESIGN.md § 6.5 forbids a
    "rainbow severity dashboard") plus text-only Finding category,
    scope, reason, and an optional recommendation. Never a button that
    mutates state (§ 6.5: "actions are recommendations")."""

    def __init__(
        self,
        item: dict,
        parent: QWidget | None = None,
        *,
        collection_names: dict[int, str] | None = None,
        template_names: dict[int, str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("analytics-brief-card")
        priority = str(item.get("priority") or "low")
        self.setProperty("priority", priority if priority in _PRIORITY_LABELS else "low")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING.md, SPACING.sm, SPACING.md, SPACING.sm)
        layout.setSpacing(2)

        header = QHBoxLayout()
        priority_label = QLabel(_PRIORITY_LABELS.get(priority, "Low"), self)
        priority_label.setObjectName("analytics-brief-priority")
        header.addWidget(priority_label, 0)
        finding_label = QLabel(_finding_label(item), self)
        finding_label.setObjectName("analytics-brief-finding")
        header.addWidget(finding_label, 0)
        header.addStretch(1)
        scope_label = QLabel(_scope_description(item, collection_names, template_names), self)
        scope_label.setObjectName("analytics-brief-scope")
        header.addWidget(scope_label, 0)
        layout.addLayout(header)

        reason = _reason_text(item)
        if reason:
            reason_label = QLabel(reason, self)
            reason_label.setObjectName("analytics-brief-reason")
            reason_label.setWordWrap(True)
            layout.addWidget(reason_label)

        action = _suggested_action_text(item)
        if action:
            action_label = QLabel(action, self)
            action_label.setObjectName("analytics-brief-action")
            action_label.setWordWrap(True)
            layout.addWidget(action_label)


class _FullFindingsDialog(QDialog):
    def __init__(self, controller: AnalyticsController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("analytics-full-findings-dialog")
        self.setWindowTitle("Full Findings")
        self.setMinimumSize(640, 560)
        self._controller = controller
        self._rows: list[dict] = []

        layout = QVBoxLayout(self)

        self._show_all_checkbox = QCheckBox("Show every current Entry (including no current Finding)", self)
        self._show_all_checkbox.toggled.connect(self._on_show_all_toggled)
        layout.addWidget(self._show_all_checkbox)

        self._table = QTableWidget(self)
        self._table.setObjectName("analytics-findings-table")
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Priority", "Finding", "Scope", "Reason"])
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.itemSelectionChanged.connect(self._on_row_selected)
        layout.addWidget(self._table, 2)

        detail_heading = QLabel("Evidence Inspector", self)
        detail_heading.setObjectName("analytics-detail-heading")
        layout.addWidget(detail_heading)

        self._detail_label = QLabel("Select a Finding above to inspect its evidence.", self)
        self._detail_label.setObjectName("analytics-detail-label")
        self._detail_label.setWordWrap(True)
        layout.addWidget(self._detail_label, 1)

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_button = QPushButton("Close", self)
        close_button.clicked.connect(self.accept)
        close_row.addWidget(close_button)
        layout.addLayout(close_row)

        self._reload_table()

    def _on_show_all_toggled(self, _checked: bool) -> None:
        self._reload_table()

    def _reload_table(self) -> None:
        # Independent-review finding: this dialog's own Design Derivation
        # Record documented a "Show every current Entry" checkbox as the
        # one control besides row selection, but the table was hard-wired
        # to actionable_findings() with no way to reveal "none"-Finding
        # Entries -- the checkbox above now actually exists and drives
        # this choice.
        if self._show_all_checkbox.isChecked():
            self._rows = self._controller.full_findings["full_findings"]
        else:
            self._rows = self._controller.actionable_findings()
        collection_names = self._controller.collection_names_by_id()
        template_names = self._controller.template_names_by_id()
        self._table.setRowCount(len(self._rows))
        for row, item in enumerate(self._rows):
            self._table.setItem(row, 0, QTableWidgetItem(_PRIORITY_LABELS.get(str(item.get("priority")), "")))
            self._table.setItem(row, 1, QTableWidgetItem(_finding_label(item)))
            self._table.setItem(row, 2, QTableWidgetItem(_scope_description(item, collection_names, template_names)))
            self._table.setItem(row, 3, QTableWidgetItem(_reason_text(item)))

    def _on_row_selected(self) -> None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._rows):
            self._detail_label.setText("Select a Finding above to inspect its evidence.")
            return
        item = self._rows[row]
        scope_text = _scope_description(
            item, self._controller.collection_names_by_id(), self._controller.template_names_by_id()
        )
        lines = [f"{_finding_label(item)} — {scope_text} — {_PRIORITY_LABELS.get(str(item.get('priority')), '')} priority"]
        if item.get("evidence_state"):
            lines.append(f"Evidence state: {item['evidence_state']}")
        metrics = item.get("metrics") or {}
        if metrics:
            lines.append("Metrics: " + ", ".join(f"{key.replace('_', ' ')}: {value}" for key, value in metrics.items()))
        reason = _reason_text(item)
        if reason:
            lines.append(f"Reasons: {reason}")
        action = _suggested_action_text(item)
        if action:
            lines.append(action)
        historical = item.get("historical_context")
        if historical:
            lines.append(
                "Historical context: "
                + ", ".join(f"{key.replace('_', ' ')}: {value}" for key, value in historical.items())
            )
        self._detail_label.setText("\n".join(lines))


def _message_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("analytics-empty-state")
    label.setWordWrap(True)
    return label


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
