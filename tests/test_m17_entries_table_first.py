from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QPlainTextEdit, QWidget

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when PySide6 is absent
    PYSIDE6_AVAILABLE = False

from src import db
from src.collections import (
    CrossCardMoveConfirmationRequired,
    add_entries_to_collection,
    create_collection,
    get_entries_in_collection,
)
from src.entries import add_entry, get_entry_by_id, get_entry_change_events
from src.entry_templates import ensure_french_verb_present_template

"""
Focused tests for M17 Feature 4 -- Entries / Table-First Manager
(DESIGN.md § 6.2 `VR-ENTRIES-001`, parent pattern P2). Per DESIGN.md § 2
Rule C, none of this proves the canonical composition was *visually*
realized -- only that scope/filter/selection/create/edit/delete contracts
match existing reusable core exactly, that no business logic or SQL was
duplicated in the desktop layer, and that CrossCardMoveConfirmationRequired
is never bypassed. Native human visual acceptance is a separate, required
gate (AGENTS.md).
"""

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if PYSIDE6_AVAILABLE:
    from src.ui_desktop.controllers.entries_controller import SCOPE_ALL, EntriesController
    from src.ui_desktop.main_window import MainWindow
    from src.ui_desktop.state.app_state import Workspace
    from src.ui_desktop.views.entries_view import (
        EntriesView,
        _EntryEditorDialog,
        _QuickAddDialog,
        _confirm_cross_card_reorganization,
    )

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
        db.DB_PATH = self.root / "m17_entries.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _make_entries(self, terms) -> list[int]:
        return [add_entry("French", "English", "word", term, meaning) for term, meaning in terms]

    def _collection_with_entries(self, count: int, card_size: int) -> tuple[int, list[int]]:
        """A collection whose card composition genuinely spans a Card
        boundary, matching the pattern already used by
        tests/test_m11_3_card_history.py to exercise
        CrossCardMoveConfirmationRequired -- built entirely through public
        core API (create_collection/add_entry/add_entries_to_collection),
        no raw SQL."""
        entry_ids = self._make_entries([(f"term{i}", f"meaning{i}") for i in range(count)])
        collection_id = create_collection(f"Synthetic {count}-{card_size}", card_size=card_size)
        add_entries_to_collection(entry_ids, collection_id)
        return collection_id, entry_ids


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class EntriesControllerBrowseTests(_SyntheticDatabaseTestCase):
    def test_refresh_projects_search_entries_rows_with_collection_names(self) -> None:
        entry_ids = self._make_entries([("chat", "cat"), ("chien", "dog")])
        collection_id = create_collection("IELTS Core", card_size=2)
        add_entries_to_collection(entry_ids, collection_id)

        controller = EntriesController()
        count = controller.refresh()

        self.assertEqual(count, 2)
        rows = controller.model.rows()
        self.assertEqual({row["term"] for row in rows}, {"chat", "chien"})
        self.assertTrue(all(row["collection_names"] == ["IELTS Core"] for row in rows))

    def test_search_text_filter_matches_core_search_entries_semantics(self) -> None:
        self._make_entries([("resilient", "able to recover"), ("alleviate", "to reduce")])
        controller = EntriesController()
        controller.refresh()

        controller.set_search_text("resil")

        self.assertEqual([row["term"] for row in controller.model.rows()], ["resilient"])

    def test_language_entry_type_status_filters_narrow_results(self) -> None:
        add_entry("French", "English", "word", "mettre", "to put")
        add_entry("English", "English", "phrase", "cope with", "handle")
        controller = EntriesController()
        controller.refresh()

        controller.set_language("French")
        self.assertEqual([row["term"] for row in controller.model.rows()], ["mettre"])

        controller.set_language("All")
        controller.set_entry_type("phrase")
        self.assertEqual([row["term"] for row in controller.model.rows()], ["cope with"])

        controller.set_entry_type("All")
        controller.set_status("new")
        self.assertEqual(len(controller.model.rows()), 2)

    def test_scope_pane_lists_system_and_user_collections(self) -> None:
        create_collection("IELTS Core", card_size=8)
        controller = EntriesController()

        controller.refresh_scopes()

        keys = [scope["key"] for scope in controller.scopes]
        self.assertEqual(keys[0], SCOPE_ALL)
        self.assertIn("system:starred", keys)
        self.assertIn("system:mistake_book", keys)
        self.assertIn("system:proficient_pool", keys)
        self.assertTrue(any(scope["label"] == "IELTS Core" for scope in controller.scopes))

    def test_collection_scope_shows_only_that_collections_entries(self) -> None:
        entry_ids = self._make_entries([("un", "one"), ("deux", "two"), ("trois", "three")])
        collection_id = create_collection("Numbers", card_size=8)
        add_entries_to_collection(entry_ids[:2], collection_id)
        controller = EntriesController()
        controller.refresh()

        controller.set_scope(f"collection:{collection_id}")

        self.assertEqual({row["term"] for row in controller.model.rows()}, {"un", "deux"})

    def test_scope_and_filters_compose(self) -> None:
        entry_ids = self._make_entries([("un", "one"), ("deux", "two")])
        add_entry("English", "English", "word", "one-en", "the number one")
        collection_id = create_collection("Numbers", card_size=8)
        add_entries_to_collection(entry_ids, collection_id)
        controller = EntriesController()
        controller.refresh()

        controller.set_scope(f"collection:{collection_id}")
        controller.set_language("French")

        self.assertEqual({row["term"] for row in controller.model.rows()}, {"un", "deux"})


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class EntriesControllerSelectionTests(_SyntheticDatabaseTestCase):
    def test_single_selection_exposes_primary_entry(self) -> None:
        entry_ids = self._make_entries([("chat", "cat"), ("chien", "dog")])
        controller = EntriesController()
        controller.refresh()

        controller.set_selected_ids({entry_ids[0]})

        self.assertEqual(controller.primary_selected_entry_id(), entry_ids[0])
        self.assertEqual([e["term"] for e in controller.selected_entries()], ["chat"])

    def test_multi_selection_has_no_single_primary_entry(self) -> None:
        entry_ids = self._make_entries([("chat", "cat"), ("chien", "dog")])
        controller = EntriesController()
        controller.refresh()

        controller.set_selected_ids(set(entry_ids))

        self.assertIsNone(controller.primary_selected_entry_id())
        self.assertEqual(len(controller.selected_entries()), 2)

    def test_refresh_prunes_selection_no_longer_visible_but_keeps_the_rest(self) -> None:
        entry_ids = self._make_entries([("chat", "cat"), ("chien", "dog")])
        controller = EntriesController()
        controller.refresh()
        controller.set_selected_ids(set(entry_ids))

        controller.set_search_text("chat")

        self.assertEqual(controller.selected_ids, {entry_ids[0]})

    def test_entry_detail_includes_template_values(self) -> None:
        entry_id = self._make_entries([("chat", "cat")])[0]
        controller = EntriesController()

        detail = controller.entry_detail(entry_id)

        self.assertEqual(detail["term"], "chat")
        self.assertIn("term", detail["template_values"])


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class EntriesControllerCreateTests(_SyntheticDatabaseTestCase):
    def test_general_entry_creation_succeeds_and_appears_in_table(self) -> None:
        controller = EntriesController()
        controller.refresh()
        template_id = controller.default_template_id()

        entry_id, errors = controller.create_entry(
            {"template_id": template_id, "language": "English", "explanation_language": "Chinese", "entry_type": "word", "status": "new"},
            {"term": "resilient", "meaning": "able to recover quickly", "example": "", "notes": "", "tags": "", "source": ""},
            "",
            "",
            [],
        )

        self.assertEqual(errors, [])
        self.assertIsNotNone(entry_id)
        self.assertIn("resilient", [row["term"] for row in controller.model.rows()])

    def test_template_aware_creation_uses_create_entry_with_template(self) -> None:
        template_id = ensure_french_verb_present_template()
        controller = EntriesController()

        entry_id, errors = controller.create_entry(
            {"template_id": template_id, "language": "French", "explanation_language": "English", "entry_type": "verb", "status": "new"},
            {"infinitive": "parler", "meaning": "to speak", "je": "parle", "tu": "parles", "il_elle_on": "parle", "nous": "parlons", "vous": "parlez", "ils_elles": "parlent"},
            "",
            "",
            [],
        )

        self.assertEqual(errors, [])
        entry = get_entry_by_id(entry_id)
        self.assertEqual(entry["term"], "parler")
        self.assertEqual(entry["meaning"], "to speak")

    def test_validation_failure_creates_nothing(self) -> None:
        controller = EntriesController()
        template_id = controller.default_template_id()

        entry_id, errors = controller.create_entry(
            {"template_id": template_id, "language": "", "explanation_language": "English", "entry_type": "word", "status": "new"},
            {"term": "", "meaning": ""},
            "",
            "",
            [],
        )

        self.assertIsNone(entry_id)
        self.assertTrue(errors)
        controller.refresh()
        self.assertEqual(controller.model.rowCount(), 0)

    def test_create_entry_can_attach_to_collections(self) -> None:
        collection_id = create_collection("IELTS Core", card_size=8)
        controller = EntriesController()
        template_id = controller.default_template_id()

        entry_id, errors = controller.create_entry(
            {"template_id": template_id, "language": "English", "explanation_language": "Chinese", "entry_type": "word", "status": "new"},
            {"term": "alleviate", "meaning": "to reduce", "example": "", "notes": "", "tags": "", "source": ""},
            "",
            "",
            [collection_id],
        )

        self.assertEqual(errors, [])
        self.assertIn(entry_id, [row["id"] for row in get_entries_in_collection(collection_id)])

    def test_canonical_mapping_reports_source_fields(self) -> None:
        controller = EntriesController()
        general_id = controller.default_template_id()
        verb_id = ensure_french_verb_present_template()

        general_mapping = controller.canonical_mapping(general_id)
        verb_mapping = controller.canonical_mapping(verb_id)

        self.assertFalse(general_mapping["needs_manual_term"])
        self.assertFalse(general_mapping["needs_manual_meaning"])
        self.assertEqual(verb_mapping["term_source"], "infinitive")


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class EntriesControllerEditTests(_SyntheticDatabaseTestCase):
    def test_template_aware_edit_updates_canonical_fields(self) -> None:
        template_id = ensure_french_verb_present_template()
        controller = EntriesController()
        entry_id, _ = controller.create_entry(
            {"template_id": template_id, "language": "French", "explanation_language": "English", "entry_type": "verb", "status": "new"},
            {"infinitive": "parler", "meaning": "to speak", "je": "parle", "tu": "parles", "il_elle_on": "parle", "nous": "parlons", "vous": "parlez", "ils_elles": "parlent"},
            "",
            "",
            [],
        )

        errors = controller.update_entry_core(
            entry_id,
            {"template_id": template_id, "language": "French", "explanation_language": "English", "entry_type": "verb", "status": "learning"},
            {"infinitive": "parler", "meaning": "to talk", "je": "parle", "tu": "parles", "il_elle_on": "parle", "nous": "parlons", "vous": "parlez", "ils_elles": "parlent"},
            "",
            "",
        )

        self.assertEqual(errors, [])
        entry = get_entry_by_id(entry_id)
        self.assertEqual(entry["meaning"], "to talk")
        self.assertEqual(entry["status"], "learning")

    def test_edit_records_a_change_event_the_ui_never_writes_directly(self) -> None:
        template_id = ensure_french_verb_present_template()
        controller = EntriesController()
        entry_id, _ = controller.create_entry(
            {"template_id": template_id, "language": "French", "explanation_language": "English", "entry_type": "verb", "status": "new"},
            {"infinitive": "parler", "meaning": "to speak", "je": "parle", "tu": "parles", "il_elle_on": "parle", "nous": "parlons", "vous": "parlez", "ils_elles": "parlent"},
            "",
            "",
            [],
        )

        controller.update_entry_core(
            entry_id,
            {"template_id": template_id, "language": "French", "explanation_language": "English", "entry_type": "verb", "status": "learning"},
            {"infinitive": "parler", "meaning": "to speak", "je": "parle", "tu": "parles", "il_elle_on": "parle", "nous": "parlons", "vous": "parlez", "ils_elles": "parlent"},
            "",
            "",
        )

        events = get_entry_change_events(entry_id)
        self.assertGreaterEqual(len(events), 1)

    def test_validation_failure_on_edit_does_not_mutate_the_entry(self) -> None:
        entry_id = self._make_entries([("chat", "cat")])[0]
        controller = EntriesController()
        before = get_entry_by_id(entry_id)

        errors = controller.update_entry_core(
            entry_id,
            {"template_id": before["template_id"], "language": "", "explanation_language": "English", "entry_type": "word", "status": "new"},
            {"term": "chat", "meaning": "cat"},
            "",
            "",
        )

        self.assertTrue(errors)
        after = get_entry_by_id(entry_id)
        self.assertEqual(before, after)

    def test_sync_entry_collections_only_touches_managed_non_system_collections(self) -> None:
        entry_id = self._make_entries([("chat", "cat")])[0]
        collection_id = create_collection("IELTS Core", card_size=8)
        controller = EntriesController()

        controller.sync_entry_collections(entry_id, [collection_id])

        self.assertIn(entry_id, [row["id"] for row in get_entries_in_collection(collection_id)])


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class EntriesControllerQuickAddTests(_SyntheticDatabaseTestCase):
    def test_quick_add_creates_a_general_entry(self) -> None:
        controller = EntriesController()
        text = (
            "language: English\n"
            "explanation_language: Chinese\n"
            "entry_type: word\n"
            "term: resilient\n"
            "meaning: able to recover quickly\n"
        )

        entry_id, errors = controller.quick_add(text)

        self.assertEqual(errors, [])
        self.assertIsNotNone(entry_id)
        self.assertEqual(get_entry_by_id(entry_id)["term"], "resilient")

    def test_quick_add_resolves_collections_field(self) -> None:
        collection_id = create_collection("IELTS Core", card_size=8)
        controller = EntriesController()
        text = (
            "language: English\n"
            "explanation_language: Chinese\n"
            "term: alleviate\n"
            "meaning: to reduce\n"
            "collections: IELTS Core\n"
        )

        entry_id, errors = controller.quick_add(text)

        self.assertEqual(errors, [])
        self.assertIn(entry_id, [row["id"] for row in get_entries_in_collection(collection_id)])

    def test_quick_add_validation_failure_creates_nothing(self) -> None:
        controller = EntriesController()

        entry_id, errors = controller.quick_add("term: onlyterm\n")

        self.assertIsNone(entry_id)
        self.assertTrue(errors)
        controller.refresh()
        self.assertEqual(controller.model.rowCount(), 0)

    def test_quick_add_unknown_collection_name_fails_without_creating(self) -> None:
        controller = EntriesController()
        text = (
            "language: English\n"
            "explanation_language: Chinese\n"
            "term: alleviate\n"
            "meaning: to reduce\n"
            "collections: Nonexistent Collection\n"
        )

        entry_id, errors = controller.quick_add(text)

        self.assertIsNone(entry_id)
        self.assertTrue(errors)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class EntriesControllerDeleteTests(_SyntheticDatabaseTestCase):
    def test_delete_selected_removes_entries(self) -> None:
        entry_ids = self._make_entries([("chat", "cat"), ("chien", "dog")])
        controller = EntriesController()
        controller.refresh()
        controller.set_selected_ids({entry_ids[0]})

        count = controller.delete_selected()

        self.assertEqual(count, 1)
        self.assertIsNone(get_entry_by_id(entry_ids[0]))
        self.assertIsNotNone(get_entry_by_id(entry_ids[1]))
        self.assertEqual(controller.selected_ids, set())

    def test_batch_delete_removes_all_selected(self) -> None:
        entry_ids = self._make_entries([("un", "one"), ("deux", "two"), ("trois", "three")])
        controller = EntriesController()
        controller.refresh()
        controller.set_selected_ids(set(entry_ids))

        count = controller.delete_selected()

        self.assertEqual(count, 3)
        controller.refresh()
        self.assertEqual(controller.model.rowCount(), 0)

    def test_delete_requiring_cross_card_confirmation_mutates_nothing_until_confirmed(self) -> None:
        collection_id, entry_ids = self._collection_with_entries(4, card_size=3)
        controller = EntriesController()
        controller.refresh()
        controller.set_selected_ids({entry_ids[0]})

        with self.assertRaises(CrossCardMoveConfirmationRequired):
            controller.delete_selected()
        self.assertEqual(
            [row["id"] for row in get_entries_in_collection(collection_id)],
            entry_ids,
        )

        controller.delete_selected(confirm_cross_card=True)

        self.assertEqual(
            [row["id"] for row in get_entries_in_collection(collection_id)],
            entry_ids[1:],
        )

    def test_add_selected_to_starred_and_proficient_pool(self) -> None:
        entry_ids = self._make_entries([("chat", "cat")])
        controller = EntriesController()
        controller.refresh()
        controller.set_selected_ids(set(entry_ids))

        controller.add_selected_to_starred()
        controller.add_selected_to_proficient_pool()

        controller.set_scope("system:starred")
        self.assertEqual([row["id"] for row in controller.model.rows()], entry_ids)


