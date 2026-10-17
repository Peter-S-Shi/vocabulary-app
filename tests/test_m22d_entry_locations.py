from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QLabel

from src import collections, db
from src.collections import (
    add_entries_to_collection,
    add_entries_to_system_collection,
    create_collection,
    delete_collection,
    move_entry_in_collection,
    remove_entries_from_collection,
    update_collection,
)
from src.entries import add_entry
from src.ui_desktop.controllers.entries_controller import EntriesController
from src.ui_desktop.views.entries_view import EntriesView


class _FictionalDatabase:
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.previous_db_path = db.DB_PATH
        db.DB_PATH = Path(self.temp_dir.name) / "m22d-fictional.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.previous_db_path
        self.temp_dir.cleanup()


class EntryLocationCoreTests(_FictionalDatabase, unittest.TestCase):
    def _entry(self, term: str) -> int:
        return add_entry("French", "English", "word", term, f"meaning-{term}")

    def test_current_locations_use_each_collections_position_and_card_size(self) -> None:
        entry_ids = [self._entry(term) for term in ("un", "deux", "trois", "quatre")]
        target = entry_ids[-1]
        alpha = create_collection("Alpha", card_size=1)
        beta = create_collection("Beta", card_size=2)
        add_entries_to_collection(entry_ids, alpha)
        add_entries_to_collection([entry_ids[0], entry_ids[1], target], beta)
        add_entries_to_system_collection([target], "starred")

        locations = collections.get_entry_locations_for_entries([target])

        self.assertEqual(
            [(row["collection_name"], row["card_number"], row["is_system"]) for row in locations[target]],
            [("Alpha", 4, False), ("Beta", 2, False), ("Starred", None, True)],
        )
        self.assertEqual(
            collections.get_collection_names_for_entries([target])[target],
            ["Alpha", "Beta", "Starred"],
        )


    def test_visible_entries_use_one_read_only_membership_query(self) -> None:
        entry_ids = [self._entry(f"batch-{index}") for index in range(24)]
        collection_id = create_collection("Batch", card_size=3)
        add_entries_to_collection(entry_ids, collection_id)
        statements: list[str] = []
        connections: list[sqlite3.Connection] = []
        real_connect = sqlite3.connect
        write_actions = {
            sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE,
            sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_DROP_TABLE,
            sqlite3.SQLITE_ALTER_TABLE,
        }

        def observed_connect(*args, **kwargs):
            connection = real_connect(*args, **kwargs)
            connections.append(connection)
            connection.set_trace_callback(statements.append)
            connection.set_authorizer(
                lambda action, *_: sqlite3.SQLITE_DENY if action in write_actions else sqlite3.SQLITE_OK
            )
            return connection

        with patch("sqlite3.connect", side_effect=observed_connect):
            locations = collections.get_entry_locations_for_entries(entry_ids)

        self.assertEqual(len(connections), 1)
        self.assertEqual(len([sql for sql in statements if sql.lstrip().upper().startswith("SELECT")]), 1)
        self.assertEqual(len(locations), len(entry_ids))
        self.assertEqual(locations[entry_ids[-1]][0]["card_number"], 8)

    def test_large_batch_respects_sqlite_parameter_limit(self) -> None:
        target = self._entry("large-batch")
        collection_id = create_collection("Large Batch", card_size=1)
        add_entries_to_collection([target], collection_id)
        real_connect = sqlite3.connect

        def limited_connect(*args, **kwargs):
            connection = real_connect(*args, **kwargs)
            connection.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 999)
            return connection

        with patch("sqlite3.connect", side_effect=limited_connect):
            locations = collections.get_entry_locations_for_entries(list(range(1, 1002)))
        self.assertEqual(locations[target][0]["card_number"], 1)
        self.assertEqual(len(locations), 1001)

    def test_locations_follow_reorder_size_change_membership_and_deletion(self) -> None:
        first, second, target = [self._entry(term) for term in ("one", "two", "target")]
        collection_id = create_collection("Mutable", card_size=2)
        add_entries_to_collection([first, second, target], collection_id)

        def current_card() -> int | None:
            rows = collections.get_entry_locations_for_entries([target])[target]
            return rows[0]["card_number"] if rows else None

        self.assertEqual(current_card(), 2)
        move_entry_in_collection(collection_id, target, 2, confirm_cross_card=True)
        self.assertEqual(current_card(), 1)
        update_collection(collection_id, "Mutable", "", 1, confirm_cross_card=True)
        self.assertEqual(current_card(), 2)
        remove_entries_from_collection([target], collection_id, confirm_cross_card=True)
        self.assertIsNone(current_card())
        add_entries_to_collection([target], collection_id)
        self.assertEqual(current_card(), 3)
        delete_collection(collection_id)
        self.assertEqual(collections.get_entry_locations_for_entries([target])[target], [])


