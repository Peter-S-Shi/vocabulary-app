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
*inside* the `QPushButton`, not the button's own `setIcon()`/text: this
lets both it and the label resolve theme tokens through ordinary QSS
descendant selectors (`QPushButton:checked QLabel#nav-rail-mark`) that
refresh automatically alongside the button's checked/disabled state, with
no per-instance runtime icon generation or hardcoded color.
"""


@dataclass(frozen=True)
class NavDestination:
    key: str
    label: str
    enabled: bool


PRIMARY_DESTINATIONS: tuple[NavDestination, ...] = (
    NavDestination("today", "Today", True),
    NavDestination("entries", "Entries", True),
    NavDestination("collections", "Collections", False),
    NavDestination("study", "Study", False),
    NavDestination("analytics", "Analytics", False),
    NavDestination("data_tools", "Data tools", False),
)

SETTINGS_DESTINATION = NavDestination("settings", "Settings", False)


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

        content = QVBoxLayout(button)
        content.setContentsMargins(0, 6, 0, 6)
        content.setSpacing(2)

        mark = QLabel(button)
        mark.setObjectName("nav-rail-mark")
        mark.setFixedSize(18, 18)
        content.addWidget(mark, 0, Qt.AlignmentFlag.AlignHCenter)

        label = QLabel(destination.label, button)
        label.setObjectName("nav-rail-label")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content.addWidget(label, 0, Qt.AlignmentFlag.AlignHCenter)

        if not destination.enabled:
            button.setToolTip(f"{destination.label} is not implemented yet.")
        else:
            button.clicked.connect(lambda _checked, key=destination.key: self.destination_activated.emit(key))
        self._buttons[destination.key] = button
        self._group.addButton(button)
        return button

    def set_active(self, key: str) -> None:
        button = self._buttons.get(key)
        if button is not None:
            button.setChecked(True)

    def is_enabled_destination(self, key: str) -> bool:
        button = self._buttons.get(key)
        return button is not None and button.isEnabled()

    def destination_keys(self) -> list[str]:
        return list(self._buttons.keys())
