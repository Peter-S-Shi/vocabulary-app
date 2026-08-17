from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from src.app_config import get_app_icon_path
from src.db import init_db
from src.ui_desktop.main_window import MainWindow
from src.ui_desktop.motion.transitions import TransitionManager, parse_motion_policy
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


def _load_app_icon() -> QIcon | None:
    """The repository-owned icon (assets/icons/vocabulary_app.ico), used
    for both the application/window icon and the desktop launcher
    shortcut (tools/setup_desktop_launcher.py). Missing gracefully -- a
    missing icon file must never block launching the app."""
    icon_path = get_app_icon_path()
    if not icon_path.is_file():
        return None
    return QIcon(str(icon_path))


def build_application(argv: list[str] | None = None) -> tuple[QApplication, MainWindow, ThemeManager]:
    application = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)

    icon = _load_app_icon()
    if icon is not None:
        application.setWindowIcon(icon)

    init_db()

    theme_manager = ThemeManager(application)
    preferences = load_preferences()
    theme_manager.apply(parse_appearance(preferences.appearance), parse_accent(preferences.accent))
    # Live OS Light/Dark reaction while Appearance=System (M17 Theme
    # Completion prompt § 7.3); the one production ThemeManager opts in
    # once, here -- tests constructing their own ThemeManager never do.
    theme_manager.watch_system_appearance()

    motion = TransitionManager(policy=parse_motion_policy(preferences.motion))
    window = MainWindow(motion=motion, preferences=preferences, theme_manager=theme_manager)
    if icon is not None:
        window.setWindowIcon(icon)
    return application, window, theme_manager


def main(argv: list[str] | None = None) -> int:
    application, window, _theme_manager = build_application(argv)
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
