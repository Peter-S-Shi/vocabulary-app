from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QLabel, QPushButton, QVBoxLayout, QWidget

from src.ui_desktop.theming.metrics import NAV_RAIL_WIDTH

"""
Shared vertical left Management Navigation Rail (DESIGN.md § 5,
`VR-SHELL-001`): shell-level infrastructure, not Today-owned UI. Any
Management Mode screen reuses this same rail rather than each feature
inventing its own first-level navigation.

Only destinations with a real implemented workspace are enabled. Every
other destination from the approved product IA is still shown -- so the
rail reads as the real, frozen shell rather than a two-item placeholder --
but stays disabled with an honest "not implemented yet" affordance, per
the M17 Feature 1 fresh-implementation prompt § 6/§ 9: represent the
frozen IA, do not implement feature bodies or fake availability early.

Each item stacks a small square mark above a compact label (icon-above-
text, `VR-TODAY-001`'s canonical rail grammar) rather than icon-beside-
label, so the rail reads as a narrow navigation spine rather than a wide
text sidebar. No icon asset pipeline exists yet, so the "icon" is a
QSS-styled square swatch (`nav-rail-mark`) -- the same generic-placeholder
role the canonical wireframe itself uses (an empty checkbox glyph) --
rather than fabricated iconography. It is a `QLabel` child laid out
*inside* the `QPushButton`, not the button's own `setIcon()`/text.

M17 Theme Completion Typography Corrective Patch follow-up: the mark and
label previously resolved their active/checked color through QSS
descendant selectors combining the ancestor `QPushButton`'s *dynamic*
pseudo-state with the child's object name (`QPushButton:checked
QLabel#nav-rail-mark`). That mechanism was found to be unreliable --
confirmed empirically on both the offscreen and real native "windows" Qt
platforms, through the real `app.py` bootstrap path -- Qt's style engine
does not correctly re-evaluate the child's resolved style against the
ancestor's live pseudo-state for this selector shape; whichever
descendant rule has the highest selector specificity wins
unconditionally regardless of whether that pseudo-state actually holds.

Two of the rail's three real states are resolved differently now:

- **disabled** is static per destination (`NavDestination.enabled` never
  changes at runtime) -- resolved once, in Python, by giving the mark
  and label distinct `-disabled` object names at construction, exactly
  like `EntriesTableModel`'s state-driven roles / `today_view.py`'s
  `today-attention-label`/`-label-disabled` precedent. No live QSS
  pseudo-state involved at all.
- **active vs normal** genuinely changes at runtime (`set_active()`), so
  it needs a mechanism Qt reliably re-evaluates: a Qt dynamic property
  (`navActive`) set directly *on* the mark/label themselves (not
  inferred from an ancestor's pseudo-state), paired with an explicit
  `style().unpolish()`/`polish()` call to force re-evaluation --
  confirmed empirically reliable, unlike the descendant-selector
  approach it replaces. `theme_manager.py` targets it via
  `QLabel#nav-rail-mark[navActive="true"]`/`QLabel#nav-rail-
  label[navActive="true"]`, an attribute selector on the widget's own
  property, not a compound ancestor-pseudo-state selector.
"""


@dataclass(frozen=True)
class NavDestination:
    key: str
    label: str
    enabled: bool


PRIMARY_DESTINATIONS: tuple[NavDestination, ...] = (
    NavDestination("today", "Today", True),
    NavDestination("entries", "Entries", True),
    NavDestination("collections", "Collections", True),
    NavDestination("study", "Study", True),
    NavDestination("analytics", "Analytics", False),
    NavDestination("data_tools", "Data tools", False),
)

SETTINGS_DESTINATION = NavDestination("settings", "Settings", True)


class NavigationRail(QWidget):
    destination_activated = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("nav-rail")
        # A plain QWidget ignores QSS background-color/border unless this
        # is set (QLabel/QPushButton paint stylesheets natively via their
        # QFrame/QAbstractButton ancestry; a bare QWidget does not) --
        # found during the first native-window human visual acceptance
        # pass for this checkpoint, where the rail rendered with no
        # visible panel treatment despite the stylesheet rule existing.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(NAV_RAIL_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 12)
        layout.setSpacing(2)

        self._buttons: dict[str, QPushButton] = {}
        self._labels: dict[str, QLabel] = {}
        self._marks: dict[str, QLabel] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        for destination in PRIMARY_DESTINATIONS:
            layout.addWidget(self._build_button(destination))

        layout.addStretch(1)
        layout.addWidget(self._build_button(SETTINGS_DESTINATION))

    def _build_button(self, destination: NavDestination) -> QPushButton:
        button = QPushButton(self)
        button.setObjectName("nav-rail-item")
        button.setCheckable(True)
        button.setEnabled(destination.enabled)

        # QAbstractButton.sizeHint() computes its own preferred size from
        # style/text/icon metrics -- it does not delegate to a child
        # layout the way plain QWidget.sizeHint() does. Left unset, the
        # rail's outer layout allocated this button only its default
        # empty-text height (~23px), crushing the icon+label content
        # below into a sliver too short to render legibly (found via a
        # real on-screen capture: at any label font size, every item's
        # text rendered as an illegible dashed smear, not readable words).
        button.setMinimumHeight(52)

        content = QVBoxLayout(button)
        content.setContentsMargins(0, 6, 0, 6)
        content.setSpacing(2)

        mark = QLabel(button)
        mark.setFixedSize(18, 18)
        content.addWidget(mark, 0, Qt.AlignmentFlag.AlignHCenter)

        label = QLabel(destination.label, button)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # A safety net for a longer multi-word label ("Data tools") at
        # this narrow a rail width, not a requirement for the current
        # single-word destinations.
        label.setWordWrap(True)
        content.addWidget(label, 0, Qt.AlignmentFlag.AlignHCenter)

        if not destination.enabled:
            # Static: this destination's enabled/disabled state never
            # changes at runtime, so the disabled object names are
            # decided once, here, rather than through a live QSS
            # pseudo-state (module docstring).
            mark.setObjectName("nav-rail-mark-disabled")
            label.setObjectName("nav-rail-label-disabled")
            button.setToolTip(f"{destination.label} is not implemented yet.")
        else:
            mark.setObjectName("nav-rail-mark")
            label.setObjectName("nav-rail-label")
            label.setProperty("navActive", False)
            mark.setProperty("navActive", False)
            button.clicked.connect(lambda _checked, key=destination.key: self.destination_activated.emit(key))
        self._buttons[destination.key] = button
        self._labels[destination.key] = label
        self._marks[destination.key] = mark
        self._group.addButton(button)
        return button

    @staticmethod
    def _set_nav_active(label: QLabel, mark: QLabel, active: bool) -> None:
        """Reliable state-driven active/normal styling (module
        docstring): sets the ``navActive`` dynamic property directly on
        the mark/label themselves and forces Qt to re-evaluate their QSS
        against it -- unlike a descendant-pseudo-state selector, this is
        reliably re-applied on every call."""
        for widget in (label, mark):
            widget.setProperty("navActive", active)
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def set_active(self, key: str) -> None:
        button = self._buttons.get(key)
        if button is not None:
            button.setChecked(True)
        for destination_key, target_button in self._buttons.items():
            if not target_button.isEnabled():
                continue  # disabled destinations render statically; not part of the active/normal distinction
            self._set_nav_active(
                self._labels[destination_key], self._marks[destination_key], destination_key == key
            )

    def is_enabled_destination(self, key: str) -> bool:
        button = self._buttons.get(key)
        return button is not None and button.isEnabled()

    def destination_keys(self) -> list[str]:
        return list(self._buttons.keys())
