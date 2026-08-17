from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtWidgets import QApplication, QWidget

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when PySide6 is absent
    PYSIDE6_AVAILABLE = False

from src import db
from src.collections import (
    CARD_PAGE_SIZE_OPTIONS,
    CrossCardMoveConfirmationRequired,
    add_entries_to_collection,
    add_entries_to_system_collection,
    create_collection,
    get_card_page_for_collection,
    get_entries_in_system_collection,
)
from src.entries import add_entry

"""
Focused tests for the M17 Minimum Collection Integration corrective pass
(M17_Minimum_Collection_Integration_Corrective_Pass.md): paged/scrollable
Card navigation for large Collections, the focused_id/checked_ids
selection-model split in Entries, and the direct per-row Star affordance.
Per DESIGN.md § 2 Rule C, none of this proves visual realization -- only
that the contracts are correct and that pagination genuinely avoids
loading a Collection's full Entry set. Native human visual acceptance is
a separate, required gate (AGENTS.md).
"""

if PYSIDE6_AVAILABLE:
    from src.ui_desktop.controllers.collections_controller import CollectionsController
    from src.ui_desktop.controllers.entries_controller import EntriesController
    from src.ui_desktop.views.collections_view import CollectionsView
    from src.ui_desktop.views.entries_view import EntriesView, _confirm_cross_card_reorganization

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
        db.DB_PATH = self.root / "m17_corrective.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _make_entries(self, terms) -> list[int]:
        return [add_entry("French", "English", "word", term, meaning) for term, meaning in terms]

    def _flush_deleted_widgets(self) -> None:
        """deleteLater()-scheduled widgets from _clear_layout() remain
        reachable via findChildren() until flushed like this."""
        app = _qt_app()
        app.processEvents()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()


# -- Card pagination (§ 2/§ 3/§ 4) ----------------------------------------


