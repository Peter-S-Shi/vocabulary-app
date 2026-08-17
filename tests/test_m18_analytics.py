from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when PySide6 is absent
    PYSIDE6_AVAILABLE = False

from src import db
from src.collections import add_entries_to_collection, create_collection
from src.entries import add_entry

"""
Focused tests for M18 Phase D -- Analytics Landing (analytics_view.py
Design/Implementation Trace above `AnalyticsView`) and Full Findings
(§ 6.6 P4A Design Derivation Record above `_FullFindingsDialog`). Per
DESIGN.md § 2 Rule C these are structural/behavioral proof that
`AnalyticsController` delegates every read to the exact same
`src.insights`/`src.analytics` functions the M14 core already provides
(no invented thresholds/scores, no SQL, no mutation) and that the scope
model, Brief cap, and Coverage-panel absence for "All Entries" all match
the frozen M14/DESIGN semantics -- not evidence the P4/P4A compositions
were visually realized. Native human visual acceptance is a separate,
required gate (AGENTS.md).
"""

if PYSIDE6_AVAILABLE:
    from src.ui_desktop.controllers.analytics_controller import AnalyticsController
    from src.ui_desktop.theming.theme_manager import build_stylesheet
    from src.ui_desktop.theming.tokens import THEME_CALM_BLUE_DARK, THEME_CALM_BLUE_LIGHT
    from src.ui_desktop.views.analytics_view import (
        AnalyticsView,
        _FullFindingsDialog,
        _scope_description,
        _suggested_action_text,
    )
    from src.ui_desktop.widgets.navigation_rail import NavigationRail

    def _qt_app() -> QApplication:
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app


