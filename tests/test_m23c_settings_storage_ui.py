from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton, QLabel

from src import app_config
from src.data_relocation import RelocationPlan, RelocationResult
from src.ui_desktop.controllers.settings_controller import SettingsController
from src.ui_desktop.views.settings_view import SettingsView


def _qt_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _create_fictional_app_database(path: Path) -> None:
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("CREATE TABLE entries (id INTEGER PRIMARY KEY, term TEXT, meaning TEXT)")
        connection.execute("CREATE TABLE collections (id INTEGER PRIMARY KEY, name TEXT)")
        connection.execute("CREATE TABLE app_metadata (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)")
        connection.executemany(
            "INSERT INTO app_metadata (key, value, updated_at) VALUES (?, ?, ?)",
            (
                ("schema_version", "2", "2026-10-17T12:00:00Z"),
                ("app_data_version", "1.1.0", "2026-10-17T12:00:00Z"),
            ),
        )
        connection.commit()


class SettingsStorageRelocationUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.home = Path(self.temp_dir.name)
        self.local_root = self.home / "local" / "vocabulary_app"
        self.local_root.mkdir(parents=True)
        _create_fictional_app_database(self.local_root / "vocab.db")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_controller_relocation_availability_reflects_overrides(self) -> None:
        controller = SettingsController()

        # Without overrides
        with patch.dict(os.environ, {
            "VOCAB_APP_DB_PATH": "",
            "VOCAB_APP_BACKUP_DIR": "",
            "VOCAB_APP_AUDIO_CACHE_DIR": "",
            "VOCAB_APP_PREFERENCES_PATH": "",
        }):
            self.assertTrue(controller.can_relocate_data())
            self.assertFalse(controller.has_storage_override())

        # With DB override
        with patch.dict(os.environ, {
            "VOCAB_APP_DB_PATH": "D:\\custom\\vocab.db",
        }):
            self.assertFalse(controller.can_relocate_data())
            self.assertTrue(controller.has_storage_override())

    def test_view_renders_move_button_enabled_when_no_overrides(self) -> None:
        with patch.dict(os.environ, {
            "LOCALAPPDATA": str(self.home / "local"),
            "VOCAB_APP_DB_PATH": "",
            "VOCAB_APP_BACKUP_DIR": "",
            "VOCAB_APP_AUDIO_CACHE_DIR": "",
            "VOCAB_APP_PREFERENCES_PATH": "",
        }):
            controller = SettingsController()
            view = SettingsView(controller)
            self.addCleanup(view.deleteLater)

            move_btn = view.findChild(QPushButton, "settings-storage-move-button")
            self.assertIsNotNone(move_btn)
            self.assertTrue(move_btn.isEnabled())
            self.assertEqual(move_btn.text(), "Move Data Folder...")

            note = view.findChild(QLabel, "settings-storage-move-note")
            self.assertIsNotNone(note)
            self.assertIn("safely move", note.text().lower())

    def test_view_disables_move_button_when_override_active(self) -> None:
        with patch.dict(os.environ, {
            "LOCALAPPDATA": str(self.home / "local"),
            "VOCAB_APP_DB_PATH": str(self.home / "custom.db"),
            "VOCAB_APP_BACKUP_DIR": "",
            "VOCAB_APP_AUDIO_CACHE_DIR": "",
            "VOCAB_APP_PREFERENCES_PATH": "",
        }):
            controller = SettingsController()
            view = SettingsView(controller)
            self.addCleanup(view.deleteLater)

            move_btn = view.findChild(QPushButton, "settings-storage-move-button")
            self.assertIsNotNone(move_btn)
            self.assertFalse(move_btn.isEnabled())

            note = view.findChild(QLabel, "settings-storage-move-note")
            self.assertIsNotNone(note)
            self.assertIn("environment overrides", note.text().lower())

    @patch("src.ui_desktop.views.settings_view.QFileDialog.getExistingDirectory")
    @patch("src.ui_desktop.views.settings_view.QMessageBox.question")
    @patch("src.ui_desktop.views.settings_view.QMessageBox.information")
    def test_view_move_dialog_confirmed_executes_relocation(
        self,
        mock_info: MagicMock,
        mock_question: MagicMock,
        mock_get_dir: MagicMock,
    ) -> None:
        target_parent = self.home / "external_drive"
        target_parent.mkdir()
        mock_get_dir.return_value = str(target_parent)
        mock_question.return_value = QMessageBox.StandardButton.Yes

        with patch.dict(os.environ, {
            "LOCALAPPDATA": str(self.home / "local"),
            "VOCAB_APP_DB_PATH": "",
            "VOCAB_APP_BACKUP_DIR": "",
            "VOCAB_APP_AUDIO_CACHE_DIR": "",
            "VOCAB_APP_PREFERENCES_PATH": "",
        }):
            controller = SettingsController()
            view = SettingsView(controller)
            self.addCleanup(view.deleteLater)

            with patch.object(self.app, "quit") as mock_quit:
                view._storage_move_btn.click()
                if hasattr(view, "_relocation_worker") and view._relocation_worker is not None:
                    view._relocation_worker.wait(5000)
                self.app.processEvents()

            mock_question.assert_called_once()
            self.assertIn("Vocabulary App will relocate your user data", mock_question.call_args[0][2])
            mock_info.assert_called_once()
            self.assertIn("Data relocation completed successfully", mock_info.call_args[0][2])
            mock_quit.assert_called_once()

            # Verify target directory created with files
            target = target_parent / "VocabularyAppData"
            self.assertTrue(target.is_dir())
            self.assertTrue((target / "vocab.db").is_file())


if __name__ == "__main__":
    unittest.main()
