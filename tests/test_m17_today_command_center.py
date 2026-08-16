from __future__ import annotations

import ast
import os
import tempfile
import unittest
from pathlib import Path

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
Focused tests for the M17 Feature 1 Today / Command Center checkpoint:
src/ui_desktop/controllers/today_controller.py,
src/ui_desktop/views/today_view.py, src/ui_desktop/state/handoff.py, and
src/ui_desktop/qt_models/learning_queue_table_model.py. Distinct from
tests/test_m16_2_desktop_vertical_slice.py, which proves only the M16.2
vertical-slice proof of concept; these prove the real Command Center
product feature built on top of it.
"""

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if PYSIDE6_AVAILABLE:
    from src.ui_desktop.controllers.today_controller import TodayController
    from src.ui_desktop.state.handoff import LearningActionIntent
    from src.ui_desktop.views.today_view import PENDING_MIGRATION_TOOLTIP, TodayView

    def _qt_app() -> QApplication:
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app


class _SyntheticDatabaseTestCase(unittest.TestCase):
    """Shared setup matching the existing repository pattern (see
    tests/test_m16_2_desktop_vertical_slice.py): swap db.DB_PATH to a
    temporary synthetic database, never the user's personal data/vocab.db."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp_dir.name)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = self.root / "m17_today.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()


@unittest.skipUnless(
    PYSIDE6_AVAILABLE,
    "PySide6 is not installed; see requirements-desktop.txt. Desktop tests are "
    "desktop-only and optional for the core/Streamlit test run.",
)
class M17TodayControllerProjectionTests(unittest.TestCase):
    """Pure projections over an already-fetched overview -- no DB, no
    SQL, no learning-completion logic (mirrors DESIGN.md § 4.1's required
    hierarchy sources one-to-one)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    @staticmethod
    def _controller_with_overview(overview: dict) -> "TodayController":
        controller = TodayController()
        controller.overview = overview
        return controller

    def test_queue_items_empty_before_first_refresh(self) -> None:
        controller = TodayController()
        self.assertEqual(controller.queue_items(), [])
        self.assertIsNone(controller.primary_recommendation())
        self.assertEqual(controller.recent_activity(), [])
        self.assertEqual(controller.collections_needing_attention(), [])

    def test_queue_items_reads_daily_quiz_recommendations_not_raw_cards(self) -> None:
        overview = {
            "daily_quiz_recommendations": [{"title": "Quiz a never-quizzed card"}],
            "study_cards": [{"title": "should not be used"}],
        }
        controller = self._controller_with_overview(overview)
        self.assertEqual(controller.queue_items(), [{"title": "Quiz a never-quizzed card"}])

    def test_primary_recommendation_returns_first_item_only(self) -> None:
        overview = {"recommendations": [{"title": "a"}, {"title": "b"}]}
        controller = self._controller_with_overview(overview)
        self.assertEqual(controller.primary_recommendation(), {"title": "a"})

    def test_primary_recommendation_none_when_empty(self) -> None:
        controller = self._controller_with_overview({"recommendations": []})
        self.assertIsNone(controller.primary_recommendation())

    def test_recent_activity_reads_review_activity_recent_reviewed_cards(self) -> None:
        overview = {"review_activity": {"recent_reviewed_cards": [{"card_number": 1}]}}
        controller = self._controller_with_overview(overview)
        self.assertEqual(controller.recent_activity(), [{"card_number": 1}])

    def test_collections_needing_attention_filters_empty_and_missing(self) -> None:
        overview = {
            "special_collections": {
                "mistake_book": {"exists": True, "collection_id": 1, "entry_count": 3},
                "proficient_pool": {"exists": True, "collection_id": 2, "entry_count": 0},
                "starred": {"exists": False, "collection_id": None, "entry_count": 0},
            }
        }
        controller = self._controller_with_overview(overview)
        attention = controller.collections_needing_attention()
        self.assertEqual(len(attention), 1)
        self.assertEqual(attention[0]["label"], "Mistake Book")
        self.assertEqual(attention[0]["entry_count"], 3)

    def test_build_learning_action_intent_from_queue_item(self) -> None:
        controller = TodayController()
        item = {
            "collection_id": 5,
            "collection_name": "French",
            "card_number": 2,
            "card_id": 9,
            "preferred_quiz_type": "mixed_mcq",
            "quiz_mode": "card",
            "reason": "never_quizzed",
            "entry_count": 4,
        }
        intent = controller.build_learning_action_intent(item)
        self.assertIsInstance(intent, LearningActionIntent)
        self.assertEqual(intent.action, "quiz")
        self.assertEqual(intent.collection_id, 5)
        self.assertEqual(intent.card_id, 9)
        self.assertEqual(intent.quiz_type, "mixed_mcq")
        self.assertEqual(intent.entry_count, 4)

    def test_build_learning_action_intent_for_suggestion_item_is_review_not_quiz(self) -> None:
        controller = TodayController()
        item = {"quiz_mode": "suggestion", "reason": "recent_entries_need_collection"}
        intent = controller.build_learning_action_intent(item)
        self.assertEqual(intent.action, "review")


@unittest.skipUnless(
    PYSIDE6_AVAILABLE,
    "PySide6 is not installed; see requirements-desktop.txt. Desktop tests are "
    "desktop-only and optional for the core/Streamlit test run.",
)
class M17TodayControllerRealCoreIntegrationTests(_SyntheticDatabaseTestCase):
    """Proves TodayController.refresh() still calls the real, unmodified
    src.learning_workflow.get_today_overview() (no duplicated business
    logic), and that the Command Center projections reflect real data."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_never_quizzed_card_surfaces_in_queue_and_recommendation(self) -> None:
        entry_a = add_entry("French", "English", "word", "chat", "cat")
        entry_b = add_entry("French", "English", "word", "chien", "dog")
        collection_id = create_collection("French Basics", card_size=2)
        add_entries_to_collection([entry_a, entry_b], collection_id)

        controller = TodayController()
        controller.refresh()

        queue = controller.queue_items()
        # Both entries were just created, so get_daily_quiz_candidates()
        # also legitimately surfaces a "recently added, needs a
        # collection" suggestion alongside the never-quizzed Card -- that
        # is real core behavior, not something Today invents.
        never_quizzed_items = [
            item for item in queue if item["recommendation_type"] == "never_quizzed_card"
        ]
        self.assertEqual(len(never_quizzed_items), 1)
        self.assertEqual(never_quizzed_items[0]["collection_name"], "French Basics")
        self.assertTrue(never_quizzed_items[0]["enabled"])

        recommendation = controller.primary_recommendation()
        self.assertIsNotNone(recommendation)
        self.assertEqual(recommendation["target_page"], "Review")

        # No Card learning has been recorded yet -- factual, not fabricated.
        self.assertEqual(controller.recent_activity(), [])
        self.assertEqual(controller.collections_needing_attention(), [])

    def test_empty_database_produces_entries_recommendation_not_a_crash(self) -> None:
        controller = TodayController()
        controller.refresh()

        self.assertEqual(controller.queue_items(), [])
        recommendation = controller.primary_recommendation()
        self.assertIsNotNone(recommendation)
        self.assertEqual(recommendation["target_page"], "Entries")


