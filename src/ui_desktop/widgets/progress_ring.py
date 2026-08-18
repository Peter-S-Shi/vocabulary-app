from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from src.ui_desktop.theming.tokens import THEME_CALM_BLUE_LIGHT

"""
A small determinate circular progress indicator ("progress ring").

Final Human Acceptance Gate corrective: the Data Tools hub's Audio
Export action runs a live provider preflight whose Mandarin route spawns
``powershell.exe`` (``src/tts_providers.py``'s
``CommandSpeechProvider.preflight``), which costs seconds on a real
machine. The operator asked specifically for a ring beside that button
that starts hollow and fills in as the work completes, so the wait is
visible rather than the button appearing dead.

Qt ships no circular progress widget, so this paints one directly: a
full-circle track plus a foreground arc sweeping clockwise from 12
o'clock in proportion to ``value/maximum``. It is deliberately
determinate -- the preflight reports real completed-language counts
(``_VoicePreflightWorker``), so the ring shows truthful progress rather
than a decorative spin.

Colors are supplied by the caller from the active theme's semantic
tokens (``apply_theme_colors``) rather than hardcoded here, so the ring
follows Light/Dark like every other themed surface. Painting happens in
``paintEvent`` rather than through QSS because QSS cannot express an
arc.
"""

DEFAULT_DIAMETER = 18
DEFAULT_THICKNESS = 3


class ProgressRing(QWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        diameter: int = DEFAULT_DIAMETER,
        thickness: int = DEFAULT_THICKNESS,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("progress-ring")
        self._diameter = max(8, int(diameter))
        self._thickness = max(1, int(thickness))
        self._value = 0
        self._maximum = 1
        # Seeded from real semantic tokens, never a hard-coded literal:
        # the M17 typography-hierarchy guard
        # (tests/test_m17_theme_typography_hierarchy_patch.py) forbids
        # undocumented hex colors in the view layer, and it is right to
        # -- a literal here would silently ignore the active theme until
        # apply_theme_colors() happened to run. MainWindow pushes the
        # live theme through apply_theme_colors(); these defaults only
        # cover the window between construction and that first push.
        self._track_color = QColor(THEME_CALM_BLUE_LIGHT.neutral.border_default)
        self._arc_color = QColor(THEME_CALM_BLUE_LIGHT.accent.primary.background)
        self.setFixedSize(self._diameter, self._diameter)

    def sizeHint(self) -> QSize:
        return QSize(self._diameter, self._diameter)

    def apply_theme_colors(self, track: str, arc: str) -> None:
        """Adopt the active theme's tokens (border/accent), so the ring
        re-themes with everything else instead of carrying a hardcoded
        palette."""
        self._track_color = QColor(track)
        self._arc_color = QColor(arc)
        self.update()

    def set_progress(self, value: int, maximum: int) -> None:
        """``value`` of ``maximum`` completed. A non-positive maximum is
        treated as 1 so the ring can never divide by zero or render a
        nonsensical sweep."""
        self._maximum = max(1, int(maximum))
        self._value = max(0, min(int(value), self._maximum))
        self.update()

    def reset(self) -> None:
        """Back to fully hollow -- the state the operator asked the ring
        to start from."""
        self.set_progress(0, self._maximum)

    def progress_ratio(self) -> float:
        return self._value / self._maximum

    def paintEvent(self, event) -> None:  # noqa: N802 -- Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        inset = self._thickness / 2 + 0.5
        rect = QRectF(inset, inset, self.width() - 2 * inset, self.height() - 2 * inset)

        track_pen = QPen(self._track_color, self._thickness)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        painter.drawEllipse(rect)

        if self._value > 0:
            arc_pen = QPen(self._arc_color, self._thickness)
            arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(arc_pen)
            # Qt angles are in 1/16 degree units; 90*16 starts at 12
            # o'clock and a negative span sweeps clockwise.
            span = int(-360 * 16 * self.progress_ratio())
            painter.drawArc(rect, 90 * 16, span)
        painter.end()