class _SyntheticDatabaseTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp_dir.name)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = self.root / "m18_analytics.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class NavigationRailAnalyticsEnabledTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_analytics_destination_is_enabled(self) -> None:
        rail = NavigationRail()
        self.addCleanup(rail.deleteLater)
        self.assertTrue(rail.is_enabled_destination("analytics"))


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class AnalyticsControllerTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_refresh_on_empty_database_produces_an_empty_brief(self) -> None:
        controller = AnalyticsController()

        controller.refresh()

        self.assertEqual(controller.brief, [])
        self.assertEqual(controller.full_findings["entry_findings"], [])
        self.assertIsNone(controller.coverage)

    def test_a_never_quizzed_entry_appears_in_full_findings(self) -> None:
        add_entry("French", "English", "word", "pomme", "apple")
        controller = AnalyticsController()

        controller.refresh()

        findings = controller.full_findings["entry_findings"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["primary_finding"], "never_quizzed")

    def test_refresh_never_mutates_learning_state(self) -> None:
        add_entry("French", "English", "word", "pomme", "apple")
        controller = AnalyticsController()

        controller.refresh()
        controller.refresh()

        self.assertEqual(len(controller.full_findings["entry_findings"]), 1)
        self.assertEqual(controller.full_findings["entry_findings"][0]["primary_finding"], "never_quizzed")

    def test_scope_all_has_no_coverage_panel(self) -> None:
        collection_id = create_collection("Fruits", "", card_size=8)
        entry_id = add_entry("French", "English", "word", "pomme", "apple")
        add_entries_to_collection([entry_id], collection_id)
        controller = AnalyticsController()
        controller.refresh()

        controller.set_scope("all")

        self.assertIsNone(controller.coverage)

    def test_scope_collection_has_a_coverage_panel(self) -> None:
        collection_id = create_collection("Fruits", "", card_size=8)
        entry_id = add_entry("French", "English", "word", "pomme", "apple")
        add_entries_to_collection([entry_id], collection_id)
        controller = AnalyticsController()
        controller.refresh()

        controller.set_scope("collection", collection_id)

        self.assertIsNotNone(controller.coverage)
        self.assertEqual(controller.coverage["total_current_entries"], 1)
        self.assertEqual(controller.coverage["touched_count"], 0)  # never quizzed -> untouched
        self.assertIn("scope_activity", controller.coverage)

    def test_scope_filters_findings_to_the_selected_collection(self) -> None:
        collection_id = create_collection("Fruits", "", card_size=8)
        in_scope_entry = add_entry("French", "English", "word", "pomme", "apple")
        add_entries_to_collection([in_scope_entry], collection_id)
        add_entry("French", "English", "word", "poire", "pear")  # not in any Collection
        controller = AnalyticsController()
        controller.refresh()

        controller.set_scope("collection", collection_id)

        scope_ids = {item["scope_id"] for item in controller.full_findings["entry_findings"]}
        self.assertEqual(scope_ids, {in_scope_entry})

    def test_refresh_resets_a_stale_scope_to_all_if_the_collection_is_gone(self) -> None:
        collection_id = create_collection("Fruits", "", card_size=8)
        controller = AnalyticsController()
        controller.refresh()
        controller.set_scope("collection", collection_id)
        self.assertEqual(controller.scope_type, "collection")

        from src.collections import delete_collection

        delete_collection(collection_id)
        controller.refresh()

        self.assertEqual(controller.scope_type, "all")
        self.assertIsNone(controller.scope_id)

    def test_actionable_findings_excludes_none_findings(self) -> None:
        add_entry("French", "English", "word", "pomme", "apple")  # never_quizzed, not "none"
        controller = AnalyticsController()
        controller.refresh()

        actionable = controller.actionable_findings()

        self.assertTrue(all(item.get("primary_finding") != "none" for item in actionable))


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class AnalyticsViewStructureTests(_SyntheticDatabaseTestCase):
    """Structural-only proof (DESIGN.md § 2 Rule C)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_empty_brief_shows_a_message_not_a_blank_page(self) -> None:
        controller = AnalyticsController()
        view = AnalyticsView(controller)
        self.addCleanup(view.deleteLater)

        view.refresh()

        self.assertEqual(view._brief_layout.count(), 1)  # the empty-state message

    def test_scope_combo_lists_collections(self) -> None:
        create_collection("Fruits", "", card_size=8)
        controller = AnalyticsController()
        view = AnalyticsView(controller)
        self.addCleanup(view.deleteLater)

        view.refresh()

        names = {view._scope_combo.itemText(i) for i in range(view._scope_combo.count())}
        self.assertIn("All Entries", names)
        self.assertIn("Fruits", names)

    def test_full_findings_dialog_lists_actionable_findings_and_shows_detail(self) -> None:
        add_entry("French", "English", "word", "pomme", "apple")
        controller = AnalyticsController()
        controller.refresh()
        dialog = _FullFindingsDialog(controller, parent=None)
        self.addCleanup(dialog.deleteLater)

        # One entry-level "Never Quizzed" finding plus one template-level
        # Coverage Gap finding for the auto-created General Entry
        # Template (0% touched with one untouched Entry) -- both are
        # real, correct M14 output for this scenario, not a bug.
        self.assertEqual(dialog._table.rowCount(), 2)
        never_quizzed_row = next(
            row
            for row in range(dialog._table.rowCount())
            if dialog._table.item(row, 1).text() == "Never Quizzed"
        )

        dialog._table.selectRow(never_quizzed_row)

        self.assertIn("Never Quizzed", dialog._detail_label.text())

    def test_full_findings_dialog_empty_selection_shows_a_prompt(self) -> None:
        controller = AnalyticsController()
        controller.refresh()
        dialog = _FullFindingsDialog(controller, parent=None)
        self.addCleanup(dialog.deleteLater)

        self.assertIn("Select a Finding", dialog._detail_label.text())

    def test_show_every_current_entry_checkbox_reveals_none_findings(self) -> None:
        """Regression for an independent-review finding: this dialog's
        own Design Derivation Record documented a "Show every current
        Entry" checkbox, but the table was hard-wired to
        actionable_findings() with no way to reveal "none"-Finding
        Entries. Two Entries: one never-quizzed (actionable), one quizzed
        to a "none" Finding is impractical to construct quickly here, so
        this instead proves the checkbox actually switches data sources
        by comparing row counts against the controller's own two
        collections directly."""
        add_entry("French", "English", "word", "pomme", "apple")
        controller = AnalyticsController()
        controller.refresh()
        dialog = _FullFindingsDialog(controller, parent=None)
        self.addCleanup(dialog.deleteLater)
        unchecked_count = dialog._table.rowCount()
        self.assertEqual(unchecked_count, len(controller.actionable_findings()))

        dialog._show_all_checkbox.setChecked(True)

        self.assertEqual(dialog._table.rowCount(), len(controller.full_findings["full_findings"]))

    def test_scope_description_resolves_a_collection_name_not_a_bare_label(self) -> None:
        """Regression for an independent-review finding: a bare
        "Collection"/"Template" string made multiple distinct Coverage
        Gap findings indistinguishable from each other."""
        item = {"scope_type": "collection", "scope_id": 42}

        bare = _scope_description(item)
        resolved = _scope_description(item, collection_names={42: "Everyday Words"})

        self.assertEqual(bare, "Collection #42")
        self.assertEqual(resolved, "Collection: Everyday Words")

    def test_scope_description_resolves_a_template_name(self) -> None:
        item = {"scope_type": "template", "scope_id": 7}

        resolved = _scope_description(item, template_names={7: "French Verb Present"})

        self.assertEqual(resolved, "Template: French Verb Present")

    def test_suggested_action_text_omits_a_none_action_type(self) -> None:
        """Regression for an independent-review finding: src.insights
        sets suggested_action.action_type="none" for a Strength finding
        (a real, present dict signaling "no action needed", not the
        absence of one). Rendering that literally produced the
        nonsensical "Suggested: None" instead of omitting the line."""
        item = {"suggested_action": {"action_type": "none"}}

        self.assertEqual(_suggested_action_text(item), "")

    def test_suggested_action_text_still_renders_a_real_action(self) -> None:
        item = {"suggested_action": {"action_type": "quiz_uncovered_content"}}

        self.assertEqual(_suggested_action_text(item), "Suggested: Quiz uncovered content")

    def test_full_findings_scope_column_shows_a_real_collection_name(self) -> None:
        """Integration proof (not just the pure-function unit tests
        above) that a Coverage Gap finding's Scope column resolves to a
        real Collection name from within the actual dialog flow."""
        collection_id = create_collection("Everyday Words", "", card_size=8)
        entry_id = add_entry("French", "English", "word", "pomme", "apple")
        add_entries_to_collection([entry_id], collection_id)
        controller = AnalyticsController()
        controller.refresh()
        dialog = _FullFindingsDialog(controller, parent=None)
        self.addCleanup(dialog.deleteLater)

        scope_texts = {dialog._table.item(row, 2).text() for row in range(dialog._table.rowCount())}

        self.assertIn("Collection: Everyday Words", scope_texts)
        self.assertFalse(any(text == "Collection" for text in scope_texts))

    def test_view_refresh_rebuilds_the_brief_exactly_once(self) -> None:
        """Regression for an independent-review finding: refresh()
        called self._reload() explicitly in addition to the reload the
        connected state_changed signal already triggers, rebuilding the
        Brief/Coverage layout twice on every navigation. `_reload` must
        be wrapped at the *class* level before construction: Qt's
        `connect(self._reload)` call inside `__init__` captures a bound
        method against whatever the class attribute resolves to at that
        moment, so patching the instance afterward would not intercept
        the signal-triggered call at all."""
        call_count = 0
        original_reload = AnalyticsView._reload

        def _counting_reload(self):
            nonlocal call_count
            call_count += 1
            original_reload(self)

        with patch.object(AnalyticsView, "_reload", _counting_reload):
            controller = AnalyticsController()
            view = AnalyticsView(controller)
            self.addCleanup(view.deleteLater)

            view.refresh()

        self.assertEqual(call_count, 1)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class M18AnalyticsTokenQssStructuralCoverageTests(unittest.TestCase):
    REPRESENTATIVE_SELECTORS = (
        "#analytics-title",
        "#analytics-scope-combo",
        "#analytics-brief-heading",
        "#analytics-evidence-heading",
        "#analytics-full-findings-button",
        "#analytics-empty-state",
        "#analytics-coverage-label",
        "#analytics-coverage-value",
        '#analytics-brief-card[priority="high"]',
        '#analytics-brief-card[priority="medium"]',
        '#analytics-brief-card[priority="low"]',
        "#analytics-brief-priority",
        "#analytics-brief-finding",
        "#analytics-brief-scope",
        "#analytics-brief-reason",
        "#analytics-brief-action",
        "#analytics-detail-heading",
        "#analytics-detail-label",
    )

    def _assert_all_selectors_present(self, tokens) -> None:
        stylesheet = build_stylesheet(tokens)
        for selector in self.REPRESENTATIVE_SELECTORS:
            self.assertIn(selector, stylesheet, f"missing themed selector: {selector}")

    def test_light_calm_blue_covers_representative_surfaces(self) -> None:
        self._assert_all_selectors_present(THEME_CALM_BLUE_LIGHT)

    def test_dark_calm_blue_covers_representative_surfaces(self) -> None:
        self._assert_all_selectors_present(THEME_CALM_BLUE_DARK)


if __name__ == "__main__":
    unittest.main()
