from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.setup_desktop_launcher import (
    LAUNCH_ARGUMENTS,
    _powershell_quote,
    build_powershell_script,
    select_launch_python,
)

"""
Focused, filesystem/PowerShell-free tests for tools/setup_desktop_launcher.py's
pure logic. The script's actual Windows shortcut creation (WScript.Shell via
powershell.exe) and the resulting shortcut's target/arguments/working-
directory/icon were verified manually against a real, running PySide6
process on the development machine; see docs/history/MILESTONE16_CLOSURE.md.
This file does not touch the real Desktop and does not shell out to
powershell.exe, so it stays part of the regular headless suite.
"""


class M162DesktopLauncherSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.scripts_dir = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_prefers_pythonw_when_present_next_to_interpreter(self) -> None:
        python_exe = self.scripts_dir / "python.exe"
        pythonw_exe = self.scripts_dir / "pythonw.exe"
        python_exe.touch()
        pythonw_exe.touch()

        selected = select_launch_python(python_exe)

        self.assertEqual(selected, pythonw_exe)

    def test_falls_back_to_python_when_pythonw_missing(self) -> None:
        python_exe = self.scripts_dir / "python.exe"
        python_exe.touch()

        selected = select_launch_python(python_exe)

        self.assertEqual(selected, python_exe)


class M162DesktopLauncherScriptBuildingTests(unittest.TestCase):
    def test_powershell_quote_escapes_single_quotes(self) -> None:
        self.assertEqual(_powershell_quote("O'Brien"), "O''Brien")
        self.assertEqual(_powershell_quote("no quotes"), "no quotes")

    def test_build_powershell_script_embeds_expected_fields(self) -> None:
        target = Path(r"C:\Fake\.venv\Scripts\pythonw.exe")
        working_directory = Path(r"C:\Fake\repo")
        icon_path = Path(r"C:\Fake\repo\assets\icons\vocabulary_app.ico")

        script = build_powershell_script(
            shortcut_file_name="Vocabulary App.lnk",
            target=target,
            arguments=LAUNCH_ARGUMENTS,
            working_directory=working_directory,
            icon_path=icon_path,
            description="Vocabulary App desktop preview (M16.2 vertical slice)",
        )

        # Uses the real per-user known-folder API rather than a hardcoded
        # "$HOME\Desktop" guess (which breaks under OneDrive Desktop
        # redirection -- confirmed on the development machine).
        self.assertIn("[Environment]::GetFolderPath('Desktop')", script)
        self.assertIn("Vocabulary App.lnk", script)
        self.assertIn(str(target), script)
        self.assertIn(LAUNCH_ARGUMENTS, script)
        self.assertIn(str(working_directory), script)
        self.assertIn(str(icon_path), script)
        self.assertIn("New-Object -ComObject WScript.Shell", script)
        self.assertIn("$shortcut.Save()", script)

    def test_launch_arguments_target_the_desktop_module_entry_point(self) -> None:
        self.assertEqual(LAUNCH_ARGUMENTS, "-m src.ui_desktop")


if __name__ == "__main__":
    unittest.main()
