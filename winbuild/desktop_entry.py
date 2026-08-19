from __future__ import annotations

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

from src.ui_desktop.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