@unittest.skipUnless(
    PYSIDE6_AVAILABLE,
    "PySide6 is not installed; see requirements-desktop.txt. Desktop tests are "
    "desktop-only and optional for the core/Streamlit test run.",
)
class M17TodayViewStructureTests(_SyntheticDatabaseTestCase):
    """Structural DESIGN.md § 4.1 / § 19 acceptance proof: the Learning
    Queue must be the dominant area, and no Review/Quiz action may appear
    functional before those workspaces exist (M17 Feature 1 prompt § 6)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def _built_view(self) -> "TodayView":
        controller = TodayController()
        view = TodayView(controller)
        self.addCleanup(view.deleteLater)
        controller.refresh()
        return view

    def test_learning_queue_has_greater_layout_weight_than_other_sections(self) -> None:
        """DESIGN.md § 4.1: "the Learning Queue must have greater visual
        weight than statistics" / § 19 Today PASS criterion. Proven via
        the actual QVBoxLayout stretch factors driving that dominance."""
        view = self._built_view()
        layout = view.layout()

        queue_index = layout.indexOf(view._queue_table)
        self.assertGreaterEqual(queue_index, 0)
        queue_stretch = layout.stretch(queue_index)

        other_stretches = [
            layout.stretch(i) for i in range(layout.count()) if i != queue_index
        ]
        self.assertTrue(all(queue_stretch > stretch for stretch in other_stretches))

    def test_summary_reflects_workload_and_never_turns_into_a_chart_dashboard(self) -> None:
        add_entry("English", "Chinese", "word", "vocab", "a word")
        view = self._built_view()
        self.assertIn("Available Cards:", view._summary_label.text())
        self.assertIn("Never Quizzed:", view._summary_label.text())
        # DESIGN.md § 18 Today anti-pattern: no chart/plot widget exists.
        self.assertFalse(hasattr(view, "_chart"))

    def test_queue_start_button_is_never_a_dead_functional_button(self) -> None:
        """Every current Learning Queue item targets Review/Quiz, which
        does not exist in the desktop app yet; selecting a row must
        disable Start with an explanatory tooltip, never leave it looking
        clickable-but-broken (M17 Feature 1 prompt § 6)."""
        entry_a = add_entry("French", "English", "word", "chat", "cat")
        entry_b = add_entry("French", "English", "word", "chien", "dog")
        collection_id = create_collection("French Basics", card_size=2)
        add_entries_to_collection([entry_a, entry_b], collection_id)

        view = self._built_view()
        self.assertGreater(view._queue_model.rowCount(), 0)

        selection_model = view._queue_table.selectionModel()
        index = view._queue_model.index(0, 0)
        selection_model.setCurrentIndex(
            index, selection_model.SelectionFlag.ClearAndSelect | selection_model.SelectionFlag.Rows
        )

        self.assertFalse(view._queue_start_button.isEnabled())
        self.assertIn("coming in a later M17 checkpoint", view._queue_start_button.toolTip())

    def test_pending_quick_actions_are_disabled_with_explanatory_tooltip(self) -> None:
        view = self._built_view()
        self.assertFalse(view._review_button.isEnabled())
        self.assertFalse(view._quiz_button.isEnabled())
        self.assertEqual(view._review_button.toolTip(), PENDING_MIGRATION_TOOLTIP)
        self.assertEqual(view._quiz_button.toolTip(), PENDING_MIGRATION_TOOLTIP)

    def test_open_entries_quick_action_is_real_and_emits_shared_navigation_signal(self) -> None:
        view = self._built_view()
        self.assertTrue(view._entries_button.isEnabled())

        received = []
        view.entries_requested.connect(lambda: received.append(True))
        view._entries_button.click()

        self.assertEqual(received, [True])

    def test_next_action_button_enabled_only_when_target_is_entries(self) -> None:
        # Empty database -> build_today_recommendations() falls through to
        # the "add_or_organize_entries" recommendation, target_page="Entries".
        view = self._built_view()

        self.assertTrue(view._next_action_button.isEnabled())
        received = []
        view.entries_requested.connect(lambda: received.append(True))
        view._next_action_button.click()
        self.assertEqual(received, [True])

    def test_next_action_button_disabled_for_review_target(self) -> None:
        entry_a = add_entry("French", "English", "word", "chat", "cat")
        entry_b = add_entry("French", "English", "word", "chien", "dog")
        collection_id = create_collection("French Basics", card_size=2)
        add_entries_to_collection([entry_a, entry_b], collection_id)

        view = self._built_view()

        self.assertFalse(view._next_action_button.isEnabled())
        self.assertEqual(view._next_action_button.toolTip(), PENDING_MIGRATION_TOOLTIP)


@unittest.skipUnless(
    PYSIDE6_AVAILABLE,
    "PySide6 is not installed; see requirements-desktop.txt. Desktop tests are "
    "desktop-only and optional for the core/Streamlit test run.",
)
class M17TodayArchitectureContinuityTests(unittest.TestCase):
    """M17 Feature 1 prompt § 5 architecture-continuity guardrail: Today
    must not directly import/instantiate a future Review or Quiz view, and
    must not couple to EntriesView/AppState directly (shared navigation
    only, via the entries_requested signal MainWindow wires)."""

    def test_today_view_does_not_import_entries_view_or_app_state(self) -> None:
        path = PROJECT_ROOT / "src" / "ui_desktop" / "views" / "today_view.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported_modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        self.assertNotIn("src.ui_desktop.views.entries_view", imported_modules)
        self.assertNotIn("src.ui_desktop.state.app_state", imported_modules)

    def test_today_controller_has_no_raw_sql(self) -> None:
        path = PROJECT_ROOT / "src" / "ui_desktop" / "controllers" / "today_controller.py"
        text = path.read_text(encoding="utf-8")
        for forbidden in ("SELECT ", "INSERT ", "UPDATE ", "DELETE FROM"):
            self.assertNotIn(forbidden, text.upper())


if __name__ == "__main__":
    unittest.main()
