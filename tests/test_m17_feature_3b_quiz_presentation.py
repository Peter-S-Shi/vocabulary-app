from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication, QWidget

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when PySide6 is absent
    PYSIDE6_AVAILABLE = False

from src import db
from src.collections import add_entries_to_collection, create_collection
from src.entries import add_entry
from src.entry_templates import ensure_french_verb_present_template
from src.entries import create_entry_with_template

"""
Focused tests for M17 Feature 3B -- Quiz Presentation Choice (DESIGN.md
§ 6.4 `VR-STUDY-002`, Quiz-only). Per DESIGN.md § 2 Rule C, none of this
proves the canonical Flip Card + Filmstrip composition was *visually*
realized -- only that the preference persists safely, the presentation
choice reaches the right Quiz surface for the right family, Matching's
compatibility fallback never mutates the saved preference, and both
presentations share exactly one QuizController/session (no second Quiz
engine). Native human visual acceptance is a separate, required gate
(AGENTS.md).
"""

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if PYSIDE6_AVAILABLE:
    from src.ui_desktop.controllers.quiz_controller import QuizController
    from src.ui_desktop.controllers.settings_controller import SettingsController
    from src.ui_desktop.main_window import MainWindow
    from src.ui_desktop.state.app_state import ShellMode, Workspace
    from src.ui_desktop.state.handoff import QuizLaunchIntent
    from src.ui_desktop.state.preferences import (
        DEFAULT_QUIZ_PRESENTATION,
        QUIZ_PRESENTATION_FLIP_CARD,
        QUIZ_PRESENTATION_IMMERSIVE,
        Preferences,
        load_preferences,
        parse_quiz_presentation,
        save_preferences,
    )
    from src.ui_desktop.views.quiz_view import QuizView
    from src.ui_desktop.views.review_view import ReviewView
    from src.ui_desktop.views.settings_view import SettingsView

    def _qt_app() -> QApplication:
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app


