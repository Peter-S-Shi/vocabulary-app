from __future__ import annotations

import sys

from src.app_config import DataRootError


def run_desktop() -> int:
    """Report an unsafe selected data root before Qt or SQLite can open it."""
    try:
        from src.ui_desktop.app import main

        return main()
    except DataRootError as error:
        message = str(error)
        if sys.stderr is not None:
            print(message, file=sys.stderr)
        if sys.platform == "win32" and (getattr(sys, "frozen", False) or sys.stderr is None):
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                None, message, "Vocabulary App — Data Location", 0x10
            )
        return 2