class EntriesCoreBoundaryTests(unittest.TestCase):
    """Reusable-core boundary guards (M16.1 contract): Entries orchestrates
    presentation and selection state only; every write goes through
    existing src.entries/src.collections/src.entry_templates/src.text_parser
    functions, and no Streamlit dependency leaks into the desktop layer."""

    def _assert_no_raw_sql(self, relative_path: str) -> None:
        path = PROJECT_ROOT / relative_path
        text = path.read_text(encoding="utf-8")
        # A literal SQL-keyword substring check false-positives here on
        # legitimate Qt API (QItemSelectionModel.SelectionFlag.Select),
        # since "Entries" text/UI legitimately talks about "selection" a
        # lot. The precise, codebase-accurate signal for raw SQL is
        # actually reaching a connection and calling .execute(...) --
        # every real raw-SQL call site in this repo uses
        # "with get_connection() as connection: connection.execute(...)".
        self.assertNotIn("get_connection", text)
        self.assertNotIn(".execute(", text)
        self.assertNotIn("import sqlite3", text)
        self.assertNotIn("from src import db", text)

    def test_controller_has_no_raw_sql_and_no_db_import(self) -> None:
        self._assert_no_raw_sql("src/ui_desktop/controllers/entries_controller.py")

    def test_view_has_no_raw_sql_and_no_direct_db_import(self) -> None:
        self._assert_no_raw_sql("src/ui_desktop/views/entries_view.py")

    def test_no_streamlit_dependency_in_desktop_entries_code(self) -> None:
        # Docstrings legitimately reference src/ui_streamlit/entries_page.py
        # as a *behavioral* reference (M17 Feature 4 prompt § 10); what must
        # never appear is an actual import of it.
        for relative_path in (
            "src/ui_desktop/controllers/entries_controller.py",
            "src/ui_desktop/views/entries_view.py",
        ):
            text = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
            self.assertNotIn("import streamlit", text.lower())
            self.assertNotIn("from src.ui_streamlit", text)
            self.assertNotIn("import src.ui_streamlit", text)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class EntriesViewStructureTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_table_and_scope_pane_populate_on_refresh(self) -> None:
        self._make_entries([("chat", "cat"), ("chien", "dog")])
        create_collection("French Verbs", card_size=8)
        controller = EntriesController()
        view = EntriesView(controller)
        self.addCleanup(view.deleteLater)

        view.refresh()

        self.assertEqual(controller.model.rowCount(), 2)
        self.assertIn("collection:", "".join(view._scope_pane._buttons.keys()))

    def test_selecting_a_row_updates_detail_and_reveals_batch_actions(self) -> None:
        entry_ids = self._make_entries([("chat", "cat")])
        controller = EntriesController()
        view = EntriesView(controller)
        self.addCleanup(view.deleteLater)
        view.show()
        self.app.processEvents()
        view.refresh()

        controller.set_selected_ids({entry_ids[0]})

        # isVisible() needs the whole ancestor chain shown; view.show() above
        # makes that reliable here (isHidden() alone would not require it).
        self.assertTrue(view._star_button.isVisible())
        self.assertTrue(view._delete_button.isVisible())
        values = [w.text() for w in view._detail_container.findChildren(QWidget) if w.objectName() == "entries-detail-value"]
        self.assertIn("chat", values)

    def test_batch_actions_hidden_with_no_selection(self) -> None:
        controller = EntriesController()
        view = EntriesView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()

        self.assertTrue(view._star_button.isHidden())
        self.assertTrue(view._delete_button.isHidden())

    def test_add_entry_dialog_saves_a_new_entry(self) -> None:
        controller = EntriesController()
        view = EntriesView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()

        dialog = _EntryEditorDialog(controller, None, view)
        self.addCleanup(dialog.deleteLater)
        dialog._language_combo.setCurrentText("English")
        dialog._explanation_language_combo.setCurrentText("Chinese")
        _set_field_value(dialog._field_inputs["term"], "resilient")
        _set_field_value(dialog._field_inputs["meaning"], "able to recover quickly")

        dialog._on_save()

        self.assertEqual(dialog._error_label.text(), "")
        controller.refresh()
        self.assertIn("resilient", [row["term"] for row in controller.model.rows()])

    def test_edit_dialog_locks_template_and_prefills_values(self) -> None:
        entry_id = self._make_entries([("chat", "cat")])[0]
        controller = EntriesController()

        dialog = _EntryEditorDialog(controller, entry_id, None)
        self.addCleanup(dialog.deleteLater)

        self.assertFalse(dialog._template_combo.isEnabled())
        self.assertEqual(dialog._field_inputs["term"].text(), "chat")

    def test_delete_selected_confirmation_flow_with_cross_card_retry(self) -> None:
        collection_id, entry_ids = self._collection_with_entries(4, card_size=3)
        controller = EntriesController()
        view = EntriesView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()
        controller.set_selected_ids({entry_ids[0]})

        with patch("src.ui_desktop.views.entries_view._confirm_cross_card_reorganization", return_value=True):
            view._delete_selected(confirm_cross_card=False)

        self.assertEqual(
            [row["id"] for row in get_entries_in_collection(collection_id)],
            entry_ids[1:],
        )

    def test_quick_add_dialog_creates_entry(self) -> None:
        controller = EntriesController()
        dialog = _QuickAddDialog(controller, None)
        self.addCleanup(dialog.deleteLater)
        dialog._text_edit.setPlainText(
            "language: English\nexplanation_language: Chinese\nterm: alleviate\nmeaning: to reduce\n"
        )

        dialog._on_create()

        self.assertEqual(dialog._error_label.text(), "")
        controller.refresh()
        self.assertIn("alleviate", [row["term"] for row in controller.model.rows()])

    def test_quick_add_dialog_preserves_text_on_validation_failure(self) -> None:
        controller = EntriesController()
        dialog = _QuickAddDialog(controller, None)
        self.addCleanup(dialog.deleteLater)
        dialog._text_edit.setPlainText("term: onlyterm\n")

        dialog._on_create()

        self.assertNotEqual(dialog._error_label.text(), "")
        self.assertEqual(dialog._text_edit.toPlainText(), "term: onlyterm\n")


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class MainWindowEntriesIntegrationTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_navigating_to_entries_refreshes_scopes_and_table(self) -> None:
        self._make_entries([("chat", "cat"), ("chien", "dog")])
        window = MainWindow()
        self.addCleanup(window.close)
        window.show()
        self.app.processEvents()

        window._navigation_rail._buttons["entries"].click()

        self.assertIs(window.current_workspace(), Workspace.ENTRIES)
        self.assertEqual(window.entries_controller.model.rowCount(), 2)
        self.assertTrue(window.entries_controller.scopes)


if PYSIDE6_AVAILABLE:

    def _set_field_value(widget, value: str) -> None:
        if isinstance(widget, QPlainTextEdit):
            widget.setPlainText(value)
        else:
            widget.setText(value)


if __name__ == "__main__":
    unittest.main()