class CardPaginationCoreTests(_SyntheticDatabaseTestCase):
    def _large_collection(self, entry_count: int = 42, card_size: int = 5) -> int:
        entry_ids = self._make_entries([(f"term{i}", f"meaning{i}") for i in range(entry_count)])
        collection_id = create_collection("Large", card_size=card_size)
        add_entries_to_collection(entry_ids, collection_id)
        return collection_id

    def test_page_count_calculation(self) -> None:
        collection_id = self._large_collection(entry_count=42, card_size=5)  # 9 Cards

        page = get_card_page_for_collection(collection_id, page=1, page_size=5)

        self.assertEqual(page["total_cards"], 9)
        self.assertEqual(page["total_pages"], 2)

    def test_cards_per_page_bounds_returned_cards(self) -> None:
        collection_id = self._large_collection(entry_count=42, card_size=5)

        page = get_card_page_for_collection(collection_id, page=1, page_size=5)

        self.assertEqual(len(page["cards"]), 5)
        self.assertEqual([c["card_number"] for c in page["cards"]], [1, 2, 3, 4, 5])

    def test_first_middle_last_page(self) -> None:
        collection_id = self._large_collection(entry_count=42, card_size=5)  # 9 Cards, page_size 5 -> 2 pages

        first = get_card_page_for_collection(collection_id, page=1, page_size=5)
        last = get_card_page_for_collection(collection_id, page=2, page_size=5)

        self.assertEqual([c["card_number"] for c in first["cards"]], [1, 2, 3, 4, 5])
        self.assertEqual([c["card_number"] for c in last["cards"]], [6, 7, 8, 9])

    def test_out_of_range_page_clamps_to_last_page(self) -> None:
        collection_id = self._large_collection(entry_count=42, card_size=5)

        page = get_card_page_for_collection(collection_id, page=999, page_size=5)

        self.assertEqual(page["page"], 2)
        self.assertEqual([c["card_number"] for c in page["cards"]], [6, 7, 8, 9])

    def test_negative_or_zero_page_clamps_to_first_page(self) -> None:
        collection_id = self._large_collection(entry_count=42, card_size=5)

        page = get_card_page_for_collection(collection_id, page=0, page_size=5)

        self.assertEqual(page["page"], 1)

    def test_sort_by_card_number_is_ascending(self) -> None:
        collection_id = self._large_collection(entry_count=20, card_size=5)

        page = get_card_page_for_collection(collection_id, page=1, page_size=10, sort_by="card_number")

        self.assertEqual([c["card_number"] for c in page["cards"]], sorted(c["card_number"] for c in page["cards"]))

    def test_entry_counts_are_correct_per_card(self) -> None:
        collection_id = self._large_collection(entry_count=11, card_size=5)  # Cards: 5, 5, 1

        page = get_card_page_for_collection(collection_id, page=1, page_size=10)

        counts = {c["card_number"]: c["entry_count"] for c in page["cards"]}
        self.assertEqual(counts, {1: 5, 2: 5, 3: 1})

    def test_missing_collection_returns_empty_page(self) -> None:
        page = get_card_page_for_collection(999999, page=1, page_size=10)

        self.assertEqual(page["cards"], [])
        self.assertEqual(page["total_cards"], 0)

    def test_paging_never_loads_the_full_entry_set(self) -> None:
        """§ 3: the paged query must never fall back to "load everything,
        slice in Python" -- ``get_entries_in_collection`` must not be
        called by the paged projection."""
        collection_id = self._large_collection(entry_count=200, card_size=8)

        with patch("src.collections.get_entries_in_collection") as mock_get_entries:
            get_card_page_for_collection(collection_id, page=1, page_size=5)

        mock_get_entries.assert_not_called()


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class CardPaginationControllerTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    _collection_counter = 0

    def _large_collection(self, entry_count: int = 42, card_size: int = 5) -> int:
        type(self)._collection_counter += 1
        entry_ids = self._make_entries([(f"term{i}", f"meaning{i}") for i in range(entry_count)])
        collection_id = create_collection(f"Large {type(self)._collection_counter}", card_size=card_size)
        add_entries_to_collection(entry_ids, collection_id)
        return collection_id

    def test_default_page_and_page_size(self) -> None:
        collection_id = self._large_collection()
        controller = CollectionsController()
        controller.refresh()
        controller.select_collection(collection_id, is_system=False)

        self.assertEqual(controller.card_page, 1)
        self.assertIn(controller.card_page_size, CARD_PAGE_SIZE_OPTIONS)

    def test_set_card_page_size_resets_to_first_page(self) -> None:
        collection_id = self._large_collection(entry_count=42, card_size=5)
        controller = CollectionsController()
        controller.refresh()
        controller.select_collection(collection_id, is_system=False)
        controller.set_card_page(2)

        controller.set_card_page_size(20)

        self.assertEqual(controller.card_page, 1)
        self.assertEqual(controller.card_page_size, 20)

    def test_set_card_sort_resets_to_first_page(self) -> None:
        collection_id = self._large_collection(entry_count=42, card_size=5)
        controller = CollectionsController()
        controller.refresh()
        controller.select_collection(collection_id, is_system=False)
        controller.set_card_page(2)

        controller.set_card_sort("card_updated_at")

        self.assertEqual(controller.card_page, 1)
        self.assertEqual(controller.card_sort, "card_updated_at")

    def test_selecting_a_new_collection_resets_page(self) -> None:
        collection_a = self._large_collection(entry_count=42, card_size=5)
        collection_b = self._large_collection(entry_count=15, card_size=5)
        controller = CollectionsController()
        controller.refresh()
        controller.select_collection(collection_a, is_system=False)
        controller.set_card_page(2)

        controller.select_collection(collection_b, is_system=False)

        self.assertEqual(controller.card_page, 1)

    def test_open_in_study_from_a_later_page_targets_the_exact_card(self) -> None:
        collection_id = self._large_collection(entry_count=42, card_size=5)  # 9 Cards
        controller = CollectionsController()
        view = CollectionsView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()
        controller.select_collection(collection_id, is_system=False)
        controller.set_card_page_size(5)  # 2 pages of 5
        controller.set_card_page(2)
        self._flush_deleted_widgets()

        from src.ui_desktop.state.handoff import StudyTargetIntent

        received: list[StudyTargetIntent] = []
        view.open_in_study_requested.connect(received.append)
        buttons = [
            w
            for w in view._detail_container.findChildren(QWidget)
            if w.objectName() == "collections-open-in-study-button"
        ]
        self.assertEqual(len(buttons), 4)  # page 2 has Cards 6-9
        buttons[0].click()

        self.assertEqual(received, [StudyTargetIntent(collection_id=collection_id, card_number=6)])

    def test_page_controls_render_previous_next_and_indicator(self) -> None:
        collection_id = self._large_collection(entry_count=42, card_size=5)  # 9 Cards
        controller = CollectionsController()
        view = CollectionsView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()
        controller.select_collection(collection_id, is_system=False)
        controller.set_card_page_size(5)  # 2 pages of 5
        self._flush_deleted_widgets()

        page_label = next(
            w for w in view._detail_container.findChildren(QWidget) if w.objectName() == "collections-card-page-label"
        )
        previous_button = next(
            w
            for w in view._detail_container.findChildren(QWidget)
            if w.objectName() == "collections-card-previous-button"
        )
        self.assertEqual(page_label.text(), "Page 1 of 2")
        self.assertFalse(previous_button.isEnabled())


