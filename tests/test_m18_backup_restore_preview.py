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
from src.entries import add_entry

"""
Focused tests for M18 Phase C5 -- Backup / Restore Preview
(data_tools_view.py's `_BackupRestoreDialog` Design Derivation Record).
Per DESIGN.md § 2 Rule C these are structural/behavioral proof that
`DataToolsController` delegates every backup/preview call to the exact
same `src.backup` functions the Streamlit Import/Export page's Backup
tab already uses, and that Restore Preview never mutates SQLite -- there
is no core restore-execution function to call in the first place, and
this workspace must not invent one. Native human visual acceptance is a
separate, required gate (AGENTS.md).
"""

if PYSIDE6_AVAILABLE:
    from src.ui_desktop.controllers.data_tools_controller import DataToolsController
    from src.ui_desktop.theming.theme_manager import build_stylesheet
    from src.ui_desktop.theming.tokens import THEME_CALM_BLUE_DARK, THEME_CALM_BLUE_LIGHT
    from src.ui_desktop.views.data_tools_view import _BackupRestoreDialog

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
        db.DB_PATH = self.root / "m18_backup_restore.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class DataToolsBackupControllerTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_backup_summary_reflects_real_counts(self) -> None:
        add_entry("French", "English", "word", "pomme", "apple")
        controller = DataToolsController()

        summary = controller.backup_summary()

        self.assertEqual(summary["entries"], 1)

    def test_database_backup_bytes_are_nonempty(self) -> None:
        add_entry("French", "English", "word", "pomme", "apple")
        controller = DataToolsController()

        data = controller.build_database_backup()

        self.assertGreater(len(data), 0)

    def test_full_backup_workbook_bytes_are_nonempty(self) -> None:
        add_entry("French", "English", "word", "pomme", "apple")
        controller = DataToolsController()

        data = controller.build_full_backup_workbook()

        self.assertGreater(len(data), 0)

    def test_backup_filename_conventions(self) -> None:
        controller = DataToolsController()

        self.assertTrue(controller.backup_filename("database", "sqlite3").endswith(".sqlite3"))
        self.assertTrue(controller.backup_filename("full", "xlsx").endswith(".xlsx"))


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class DataToolsRestorePreviewControllerTests(_SyntheticDatabaseTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_preview_a_real_backup_workbook_reports_valid(self) -> None:
        add_entry("French", "English", "word", "pomme", "apple")
        controller = DataToolsController()
        workbook_bytes = controller.build_full_backup_workbook()

        controller.load_restore_preview_file(workbook_bytes, "backup.xlsx")
        controller.run_restore_preview()

        self.assertTrue(controller.restore_preview_result["valid_backup"])
        sheet_names = {sheet["sheet_name"] for sheet in controller.restore_preview_result["sheets"]}
        self.assertIn("entries", sheet_names)

    def test_preview_never_mutates_sqlite(self) -> None:
        controller = DataToolsController()
        workbook_bytes = controller.build_full_backup_workbook()
        controller.load_restore_preview_file(workbook_bytes, "backup.xlsx")
        before = controller.backup_summary()

        controller.run_restore_preview()

        after = controller.backup_summary()
        self.assertEqual(before, after)

    def test_preview_an_unrelated_file_reports_invalid(self) -> None:
        controller = DataToolsController()

        controller.load_restore_preview_file(b"not a real workbook", "not_a_backup.xlsx")
        controller.run_restore_preview()

        self.assertFalse(controller.restore_preview_result["valid_backup"])
        self.assertTrue(controller.restore_preview_result["errors"])

    def test_reset_restore_preview_clears_state(self) -> None:
        controller = DataToolsController()
        workbook_bytes = controller.build_full_backup_workbook()
        controller.load_restore_preview_file(workbook_bytes, "backup.xlsx")
        controller.run_restore_preview()
        self.assertIsNotNone(controller.restore_preview_result)

        controller.reset_restore_preview()

        self.assertIsNone(controller.restore_preview_file_bytes)
        self.assertIsNone(controller.restore_preview_result)

    def test_controller_exposes_no_restore_execution_method(self) -> None:
        """Product-truth guard: restore is intentionally preview-only.
        This surface must never grow a method that actually writes a
        backup's contents back into the live database."""
        controller = DataToolsController()
        restore_execution_names = [
            name
            for name in dir(controller)
            if "restore" in name.lower() and ("apply" in name.lower() or "confirm" in name.lower() or "execute" in name.lower())
        ]
        self.assertEqual(restore_execution_names, [])


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class BackupRestoreDialogStructureTests(_SyntheticDatabaseTestCase):
    """Structural-only proof (DESIGN.md § 2 Rule C)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_dialog_has_no_restore_confirm_button(self) -> None:
        """No button anywhere in this dialog may perform a destructive
        restore -- only Preview, Close, and the two Backup download
        actions should exist."""
        from PySide6.QtWidgets import QPushButton

        controller = DataToolsController()
        dialog = _BackupRestoreDialog(controller, parent=None)
        self.addCleanup(dialog.deleteLater)

        object_names = {button.objectName() for button in dialog.findChildren(QPushButton)}
        for name in object_names:
            self.assertNotIn("restore-confirm", name)
            self.assertNotIn("restore-execute", name)

    def test_preview_renders_sheet_table_after_a_real_backup_preview(self) -> None:
        add_entry("French", "English", "word", "pomme", "apple")
        controller = DataToolsController()
        dialog = _BackupRestoreDialog(controller, parent=None)
        self.addCleanup(dialog.deleteLater)

        workbook_bytes = controller.build_full_backup_workbook()
        controller.load_restore_preview_file(workbook_bytes, "backup.xlsx")
        controller.run_restore_preview()

        self.assertGreater(dialog._sheets_table.rowCount(), 0)
        self.assertIn("supported backup metadata", dialog._restore_summary_label.text())


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class M18BackupRestoreTokenQssStructuralCoverageTests(unittest.TestCase):
    REPRESENTATIVE_SELECTORS = (
        "#data-tools-backup-button",
        "#data-tools-database-backup-button",
        "#data-tools-workbook-backup-button",
        "#data-tools-restore-preview-button",
        "#data-tools-restore-notice",
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
