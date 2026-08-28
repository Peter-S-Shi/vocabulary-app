from __future__ import annotations

import os
import sys
from pathlib import Path

"""
PyInstaller entry-point script for the Windows desktop build (M20
Release Contract § 2.5 "PyInstaller --onedir + Inno Setup").

PyInstaller's ``Analysis`` needs a real ``.py`` script, not a ``python
-m src.ui_desktop`` invocation -- this is that script, and nothing
else: it locates the repository root relative to itself so ``src`` is
importable, then delegates straight to the same
``src.ui_desktop.app.main()`` the ``python -m src.ui_desktop`` dev
launch already uses. No packaging-specific application logic lives
here.
"""

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def _run_smoke_test() -> int:
    """Headless import & startup smoke test for packaged bundle verification."""
    # Verify core external dependencies required by desktop app
    import openpyxl  # noqa: F401
    import src.backup  # noqa: F401
    import src.import_export  # noqa: F401
    import src.ui_desktop.app  # noqa: F401
    import src.ui_desktop.main_window  # noqa: F401

    print("PACKAGED_SMOKE_TEST_PASSED")
    return 0


if __name__ == "__main__":
    if "--smoke-test" in sys.argv or os.environ.get("VOCAB_APP_SMOKE_TEST") == "1":
        raise SystemExit(_run_smoke_test())
    from src.ui_desktop.app import main  # noqa: E402

    raise SystemExit(main())