# -- Entries: focused vs checked (§ 5/§ 6/§ 8) -----------------------------


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class EntriesFocusVsCheckedTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_row_click_sets_focused_without_touching_checked(self) -> None:
        entry_ids = self._make_entries([("chat", "cat"), ("chien", "dog")])
        controller = EntriesController()
        view = EntriesView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()
        controller.set_checked_ids({entry_ids[0]})

        controller.set_focused_id(entry_ids[1])

        self.assertEqual(controller.checked_ids, {entry_ids[0]})
        self.assertEqual(controller.focused_id, entry_ids[1])

    def test_non_contiguous_checked_entries_persist(self) -> None:
        entry_ids = self._make_entries([(f"term{i}", f"meaning{i}") for i in range(10)])
        controller = EntriesController()
        view = EntriesView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()

        controller.set_checked_ids({entry_ids[0]})
        controller.set_checked_ids(controller.checked_ids | {entry_ids[7]})

        self.assertEqual(controller.checked_ids, {entry_ids[0], entry_ids[7]})

    def test_header_select_all_does_not_change_focused_id(self) -> None:
        entry_ids = self._make_entries([("chat", "cat"), ("chien", "dog")])
        controller = EntriesController()
        view = EntriesView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()
        controller.set_focused_id(entry_ids[0])

        view._on_header_toggled(True)

        self.assertEqual(controller.focused_id, entry_ids[0])
        self.assertEqual(controller.checked_ids, set(entry_ids))

    def test_bottom_detail_follows_focused_entry_with_multiple_checked(self) -> None:
        entry_ids = self._make_entries([("chat", "cat"), ("chien", "dog")])
        controller = EntriesController()
        view = EntriesView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()

        controller.set_checked_ids(set(entry_ids))
        controller.set_focused_id(entry_ids[0])

        values = [w.text() for w in view._detail_container.findChildren(QWidget) if w.objectName() == "entries-detail-value"]
        self.assertIn("chat", values)
        checked_line = [w.text() for w in view._detail_container.findChildren(QWidget) if w.objectName() == "entries-detail-value" and "Entries" in w.text()]
        self.assertTrue(checked_line)

    def test_bottom_detail_shows_choose_a_row_when_nothing_focused_even_if_checked(self) -> None:
        entry_ids = self._make_entries([("chat", "cat"), ("chien", "dog")])
        controller = EntriesController()
        view = EntriesView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()

        controller.set_checked_ids(set(entry_ids))

        messages = [w.text() for w in view._detail_container.findChildren(QWidget) if w.objectName() == "entries-empty-state"]
        self.assertTrue(any("checked" in m for m in messages))
        self.assertFalse(any(w.objectName() == "entries-detail-value" for w in view._detail_container.findChildren(QWidget)))

    def test_batch_delete_operates_on_checked_not_focused(self) -> None:
        entry_ids = self._make_entries([("chat", "cat"), ("chien", "dog"), ("oiseau", "bird")])
        controller = EntriesController()
        controller.refresh()
        controller.set_focused_id(entry_ids[2])  # focused, but not checked
        controller.set_checked_ids({entry_ids[0], entry_ids[1]})

        controller.delete_selected()

        from src.entries import get_entry_by_id

        self.assertIsNone(get_entry_by_id(entry_ids[0]))
        self.assertIsNone(get_entry_by_id(entry_ids[1]))
        self.assertIsNotNone(get_entry_by_id(entry_ids[2]))


