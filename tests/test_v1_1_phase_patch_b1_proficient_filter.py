from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication, QCheckBox, QLabel

from src.collections import (
    add_entries_to_collection,
    add_entries_to_system_collection,
    create_collection,
    get_card_entries_for_study,
    get_card_groups_for_collection,
    get_or_create_system_collection,
    is_system_collection_id,
)
from src import db
from src.entries import add_entry, create_entry_with_template
from src.entry_templates import (
    ensure_french_noun_gender_plural_template,
    ensure_french_verb_present_template,
)
from src.quiz import (
    generate_mcq_items,
    get_entries_for_quiz,
    get_quiz_session,
)
from src.template_quiz import (
    generate_template_multi_rule_quiz_items,
    get_available_template_quiz_sources_for_card,
    get_entries_for_template_quiz_card,
    get_template_quiz_rules,
)
from src.ui_desktop.controllers.quiz_controller import QuizController
from src.ui_desktop.controllers.review_controller import ReviewController
from src.ui_desktop.controllers.settings_controller import SettingsController
from src.ui_desktop.state.handoff import QuizLaunchIntent
from src.ui_desktop.state.preferences import Preferences, load_preferences, save_preferences
from src.ui_desktop.views.review_view import ReviewView
from src.ui_desktop.views.settings_view import SettingsView