class EntryLocationViewTests(_FictionalDatabase, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_open_detail_updates_after_collection_changes_and_refresh(self) -> None:
        ids = [add_entry("French", "English", "word", term, term) for term in ("first", "second", "target")]
        target = ids[-1]
        collection_id = create_collection("Mutable", card_size=2)
        add_entries_to_collection(ids, collection_id)
        controller = EntriesController()
        view = EntriesView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()
        controller.set_focused_id(target)

        def visible_location() -> str:
            # The view replaces old detail widgets with deferred Qt deletion.
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            caption = next(
                label for label in view.findChildren(QLabel, "entries-detail-caption")
                if label.text() == "Current locations"
            )
            return caption.parentWidget().findChild(QLabel, "entries-detail-value").text()

        self.assertEqual(visible_location(), "Mutable · Card 2")
        move_entry_in_collection(collection_id, target, 2, confirm_cross_card=True)
        view.refresh()
        self.assertEqual(visible_location(), "Mutable · Card 1")
        update_collection(collection_id, "Mutable", "", 1, confirm_cross_card=True)
        view.refresh()
        self.assertEqual(visible_location(), "Mutable · Card 2")
        remove_entries_from_collection([target], collection_id, confirm_cross_card=True)
        view.refresh()
        self.assertEqual(visible_location(), "No current locations")

    def test_detail_explains_when_entry_has_no_current_locations(self) -> None:
        target = add_entry("French", "English", "word", "orphan", "fictional")
        controller = EntriesController()
        view = EntriesView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()
        controller.set_focused_id(target)
        caption = next(
            label for label in view.findChildren(QLabel, "entries-detail-caption")
            if label.text() == "Current locations"
        )
        displayed = caption.parentWidget().findChild(QLabel, "entries-detail-value").text()
        self.assertEqual(displayed, "No current locations")

    def test_detail_displays_each_current_card_and_labels_practice_pool(self) -> None:
        entry_ids = [add_entry("French", "English", "word", term, term) for term in ("un", "deux", "trois", "quatre")]
        target = entry_ids[-1]
        alpha = create_collection("Alpha", card_size=1)
        beta = create_collection("Beta", card_size=2)
        add_entries_to_collection(entry_ids, alpha)
        add_entries_to_collection([entry_ids[0], entry_ids[1], target], beta)
        add_entries_to_system_collection([target], "starred")
        controller = EntriesController()
        view = EntriesView(controller)
        self.addCleanup(view.deleteLater)
        view.refresh()
        controller.set_focused_id(target)

        caption = next(
            label for label in view.findChildren(QLabel, "entries-detail-caption")
            if label.text() == "Current locations"
        )
        displayed = caption.parentWidget().findChild(QLabel, "entries-detail-value").text()
        self.assertEqual(displayed, "Alpha · Card 4\nBeta · Card 2\nStarred · Practice pool")
        self.assertEqual(controller.focused_entry()["collection_names"], ["Alpha", "Beta", "Starred"])


if __name__ == "__main__":
    unittest.main()
