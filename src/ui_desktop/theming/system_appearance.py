from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

"""
The one platform/theme abstraction M17 Theme Completion introduces for
resolving ``Appearance.SYSTEM`` to a real, current OS Light/Dark value
(M17 Theme Completion prompt § 7).

Backed directly by Qt's own ``QStyleHints.colorScheme()`` (Qt 6.5+), which
reads each platform's native OS-level appearance hook (on Windows, the
same signal DWM itself uses) rather than polling a Windows-specific
registry key -- the "cleaner Qt abstraction" the prompt asks for in
preference to a hand-rolled, platform-specific watcher. ``colorScheme()``
returns ``Qt.ColorScheme.Unknown`` when the platform cannot report an
appearance; callers (``theme_manager.py``) are responsible for the
documented safe fallback, not this module -- this module only ever
reports what Qt actually detected.

Qt also emits ``colorSchemeChanged`` on the same ``QStyleHints`` object
whenever the OS appearance changes live, so no additional polling loop is
needed to react to a running OS theme change; ``ThemeManager.
watch_system_appearance()`` connects to it directly.
"""


def detect_system_color_scheme() -> Qt.ColorScheme:
    """Return the OS's current Light/Dark/Unknown appearance, read live
    (not cached) on every call."""
    return QGuiApplication.styleHints().colorScheme()