class TestProficientPoolSemanticsAndFilter(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = Path(self.temp_dir.name) / "test_vocab.db"
        db.init_db()

        # Create sample entries in a collection
        self.col_id = create_collection("French Vocab", "French words")
        self.entry_ids = []
        for i in range(1, 9):
            eid = add_entry(
                language="French",
                explanation_language="English",
                entry_type="word",
                term=f"mot_{i}",
                meaning=f"word_{i}",
                example=f"Exemple {i}",
            )
            self.entry_ids.append(eid)
        add_entries_to_collection(self.entry_ids, self.col_id)

        # Create system collections
        self.proficient_pool_id = get_or_create_system_collection("proficient_pool", "Proficient Pool")
        self.starred_pool_id = get_or_create_system_collection("starred", "Starred")
        self.mistake_pool_id = get_or_create_system_collection("mistake_book", "Mistake Book")

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    # -- 1. Preferences & Upgrade Compatibility ----------------------------

    def test_preferences_default_and_upgrade_safety(self) -> None:
        prefs = Preferences()
        self.assertTrue(prefs.include_proficient_in_study)

        # Old JSON payload without include_proficient_in_study
        old_json_path = Path(self.temp_dir.name) / "old_prefs.json"
        old_json_path.write_text(json.dumps({"appearance": "Dark", "accent": "Calm Blue"}), encoding="utf-8")

        loaded = load_preferences(old_json_path)
        self.assertTrue(loaded.include_proficient_in_study)
        self.assertEqual(loaded.appearance, "Dark")

        # Round-trip with False
        prefs_false = Preferences(include_proficient_in_study=False)
        save_path = Path(self.temp_dir.name) / "prefs_false.json"
        save_preferences(prefs_false, save_path)

        loaded_false = load_preferences(save_path)
        self.assertFalse(loaded_false.include_proficient_in_study)

        # Malformed non-bool value
        malformed_path = Path(self.temp_dir.name) / "malformed.json"
        malformed_path.write_text(json.dumps({"include_proficient_in_study": "invalid_str"}), encoding="utf-8")
        loaded_malformed = load_preferences(malformed_path)
        self.assertTrue(loaded_malformed.include_proficient_in_study)

    # -- 2. Membership Invariance ------------------------------------------

    def test_proficient_pool_preserves_card_and_collection_membership(self) -> None:
        # Add 2 entries to proficient pool
        add_entries_to_system_collection([self.entry_ids[0], self.entry_ids[1]], "proficient_pool")

        # Original Card structure in collection is intact
        groups = get_card_groups_for_collection(self.col_id)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["card_number"], 1)
        # All 5 entries remain in the collection card group
        entry_ids_in_card = [e["id"] for e in groups[0]["entries"]]
        self.assertEqual(entry_ids_in_card, self.entry_ids)

    # -- 3. Card Study Filtering & System Pool Protection ------------------

    def test_get_card_entries_for_study_filtering_and_system_protection(self) -> None:
        # Mark entry 1 and 2 as proficient
        add_entries_to_system_collection([self.entry_ids[0], self.entry_ids[1]], "proficient_pool")

        # Regular collection with include_proficient=True (default)
        entries_all = get_card_entries_for_study(self.col_id, 1, include_proficient=True)
        self.assertEqual(len(entries_all), 8)

        # Regular collection with include_proficient=False
        entries_filtered = get_card_entries_for_study(self.col_id, 1, include_proficient=False)
        self.assertEqual(len(entries_filtered), 6)
        self.assertEqual([e["id"] for e in entries_filtered], self.entry_ids[2:])

        # System collections are NEVER filtered even with include_proficient=False
        self.assertTrue(is_system_collection_id(self.proficient_pool_id))
        self.assertTrue(is_system_collection_id(self.starred_pool_id))
        self.assertFalse(is_system_collection_id(self.col_id))

        proficient_entries = get_card_entries_for_study(self.proficient_pool_id, 1, include_proficient=False)
        self.assertEqual(len(proficient_entries), 2)

    # -- 4. Quiz Generation Filtering --------------------------------------

    def test_plain_quiz_generation_respects_filter(self) -> None:
        add_entries_to_system_collection([self.entry_ids[0], self.entry_ids[1]], "proficient_pool")

        # Self-graded entries
        quiz_entries_default = get_entries_for_quiz(self.col_id, 1, include_proficient=True)
        self.assertEqual(len(quiz_entries_default), 8)

        quiz_entries_filtered = get_entries_for_quiz(self.col_id, 1, include_proficient=False)
        self.assertEqual(len(quiz_entries_filtered), 6)

        # MCQ items
        mcq_items_default = generate_mcq_items(self.col_id, 1, "term_to_meaning_mcq", include_proficient=True)
        self.assertEqual(len(mcq_items_default), 8)

        mcq_items_filtered = generate_mcq_items(self.col_id, 1, "term_to_meaning_mcq", include_proficient=False)
        self.assertEqual(len(mcq_items_filtered), 6)

    def test_template_quiz_generation_respects_filter(self) -> None:
        tpl_col_id = create_collection("Verb Collection", "")
        template_id = ensure_french_verb_present_template()
        t_entry_ids = []
        for i in range(1, 4):
            eid = create_entry_with_template(
                entry_data={
                    "template_id": template_id,
                    "language": "French",
                    "explanation_language": "English",
                    "entry_type": "word",
                    "status": "new",
                },
                template_values={
                    "term": f"verb_{i}",
                    "meaning": f"meaning_{i}",
                    "infinitive": f"inf_{i}",
                    "je": f"je_{i}",
                    "tu": f"tu_{i}",
                    "il_elle_on": f"il_{i}",
                    "nous": f"nous_{i}",
                    "vous": f"vous_{i}",
                    "ils_elles": f"ils_{i}",
                },
            )
            t_entry_ids.append(eid)
        add_entries_to_collection(t_entry_ids, tpl_col_id)

        # Mark first verb entry as proficient
        add_entries_to_system_collection([t_entry_ids[0]], "proficient_pool")

        sources_filtered = get_available_template_quiz_sources_for_card(tpl_col_id, 1, include_proficient=False)
        self.assertEqual(len(sources_filtered), 1)
        self.assertEqual(sources_filtered[0]["entry_count"], 2)

        card_entries_filtered = get_entries_for_template_quiz_card(tpl_col_id, 1, template_id, include_proficient=False)
        self.assertEqual(len(card_entries_filtered), 2)
        self.assertEqual([e["id"] for e in card_entries_filtered], [t_entry_ids[1], t_entry_ids[2]])

        rules = get_template_quiz_rules("french_verb_present")[:1]
        generation = generate_template_multi_rule_quiz_items(
            tpl_col_id,
            1,
            template_id,
            rules,
            "template_field_self_graded",
            include_proficient=False,
        )
        self.assertEqual(len(generation["quiz_items"]), 2)

    # -- 5. All-Proficient Card Honest Boundary ----------------------------

    def test_all_proficient_card_in_review_controller_and_view(self) -> None:
        # Mark all entries in the collection as proficient
        add_entries_to_system_collection(self.entry_ids, "proficient_pool")

        prefs_false = Preferences(include_proficient_in_study=False)
        controller = ReviewController(preferences=prefs_false)
        view = ReviewView(controller)
        opened = controller.open_card(self.col_id, 1)
        self.assertTrue(opened)

        self.assertEqual(len(controller.entries()), 0)
        self.assertEqual(controller.entry_progress(), (0, 0))
        self.assertIsNone(controller.current_entry())
        self.assertTrue(controller.is_current_card_all_proficient())

        labels = [lbl.text() for lbl in view.findChildren(QLabel)]
        self.assertTrue(any("marked as proficient" in text for text in labels))

    def test_all_proficient_card_in_quiz_controller_start(self) -> None:
        add_entries_to_system_collection(self.entry_ids, "proficient_pool")

        prefs_false = Preferences(include_proficient_in_study=False)
        controller = QuizController(preferences=prefs_false)

        intent = QuizLaunchIntent(
            source="review_quick_quiz",
            collection_id=self.col_id,
            collection_name="French Vocab",
            card_number=1,
            card_id=None,
            quiz_type="term_to_meaning",
            item_count=5,
            reason="Test",
        )

        started = controller.start(intent)
        self.assertFalse(started)
        self.assertIsNotNone(controller.start_error)
        self.assertIn("marked as proficient", controller.start_error)
        self.assertIsNone(controller.session_id)

    def test_non_proficient_template_rule_mismatch_does_not_report_all_proficient(self) -> None:
        tpl_col_id = create_collection("Verb Mismatch Col", "")
        verb_template_id = ensure_french_verb_present_template()
        noun_template_id = ensure_french_noun_gender_plural_template()

        # eid1 is a verb template entry
        eid1 = create_entry_with_template(
            entry_data={
                "template_id": verb_template_id,
                "language": "French",
                "explanation_language": "English",
                "entry_type": "word",
                "status": "new",
            },
            template_values={
                "term": "parler",
                "meaning": "to speak",
                "infinitive": "parler",
                "je": "parle",
                "tu": "parles",
                "il_elle_on": "parle",
                "nous": "parlons",
                "vous": "parlez",
                "ils_elles": "parlent",
            },
        )
        # eid2 is a noun template entry (does NOT match verb template rules)
        eid2 = create_entry_with_template(
            entry_data={
                "template_id": noun_template_id,
                "language": "French",
                "explanation_language": "English",
                "entry_type": "word",
                "status": "new",
            },
            template_values={
                "term": "livre",
                "meaning": "book",
                "singular": "livre",
                "gender": "m",
                "plural": "livres",
                "article": "le",
            },
        )
        add_entries_to_collection([eid1, eid2], tpl_col_id)

        # Mark only eid1 as proficient. eid2 remains non-proficient in Card 1.
        add_entries_to_system_collection([eid1], "proficient_pool")

        prefs_false = Preferences(include_proficient_in_study=False)
        controller = QuizController(preferences=prefs_false)

        intent = QuizLaunchIntent(
            source="review_choose_quiz_type",
            collection_id=tpl_col_id,
            collection_name="Verb Mismatch Col",
            card_number=1,
            card_id=None,
            quiz_type="template_field_self_graded",
            item_count=2,
            reason="Test",
            template_id=verb_template_id,
            template_type="french_verb_present",
            template_rule_ids=("infinitive_to_je",),
        )

        # eid2 is non-proficient in Card 1, but cannot generate items for verb_template_id -> 0 items generated
        started = controller.start(intent)
        self.assertFalse(started)
        self.assertIsNotNone(controller.start_error)
        # Must NOT be misattributed to all-proficient because eid2 is still non-proficient!
        self.assertNotIn("marked as proficient", controller.start_error)
        self.assertEqual(controller.start_error, "Not enough entries to build this quiz.")

        # Now mark eid2 as proficient as well -> truly all proficient in this Card
        add_entries_to_system_collection([eid2], "proficient_pool")
        started2 = controller.start(intent)
        self.assertFalse(started2)
        self.assertIsNotNone(controller.start_error)
        self.assertIn("marked as proficient", controller.start_error)

    # -- 6. Settings Controller and View -----------------------------------

    def test_settings_controller_and_view_integration(self) -> None:
        prefs_path = Path(self.temp_dir.name) / "settings_test.json"
        prefs = Preferences(include_proficient_in_study=True)
        save_preferences(prefs, prefs_path)

        controller = SettingsController(preferences=prefs, preferences_path=prefs_path)
        self.assertTrue(controller.include_proficient_in_study())

        signals_emitted = []
        controller.include_proficient_in_study_changed.connect(signals_emitted.append)

        controller.set_include_proficient_in_study(False)
        self.assertFalse(controller.include_proficient_in_study())
        self.assertEqual(signals_emitted, [False])

        # Verify disk persistence
        reloaded = load_preferences(prefs_path)
        self.assertFalse(reloaded.include_proficient_in_study)

        # SettingsView UI check
        view = SettingsView(controller)
        checkbox = view.findChild(QCheckBox, "settings-include-proficient-checkbox")
        self.assertIsNotNone(checkbox)
        self.assertFalse(checkbox.isChecked())

        # Toggle UI
        checkbox.setChecked(True)
        self.assertTrue(controller.include_proficient_in_study())


if __name__ == "__main__":
    unittest.main()