class _SyntheticDatabaseTestCase(unittest.TestCase):
    """Shared setup matching the existing repository pattern: swap
    db.DB_PATH to a temporary synthetic database, never the user's
    personal data/vocab.db."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp_dir.name)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = self.root / "m17_feature_3b.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _make_card(self, terms, card_size=None, collection_name="Feature 3B Collection"):
        entry_ids = [add_entry("French", "English", "word", term, meaning) for term, meaning in terms]
        collection_id = create_collection(collection_name, card_size=card_size or len(entry_ids))
        add_entries_to_collection(entry_ids, collection_id)
        return collection_id, entry_ids

    def _quick_intent(self, collection_id, card_number, card_id, entry_count, quiz_type="term_to_meaning"):
        return QuizLaunchIntent(
            source="test",
            collection_id=collection_id,
            collection_name="",
            card_number=card_number,
            card_id=card_id,
            quiz_type=quiz_type,
            item_count=entry_count,
            reason="test",
        )


class QuizPresentationPreferenceTests(unittest.TestCase):
    """`state/preferences.py`'s quiz_presentation field: same fail-safe
    load/save discipline already established for Appearance/Accent/Motion
    (M17 Feature 3B prompt § 5/§ 21)."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.path = Path(self.temp_dir.name) / "preferences.json"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_default_is_immersive_focus(self) -> None:
        self.assertEqual(DEFAULT_QUIZ_PRESENTATION, QUIZ_PRESENTATION_IMMERSIVE)
        preferences = load_preferences(self.path)
        self.assertEqual(preferences.quiz_presentation, QUIZ_PRESENTATION_IMMERSIVE)

    def test_old_preferences_file_without_quiz_presentation_key_stays_valid(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"appearance": "Dark", "accent": "Calm Blue"}), encoding="utf-8")

        preferences = load_preferences(self.path)

        self.assertEqual(preferences.appearance, "Dark")
        self.assertEqual(preferences.quiz_presentation, QUIZ_PRESENTATION_IMMERSIVE)

    def test_round_trip_save_and_load_flip_card_choice(self) -> None:
        save_preferences(Preferences(quiz_presentation=QUIZ_PRESENTATION_FLIP_CARD), self.path)

        loaded = load_preferences(self.path)

        self.assertEqual(loaded.quiz_presentation, QUIZ_PRESENTATION_FLIP_CARD)

    def test_malformed_value_fails_safely_to_default(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"quiz_presentation": "some_unknown_value"}), encoding="utf-8")

        preferences = load_preferences(self.path)

        self.assertEqual(preferences.quiz_presentation, QUIZ_PRESENTATION_IMMERSIVE)

    def test_parse_quiz_presentation_rejects_unknown_values(self) -> None:
        self.assertEqual(parse_quiz_presentation(QUIZ_PRESENTATION_FLIP_CARD), QUIZ_PRESENTATION_FLIP_CARD)
        self.assertEqual(parse_quiz_presentation("nonsense"), QUIZ_PRESENTATION_IMMERSIVE)
        self.assertEqual(parse_quiz_presentation(""), QUIZ_PRESENTATION_IMMERSIVE)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class SettingsControllerTests(unittest.TestCase):
    """`SettingsController` wraps the existing preferences persistence
    mechanism (M17 Feature 3B prompt § 5) -- no second settings file, no
    vocab.db writes."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.preferences_path = Path(self.temp_dir.name) / "preferences.json"
        self._previous_env = os.environ.get("VOCAB_APP_PREFERENCES_PATH")
        os.environ["VOCAB_APP_PREFERENCES_PATH"] = str(self.preferences_path)

    def tearDown(self) -> None:
        if self._previous_env is None:
            os.environ.pop("VOCAB_APP_PREFERENCES_PATH", None)
        else:
            os.environ["VOCAB_APP_PREFERENCES_PATH"] = self._previous_env
        self.temp_dir.cleanup()

    def test_quiz_presentation_reflects_constructed_preferences(self) -> None:
        controller = SettingsController(Preferences(quiz_presentation=QUIZ_PRESENTATION_FLIP_CARD))
        self.assertEqual(controller.quiz_presentation(), QUIZ_PRESENTATION_FLIP_CARD)

    def test_set_quiz_presentation_persists_to_disk_and_emits_state_changed(self) -> None:
        controller = SettingsController()
        received: list[None] = []
        controller.state_changed.connect(lambda: received.append(None))

        controller.set_quiz_presentation(QUIZ_PRESENTATION_FLIP_CARD)

        self.assertEqual(controller.quiz_presentation(), QUIZ_PRESENTATION_FLIP_CARD)
        self.assertEqual(len(received), 1)
        reloaded = load_preferences(self.preferences_path)
        self.assertEqual(reloaded.quiz_presentation, QUIZ_PRESENTATION_FLIP_CARD)

    def test_set_quiz_presentation_malformed_value_falls_back_safely(self) -> None:
        controller = SettingsController()

        controller.set_quiz_presentation("not_a_real_presentation")

        self.assertEqual(controller.quiz_presentation(), QUIZ_PRESENTATION_IMMERSIVE)

    def test_set_quiz_presentation_is_a_no_op_when_unchanged(self) -> None:
        controller = SettingsController(Preferences(quiz_presentation=QUIZ_PRESENTATION_IMMERSIVE))
        received: list[None] = []
        controller.state_changed.connect(lambda: received.append(None))

        controller.set_quiz_presentation(QUIZ_PRESENTATION_IMMERSIVE)

        self.assertEqual(len(received), 0)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class SettingsViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.preferences_path = Path(self.temp_dir.name) / "preferences.json"
        self._previous_env = os.environ.get("VOCAB_APP_PREFERENCES_PATH")
        os.environ["VOCAB_APP_PREFERENCES_PATH"] = str(self.preferences_path)

    def tearDown(self) -> None:
        if self._previous_env is None:
            os.environ.pop("VOCAB_APP_PREFERENCES_PATH", None)
        else:
            os.environ["VOCAB_APP_PREFERENCES_PATH"] = self._previous_env
        self.temp_dir.cleanup()

    def test_shows_the_current_quiz_presentation(self) -> None:
        controller = SettingsController(Preferences(quiz_presentation=QUIZ_PRESENTATION_FLIP_CARD))
        view = SettingsView(controller)
        self.addCleanup(view.deleteLater)

        self.assertEqual(view._quiz_presentation_combo.currentText(), "Flip Card + Filmstrip")

    def test_changing_selection_persists_via_controller(self) -> None:
        controller = SettingsController()
        view = SettingsView(controller)
        self.addCleanup(view.deleteLater)

        index = view._quiz_presentation_combo.findData(QUIZ_PRESENTATION_FLIP_CARD)
        view._quiz_presentation_combo.setCurrentIndex(index)

        self.assertEqual(controller.quiz_presentation(), QUIZ_PRESENTATION_FLIP_CARD)
        reloaded = load_preferences(self.preferences_path)
        self.assertEqual(reloaded.quiz_presentation, QUIZ_PRESENTATION_FLIP_CARD)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class QuizPresentationDispatchTests(_SyntheticDatabaseTestCase):
    """QuizView's presentation dispatch: the exact same QuizController
    state renders through either surface depending on ``set_presentation``
    (M17 Feature 3B prompt § 16) -- never a second Quiz engine."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def _object_names(self, view: QuizView) -> set[str]:
        return {w.objectName() for w in view.findChildren(QWidget) if w.objectName()}

    def test_default_presentation_before_set_presentation_is_immersive(self) -> None:
        collection_id, _ = self._make_card([("chat", "cat")])
        controller = QuizController()
        view = QuizView(controller)
        self.addCleanup(view.deleteLater)

        controller.start(self._quick_intent(collection_id, 1, None, 1))

        names = self._object_names(view)
        self.assertIn("quiz-show-answer-button", names)
        self.assertNotIn("quiz-flip-card-front", names)
        self.assertNotIn("quiz-filmstrip", names)

    def test_immersive_presentation_selects_the_accepted_immersive_self_graded_surface(self) -> None:
        collection_id, _ = self._make_card([("chat", "cat")])
        controller = QuizController()
        view = QuizView(controller)
        self.addCleanup(view.deleteLater)

        view.set_presentation(QUIZ_PRESENTATION_IMMERSIVE)
        controller.start(self._quick_intent(collection_id, 1, None, 1))

        names = self._object_names(view)
        self.assertIn("quiz-show-answer-button", names)
        self.assertNotIn("quiz-flip-card-front", names)
        self.assertNotIn("quiz-filmstrip", names)

    def test_flip_card_presentation_selects_vr_study_002_for_self_graded(self) -> None:
        collection_id, _ = self._make_card([("chat", "cat")])
        controller = QuizController()
        view = QuizView(controller)
        self.addCleanup(view.deleteLater)

        view.set_presentation(QUIZ_PRESENTATION_FLIP_CARD)
        controller.start(self._quick_intent(collection_id, 1, None, 1))

        names = self._object_names(view)
        self.assertIn("quiz-flip-card-front", names)
        self.assertIn("quiz-filmstrip", names)
        # Same answer-entry mechanism as Immersive Focus -- one Quiz engine.
        self.assertIn("quiz-show-answer-button", names)

        controller.reveal_answer()
        names = self._object_names(view)
        self.assertIn("quiz-flip-card-revealed", names)
        self.assertIn("quiz-grade-correct-button", names)

    def test_flip_card_presentation_selects_vr_study_002_for_mcq(self) -> None:
        collection_id, _ = self._make_card(
            [("un", "one"), ("deux", "two"), ("trois", "three"), ("quatre", "four"), ("cinq", "five")]
        )
        controller = QuizController()
        view = QuizView(controller)
        self.addCleanup(view.deleteLater)

        view.set_presentation(QUIZ_PRESENTATION_FLIP_CARD)
        controller.start(self._quick_intent(collection_id, 1, None, 5, "term_to_meaning_mcq"))

        names = self._object_names(view)
        self.assertIn("quiz-flip-card-front", names)
        self.assertIn("quiz-filmstrip", names)
        self.assertIn("quiz-mcq-option", names)

        item = controller.current_item()
        controller.submit_mcq(item["correct_answer"])
        names = self._object_names(view)
        self.assertIn("quiz-flip-card-revealed", names)
        self.assertIn("quiz-feedback-correct", names)

    def test_flip_card_presentation_applies_to_template_linear_self_graded(self) -> None:
        template_id = ensure_french_verb_present_template()
        entry_id = create_entry_with_template(
            entry_data={
                "template_id": template_id,
                "language": "French",
                "explanation_language": "English",
                "entry_type": "verb",
            },
            template_values={
                "infinitive": "parler",
                "meaning": "to speak",
                "je": "parle",
                "tu": "parle",
                "il_elle_on": "parle",
                "nous": "parle",
                "vous": "parle",
                "ils_elles": "parle",
            },
        )
        collection_id = create_collection("Template Collection", card_size=1)
        add_entries_to_collection([entry_id], collection_id)

        controller = QuizController()
        view = QuizView(controller)
        self.addCleanup(view.deleteLater)
        view.set_presentation(QUIZ_PRESENTATION_FLIP_CARD)
        controller.start(
            QuizLaunchIntent(
                source="test",
                collection_id=collection_id,
                collection_name="",
                card_number=1,
                card_id=None,
                quiz_type="template_field_self_graded",
                item_count=1,
                reason="test",
                template_id=template_id,
                template_type="french_verb_present",
                template_rule_ids=("infinitive_to_je",),
            )
        )

        names = self._object_names(view)
        self.assertIn("quiz-flip-card-front", names)
        self.assertIn("quiz-filmstrip", names)

    def test_matching_falls_back_to_immersive_even_with_flip_card_selected(self) -> None:
        collection_id, _ = self._make_card(
            [("un", "one"), ("deux", "two"), ("trois", "three"), ("quatre", "four")]
        )
        controller = QuizController()
        view = QuizView(controller)
        self.addCleanup(view.deleteLater)

        view.set_presentation(QUIZ_PRESENTATION_FLIP_CARD)
        controller.start(self._quick_intent(collection_id, 0, None, 4, "matching"))

        names = self._object_names(view)
        self.assertIn("quiz-matching-row", names)
        self.assertNotIn("quiz-flip-card-front", names)
        self.assertNotIn("quiz-flip-card-revealed", names)
        self.assertNotIn("quiz-filmstrip", names)

    def test_matching_fallback_does_not_alter_the_saved_view_presentation(self) -> None:
        collection_id, _ = self._make_card(
            [("un", "one"), ("deux", "two"), ("trois", "three"), ("quatre", "four")]
        )
        controller = QuizController()
        view = QuizView(controller)
        self.addCleanup(view.deleteLater)

        view.set_presentation(QUIZ_PRESENTATION_FLIP_CARD)
        controller.start(self._quick_intent(collection_id, 0, None, 4, "matching"))

        # The view's own resolved choice for this session is untouched --
        # only Matching's *rendering* fell back, per the compatibility rule.
        self.assertEqual(view._presentation, QUIZ_PRESENTATION_FLIP_CARD)

    def test_completion_state_is_shared_regardless_of_presentation(self) -> None:
        collection_id, _ = self._make_card([("chat", "cat")])
        controller = QuizController()
        view = QuizView(controller)
        self.addCleanup(view.deleteLater)

        view.set_presentation(QUIZ_PRESENTATION_FLIP_CARD)
        controller.start(self._quick_intent(collection_id, 1, None, 1))
        controller.reveal_answer()
        controller.submit_self_graded(True)
        # _clear_layout() schedules the old Flip Card/filmstrip widgets for
        # deletion via deleteLater() -- a plain processEvents() alone does
        # not flush DeferredDelete; sendPostedEvents() does, so the old
        # widgets are actually gone before asserting their absence, not
        # just unparented from the layout.
        self.app.processEvents()
        self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()

        names = self._object_names(view)
        self.assertIn("quiz-completion-title", names)
        self.assertNotIn("quiz-flip-card-front", names)
        self.assertNotIn("quiz-flip-card-revealed", names)
        self.assertNotIn("quiz-filmstrip", names)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class MainWindowQuizPresentationIntegrationTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def setUp(self) -> None:
        super().setUp()
        self.temp_dir_prefs = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.preferences_path = Path(self.temp_dir_prefs.name) / "preferences.json"
        self._previous_env = os.environ.get("VOCAB_APP_PREFERENCES_PATH")
        os.environ["VOCAB_APP_PREFERENCES_PATH"] = str(self.preferences_path)

    def tearDown(self) -> None:
        if self._previous_env is None:
            os.environ.pop("VOCAB_APP_PREFERENCES_PATH", None)
        else:
            os.environ["VOCAB_APP_PREFERENCES_PATH"] = self._previous_env
        self.temp_dir_prefs.cleanup()
        super().tearDown()

    def _add_mcq_ready_card(self, collection_name: str = "Feature 3B Rail Collection") -> int:
        entry_ids = [
            add_entry("French", "English", "word", term, meaning)
            for term, meaning in (("un", "one"), ("deux", "two"), ("trois", "three"), ("quatre", "four"))
        ]
        collection_id = create_collection(collection_name, card_size=4)
        add_entries_to_collection(entry_ids, collection_id)
        return collection_id

    def test_settings_reachable_from_navigation_rail(self) -> None:
        window = MainWindow()
        self.addCleanup(window.close)
        window.show()
        self.app.processEvents()

        window._navigation_rail._buttons["settings"].click()

        self.assertIs(window.current_workspace(), Workspace.SETTINGS)
        self.assertIs(window.app_state.mode, ShellMode.MANAGEMENT)
        self.assertIs(window._workspace_stack.currentWidget(), window.settings_view)

    def test_main_window_uses_saved_presentation_for_quiz_launch(self) -> None:
        collection_id = self._add_mcq_ready_card()
        window = MainWindow(preferences=Preferences(quiz_presentation=QUIZ_PRESENTATION_FLIP_CARD))
        self.addCleanup(window.close)
        window.show()
        self.app.processEvents()

        window._start_quiz(
            QuizLaunchIntent(
                source="test",
                collection_id=collection_id,
                collection_name="Feature 3B Rail Collection",
                card_number=1,
                card_id=None,
                quiz_type="mixed_mcq",
                item_count=4,
                reason="test",
            )
        )

        names = {w.objectName() for w in window.quiz_view.findChildren(QWidget) if w.objectName()}
        self.assertIn("quiz-flip-card-front", names)

    def test_changing_settings_affects_the_next_quiz_launch_within_the_same_session(self) -> None:
        collection_id = self._add_mcq_ready_card()
        window = MainWindow()  # defaults to Immersive Focus
        self.addCleanup(window.close)
        window.show()
        self.app.processEvents()

        window.settings_controller.set_quiz_presentation(QUIZ_PRESENTATION_FLIP_CARD)

        window._start_quiz(
            QuizLaunchIntent(
                source="test",
                collection_id=collection_id,
                collection_name="Feature 3B Rail Collection",
                card_number=1,
                card_id=None,
                quiz_type="mixed_mcq",
                item_count=4,
                reason="test",
            )
        )

        names = {w.objectName() for w in window.quiz_view.findChildren(QWidget) if w.objectName()}
        self.assertIn("quiz-flip-card-front", names)

    def test_review_has_no_flip_card_controls_and_stays_immersive(self) -> None:
        self._make_card([("chat", "cat"), ("chien", "dog")])
        window = MainWindow(preferences=Preferences(quiz_presentation=QUIZ_PRESENTATION_FLIP_CARD))
        self.addCleanup(window.close)
        window.show()
        self.app.processEvents()

        window._navigation_rail._buttons["study"].click()

        self.assertIs(window.current_workspace(), Workspace.REVIEW)
        names = {w.objectName() for w in window.review_view.findChildren(QWidget) if w.objectName()}
        self.assertIn("review-term-label", names)
        for flip_card_name in ("quiz-flip-card-front", "quiz-flip-card-revealed", "quiz-filmstrip"):
            self.assertNotIn(flip_card_name, names)

    def test_settings_activation_does_not_change_management_shell_behavior(self) -> None:
        window = MainWindow()
        self.addCleanup(window.close)
        window.show()
        self.app.processEvents()

        window._navigation_rail._buttons["settings"].click()

        self.assertTrue(window._navigation_rail.isVisible())
        self.assertIs(window.app_state.mode, ShellMode.MANAGEMENT)
        self.assertFalse(window._study_toolbar.isVisible())

    def test_preference_persists_across_a_simulated_restart(self) -> None:
        window = MainWindow()
        self.addCleanup(window.close)
        window.show()
        self.app.processEvents()
        window.settings_controller.set_quiz_presentation(QUIZ_PRESENTATION_FLIP_CARD)

        # A restart re-reads preferences.json from disk exactly as
        # app.py's build_application() does at bootstrap.
        reloaded_preferences = load_preferences(self.preferences_path)
        second_window = MainWindow(preferences=reloaded_preferences)
        self.addCleanup(second_window.close)

        self.assertEqual(second_window.settings_controller.quiz_presentation(), QUIZ_PRESENTATION_FLIP_CARD)


if __name__ == "__main__":
    unittest.main()
