from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from src import db
from src.collections import (
    CrossCardMoveConfirmationRequired,
    add_entries_to_collection,
    add_entries_to_system_collection,
    create_collection,
    is_entry_in_system_collection,
)
from src.entries import add_entry
from src.ui_desktop.controllers.review_controller import ReviewController
from src.ui_desktop.state.preferences import Preferences
from src.ui_desktop.theming.theme_manager import Accent, Appearance, build_stylesheet, resolve_tokens
from src.ui_desktop.theming.tokens import (
    PRESET_SAGE_TEAL,
    THEME_CALM_BLUE_DARK,
    THEME_CALM_BLUE_LIGHT,
    ModeCustomization,
)
from src.ui_desktop.views.review_view import ReviewView


class PatchB2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = Path(self.temp_dir.name) / "patch-b2.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def collection_with_entries(self, count: int, *, card_size: int = 8) -> tuple[int, list[int]]:
        collection_id = create_collection("Synthetic Patch B2", "", card_size=card_size)
        entry_ids = [
            add_entry("English", "English", "word", f"term-{index}", f"meaning-{index}")
            for index in range(count)
        ]
        add_entries_to_collection(entry_ids, collection_id)
        return collection_id, entry_ids


class ManualProficientMutationTests(PatchB2TestCase):
    def test_add_and_remove_change_only_membership_and_preserve_study_state(self) -> None:
        collection_id, entry_ids = self.collection_with_entries(2)
        controller = ReviewController(preferences=Preferences(include_proficient_in_study=True))
        self.assertTrue(controller.open_card(collection_id, 1))
        current_before = controller.current_entry()
        progress_before = controller.entry_progress()
        visited_before = set(controller._visited_entry_ids)

        self.assertTrue(controller.toggle_current_entry_proficient())
        self.assertTrue(is_entry_in_system_collection(entry_ids[0], "proficient_pool"))
        self.assertEqual(controller.current_entry(), current_before)
        self.assertEqual(controller.entry_progress(), progress_before)
        self.assertEqual(controller._visited_entry_ids, visited_before)

        self.assertFalse(controller.toggle_current_entry_proficient())
        self.assertFalse(is_entry_in_system_collection(entry_ids[0], "proficient_pool"))
        self.assertEqual(controller.current_entry(), current_before)
        self.assertEqual(controller.entry_progress(), progress_before)
        self.assertEqual(controller._visited_entry_ids, visited_before)

    def test_remove_keeps_cross_card_confirmation_gate(self) -> None:
        collection_id, entry_ids = self.collection_with_entries(9)
        add_entries_to_system_collection(entry_ids, "proficient_pool")
        controller = ReviewController()
        self.assertTrue(controller.open_card(collection_id, 1))

        with self.assertRaises(CrossCardMoveConfirmationRequired):
            controller.toggle_current_entry_proficient()
        self.assertTrue(is_entry_in_system_collection(entry_ids[0], "proficient_pool"))

        self.assertFalse(controller.toggle_current_entry_proficient(confirm_cross_card=True))
        self.assertFalse(is_entry_in_system_collection(entry_ids[0], "proficient_pool"))

    def test_filter_off_moves_to_next_entry_without_marking_it_visited(self) -> None:
        collection_id, entry_ids = self.collection_with_entries(3)
        controller = ReviewController(preferences=Preferences(include_proficient_in_study=False))
        self.assertTrue(controller.open_card(collection_id, 1))
        visited_before = set(controller._visited_entry_ids)

        self.assertTrue(controller.toggle_current_entry_proficient())

        self.assertEqual([entry["id"] for entry in controller.entries()], entry_ids[1:])
        self.assertEqual(controller.current_entry()["id"], entry_ids[1])
        self.assertEqual(controller.entry_index(), 0)
        self.assertEqual(controller.entry_progress(), (1, 2))
        self.assertEqual(controller._visited_entry_ids, visited_before)

    def test_filter_off_last_entry_reaches_honest_empty_state(self) -> None:
        collection_id, entry_ids = self.collection_with_entries(1)
        controller = ReviewController(preferences=Preferences(include_proficient_in_study=False))
        view = ReviewView(controller)
        self.addCleanup(view.deleteLater)
        self.assertTrue(controller.open_card(collection_id, 1))

        self.assertTrue(controller.toggle_current_entry_proficient())

        self.assertEqual(controller.entries(), [])
        self.assertIsNone(controller.current_entry())
        self.assertEqual(controller.entry_progress(), (0, 0))
        self.assertTrue(controller.is_current_card_all_proficient())
        labels = [label.text() for label in view.findChildren(QLabel)]
        self.assertTrue(any("marked as proficient" in text for text in labels))


class ManualProficientControlTests(PatchB2TestCase):
    def test_compact_paired_controls_and_theme_tokens(self) -> None:
        collection_id, _entry_ids = self.collection_with_entries(1)
        controller = ReviewController()
        view = ReviewView(controller)
        self.addCleanup(view.deleteLater)
        self.assertTrue(controller.open_card(collection_id, 1))

        star = view.findChild(QPushButton, "review-current-entry-star-button")
        proficient = view.findChild(QPushButton, "review-current-entry-proficient-button")
        self.assertIsNotNone(star)
        self.assertIsNotNone(proficient)
        self.assertTrue(star.property("learningEntryAction"))
        self.assertTrue(proficient.property("learningEntryAction"))
        self.assertLess(star.minimumHeight(), 40)
        self.assertLess(proficient.minimumHeight(), 40)
        self.assertEqual(proficient.text(), "→ Proficient")

        proficient.click()
        self.assertEqual(proficient.text(), "✓ Proficient")

        preset_tokens = resolve_tokens(Appearance.LIGHT, Accent.INDIGO_VIOLET)
        custom_tokens = resolve_tokens(
            Appearance.DARK,
            customization=ModeCustomization(
                preset=PRESET_SAGE_TEAL,
                accent_color="#B76A2A",
            ),
        )
        for tokens in (
            THEME_CALM_BLUE_LIGHT,
            THEME_CALM_BLUE_DARK,
            preset_tokens,
            custom_tokens,
        ):
            stylesheet = build_stylesheet(tokens)
            self.assertIn('QPushButton[learningProficient="true"][proficient="false"]', stylesheet)
            self.assertIn('QPushButton[learningProficient="true"][proficient="true"]', stylesheet)
            self.assertIn(f"background-color: {tokens.accent.primary.background};", stylesheet)
            self.assertIn(f"color: {tokens.accent.primary.foreground};", stylesheet)
            self.assertIn(f"color: {tokens.semantic.star.background};", stylesheet)


if __name__ == "__main__":
    unittest.main()
