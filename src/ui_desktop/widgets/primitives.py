from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.ui_desktop.theming.tokens import METRICS

"""
Shared desktop UI primitives.

These exist so the product's visual grammar is applied consistently by
*construction* rather than re-implemented per screen: every workspace that
needs a page header, a section heading, a panel surface, a metric tile, or
an empty state uses the same primitive, and therefore inherits the same
typography step, spacing rhythm, and surface treatment from
``theming/theme_manager.py``'s stylesheet.

Each primitive only sets structure plus the semantic selector properties
(``typography``, ``surface``) the stylesheet keys off. **No primitive
hardcodes a color** -- colors resolve from the active theme's tokens, so
Light/Dark and any future accent family work without touching this module
(DESIGN.md § 8/§ 9).

Deliberately small: these are the concerns that are already genuinely
cross-cutting for M17's screens. This is not a general-purpose component
framework, and speculative components for hypothetical future needs do not
belong here.
"""


def _apply(widget: QWidget, **properties: object) -> QWidget:
    """Set stylesheet selector properties before first polish."""
    for name, value in properties.items():
        widget.setProperty(name, value)
    return widget


class PageHeader(QWidget):
    """Page title, with optional one-line subtitle beneath it.

    The top of every management workspace, giving the user an unambiguous
    "where am I" anchor at the page-title typography step (DESIGN.md § 15).
    """

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.title_label = _apply(QLabel(title, self), typography="page-title")
        self.subtitle_label = _apply(QLabel(subtitle, self), typography="page-subtitle")
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setVisible(bool(subtitle))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(METRICS.space_xs)
        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)

    def set_subtitle(self, subtitle: str) -> None:
        self.subtitle_label.setText(subtitle)
        self.subtitle_label.setVisible(bool(subtitle))


class SectionHeading(QLabel):
    """Labels a content region below the page title (DESIGN.md § 15).

    Visually subordinate to the page title and distinct from body text, so
    a screen reads as structured regions rather than a flat stack of
    similar-looking labels.
    """

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text.upper(), parent)
        _apply(self, typography="section-heading")

    def setText(self, text: str) -> None:  # noqa: N802 (Qt API)
        super().setText(text.upper())


class Panel(QFrame):
    """A content surface that groups related supporting information.

    Uses the ``surface`` token role rather than an ad hoc border so panels
    read as intentional product surfaces and stay coherent in Dark Mode,
    where DESIGN.md § 13 requires real separation between app background,
    content surface, and elevated surfaces.
    """

    def __init__(
        self,
        heading: str = "",
        parent: QWidget | None = None,
        *,
        surface: str = "panel",
    ) -> None:
        super().__init__(parent)
        _apply(self, surface=surface)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(
            METRICS.space_lg, METRICS.space_md, METRICS.space_lg, METRICS.space_md
        )
        self._layout.setSpacing(METRICS.space_sm)

        self.heading_label: SectionHeading | None = None
        if heading:
            self.heading_label = SectionHeading(heading, self)
            self._layout.addWidget(self.heading_label)

    def body_layout(self) -> QVBoxLayout:
        return self._layout

    def add_widget(self, widget: QWidget, stretch: int = 0) -> None:
        self._layout.addWidget(widget, stretch)


class MetricTile(QFrame):
    """One compact figure plus its label.

    Today's summary row is built from these. They are intentionally small
    and quiet: DESIGN.md § 4.1 requires the Learning Queue to carry greater
    visual weight than statistics, and § 18 lists a chart-heavy dashboard
    as a Today anti-pattern. A tile states a number; it does not compete
    with the queue.
    """

    def __init__(
        self,
        label: str,
        value: str = "--",
        parent: QWidget | None = None,
        *,
        emphasized: bool = False,
    ) -> None:
        super().__init__(parent)
        _apply(self, surface="accent-tile" if emphasized else "tile")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.value_label = _apply(QLabel(value, self), typography="metric-value")
        self.label_label = _apply(QLabel(label, self), typography="metric-label")
        self.label_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            METRICS.space_md, METRICS.space_md, METRICS.space_md, METRICS.space_md
        )
        layout.setSpacing(METRICS.space_xs)
        layout.addWidget(self.value_label)
        layout.addWidget(self.label_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class EmptyState(QWidget):
    """Explains why a region is empty instead of leaving it blank.

    DESIGN.md § 16 requires an empty state to say what would appear here
    and, where applicable, how to populate it -- "never a bare blank area".
    """

    def __init__(self, message: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.message_label = _apply(QLabel(message, self), typography="empty-state")
        self.message_label.setWordWrap(True)
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            METRICS.space_xl, METRICS.space_xl, METRICS.space_xl, METRICS.space_xl
        )
        layout.addStretch(1)
        layout.addWidget(self.message_label)
        layout.addStretch(1)

    def set_message(self, message: str) -> None:
        self.message_label.setText(message)


class StatusPill(QLabel):
    """Compact status marker (``neutral`` / ``accent`` / ``warning``).

    Tone is a semantic token role, never a hand-picked color, so status
    meaning stays stable across accent families (DESIGN.md § 10).
    """

    def __init__(self, text: str, tone: str = "neutral", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        _apply(self, pill=tone)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

    def set_tone(self, tone: str) -> None:
        self.setProperty("pill", tone)
        # A property change after first polish needs an explicit repolish
        # for the new selector branch to take effect.
        style = self.style()
        style.unpolish(self)
        style.polish(self)


class HorizontalDivider(QFrame):
    """A hairline separator using the decorative border token."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        _apply(self, surface="divider")
        self.setFixedHeight(1)


def build_row(*widgets: QWidget, spacing: int = METRICS.space_md) -> QHBoxLayout:
    """A horizontal run of widgets on the shared spacing rhythm."""
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)
    for widget in widgets:
        layout.addWidget(widget)
    return layout