# -- Star (§ 9/§ 10/§ 11) ---------------------------------------------------


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class EntriesStarTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_unstarred_entry_renders_unfilled(self) -> None:
        self._make_entries([("chat", "cat")])
        controller = EntriesController()
        controller.refresh()

        model = controller.model
        star_column = model.COLUMNS.index(model.STAR_COLUMN)
        index = model.index(0, star_column)
        self.assertEqual(model.data(index, Qt.ItemDataRole.DisplayRole), "☆")

    def test_starred_entry_renders_filled(self) -> None:
        entry_ids = self._make_entries([("chat", "cat")])
        add_entries_to_system_collection(entry_ids, "starred")
        controller = EntriesController()
        controller.refresh()

        model = controller.model
        star_column = model.COLUMNS.index(model.STAR_COLUMN)
        index = model.index(0, star_column)
        self.assertEqual(model.data(index, Qt.ItemDataRole.DisplayRole), "★")

    def test_star_click_persists_membership(self) -> None:
        entry_ids = self._make_entries([("chat", "cat")])
        controller = EntriesController()
        controller.refresh()

        controller.toggle_star(entry_ids[0])

        self.assertIn(entry_ids[0], {int(e["id"]) for e in get_entries_in_system_collection("starred")})

    def test_unstar_click_removes_membership(self) -> None:
        entry_ids = self._make_entries([("chat", "cat")])
        add_entries_to_system_collection(entry_ids, "starred")
        controller = EntriesController()
        controller.refresh()

        controller.toggle_star(entry_ids[0])

        self.assertNotIn(entry_ids[0], {int(e["id"]) for e in get_entries_in_system_collection("starred")})

    def test_starred_scope_refresh_removes_entry_after_unstar(self) -> None:
        entry_ids = self._make_entries([("chat", "cat"), ("chien", "dog")])
        add_entries_to_system_collection(entry_ids, "starred")
        controller = EntriesController()
        controller.set_scope("system:starred")
        controller.refresh()
        self.assertEqual(len(controller.model.rows()), 2)

        controller.toggle_star(entry_ids[0])

        self.assertEqual([row["id"] for row in controller.model.rows()], [entry_ids[1]])

    def test_cross_card_confirmation_preserved_on_unstar(self) -> None:
        """Unstarring can trigger the same Card-reorganization safety gate
        as any other Collection-removal (§ 10) -- never silently
        bypassed."""
        # Pre-create the Starred pool with a small Card size *before* any
        # Entries are added to it, so the pool itself already spans
        # multiple Cards once populated -- resizing an already-populated
        # pool would itself require confirmation, which would corrupt
        # this setup step.
        from src.collections import get_or_create_system_collection

        get_or_create_system_collection("starred", "Starred", "", card_size=3)
        entry_ids = self._make_entries([(f"term{i}", f"meaning{i}") for i in range(4)])
        add_entries_to_system_collection(entry_ids, "starred")

        controller = EntriesController()
        controller.refresh()

        with self.assertRaises(CrossCardMoveConfirmationRequired):
            controller.toggle_star(entry_ids[0])

        self.assertIn(entry_ids[0], {int(e["id"]) for e in get_entries_in_system_collection("starred")})

        controller.toggle_star(entry_ids[0], confirm_cross_card=True)

        self.assertNotIn(entry_ids[0], {int(e["id"]) for e in get_entries_in_system_collection("starred")})

    def test_star_column_click_in_view_toggles_and_handles_confirmation(self) -> None:
        entry_ids = self._make_entries([("chat", "cat")])
        controller = EntriesController()
        view = EntriesView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()

        with patch("src.ui_desktop.views.entries_view._confirm_cross_card_reorganization", return_value=True):
            view._toggle_star(entry_ids[0], confirm_cross_card=False)

        self.assertIn(entry_ids[0], {int(e["id"]) for e in get_entries_in_system_collection("starred")})


if __name__ == "__main__":
    unittest.main()
