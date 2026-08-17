from __future__ import annotations

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
Focused tests for the **retained, UI-independent** M17 Today groundwork:
``TodayController``'s read-only projections over the reusable core, and
the ``LearningActionIntent`` handoff contract in
``src/ui_desktop/state/handoff.py``.

Scope note: this module deliberately proves *no* Today presentation. The
M17 Today visual implementation was rejected at human visual review and
has been reset to the M16.2 placeholder pending a replacement DESIGN.md,
so the previous view-structure assertions (metric tiles, a table-based
Learning Queue, layout stretch dominance, panel/button composition) were
removed rather than carried forward -- keeping them would let a rejected
design silently constrain its replacement.

What survives here is genuinely presentation-agnostic: which reusable-core
data Today reads, how a queue item's intent is classified, and that the
desktop layer does not duplicate core/SQL. A future Today built from the
replacement DESIGN.md can consume all of it whether it renders rows,
cards, a rail, or something else entirely.
"""

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if PYSIDE6_AVAILABLE:
    from src.ui_desktop.controllers.today_controller import TodayController
    from src.ui_desktop.state.handoff import LearningActionIntent

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
    """Pure projections over an already-fetched overview -- no DB, no SQL,
    no learning-completion logic. These describe *what data Today reads*,
    not how any of it is displayed."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    @staticmethod
    def _controller_with_overview(overview: dict) -> "TodayController":
        controller = TodayController()
        controller.overview = overview
        return controller

    def test_projections_are_empty_before_first_refresh(self) -> None:
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


@unittest.skipUnless(
    PYSIDE6_AVAILABLE,
    "PySide6 is not installed; see requirements-desktop.txt. Desktop tests are "
    "desktop-only and optional for the core/Streamlit test run.",
)
class M17LearningActionIntentTests(unittest.TestCase):
    """The handoff contract: how a Learning Queue item's *meaning* is
    classified. Presentation-agnostic -- it says what the item is for, not
    how a screen should render or trigger it."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_card_queue_item_is_a_quiz_intent(self) -> None:
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

    def test_random_queue_item_is_also_a_quiz_intent(self) -> None:
        controller = TodayController()
        item = {"quiz_mode": "random", "reason": "proficient_pool_has_entries"}
        self.assertEqual(controller.build_learning_action_intent(item).action, "quiz")

    def test_recent_entries_suggestion_is_an_organize_intent_not_review(self) -> None:
        """The real core item this represents
        (recommendation_type="recent_entries_suggestion") means "add these
        Entries to a Collection before quizzing" -- it is not a Review or
        Quiz candidate, and must not be mislabeled as one."""
        controller = TodayController()
        item = {
            "recommendation_type": "recent_entries_suggestion",
            "quiz_mode": "suggestion",
            "reason": "recent_entries_need_collection",
            "entry_count": 3,
        }
        intent = controller.build_learning_action_intent(item)
        self.assertEqual(intent.action, "organize")
        self.assertNotEqual(intent.action, "review")
        self.assertNotEqual(intent.action, "quiz")
        self.assertEqual(intent.reason, "recent_entries_need_collection")
        self.assertEqual(intent.entry_count, 3)

    def test_unrecognized_quiz_mode_fails_closed_to_unknown(self) -> None:
        """An unrecognized future quiz_mode must not be guessed at as
        "quiz" or "review" -- the contract fails closed to an explicit
        "unknown" action so a caller can detect and handle the gap,
        rather than silently asserting semantics nobody has verified."""
        controller = TodayController()
        intent = controller.build_learning_action_intent(
            {"quiz_mode": "some-future-mode-not-yet-known"}
        )
        self.assertEqual(intent.action, "unknown")
        self.assertNotEqual(intent.action, "review")
        self.assertNotEqual(intent.action, "quiz")


@unittest.skipUnless(
    PYSIDE6_AVAILABLE,
    "PySide6 is not installed; see requirements-desktop.txt. Desktop tests are "
    "desktop-only and optional for the core/Streamlit test run.",
)
class M17TodayControllerRealCoreIntegrationTests(_SyntheticDatabaseTestCase):
    """Proves TodayController.refresh() calls the real, unmodified
    src.learning_workflow.get_today_overview() (no duplicated business
    logic), and that the projections reflect real data."""

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
class M17TodayCoreBoundaryTests(unittest.TestCase):
    """Reusable-core boundary guards (M16.1 contract): the desktop layer
    orchestrates, it does not reimplement domain behavior."""

    def test_today_controller_has_no_raw_sql(self) -> None:
        path = PROJECT_ROOT / "src" / "ui_desktop" / "controllers" / "today_controller.py"
        text = path.read_text(encoding="utf-8").upper()
        for forbidden in ("SELECT ", "INSERT ", "UPDATE ", "DELETE FROM"):
            self.assertNotIn(forbidden, text)

    def test_handoff_contract_has_no_raw_sql_and_no_core_import(self) -> None:
        path = PROJECT_ROOT / "src" / "ui_desktop" / "state" / "handoff.py"
        text = path.read_text(encoding="utf-8")
        for forbidden in ("SELECT ", "INSERT ", "UPDATE ", "DELETE FROM"):
            self.assertNotIn(forbidden, text.upper())
        # The handoff shape is inert data; it must not reach into the
        # database or the learning engine itself.
        self.assertNotIn("import sqlite3", text)
        self.assertNotIn("from src import db", text)


if __name__ == "__main__":
    unittest.main()
