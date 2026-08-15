from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from src.db import init_db
from src.ui_desktop.main_window import MainWindow
from src.ui_desktop.state.preferences import load_preferences
from src.ui_desktop.theming.theme_manager import ThemeManager, parse_accent, parse_appearance

"""
Desktop bootstrap: construct QApplication, initialize the database once,
load and apply the saved theme preference, build the shell, run the event
loop, and shut down cleanly (M16.1 contract § 8/§ 19 item 2).

Launch with:  python -m src.ui_desktop
This does not replace the existing Streamlit app.py; both remain runnable
independently during the migration.
"""


def build_application(argv: list[str] | None = None) -> tuple[QApplication, MainWindow, ThemeManager]:
    application = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)

    init_db()

    theme_manager = ThemeManager(application)
    preferences = load_preferences()
    theme_manager.apply(parse_appearance(preferences.appearance), parse_accent(preferences.accent))

    window = MainWindow()
    return application, window, theme_manager


def main(argv: list[str] | None = None) -> int:
    application, window, _theme_manager = build_application(argv)
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
