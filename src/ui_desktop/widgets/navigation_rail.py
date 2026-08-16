from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QPushButton, QVBoxLayout, QWidget

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
        button = QPushButton(destination.label, self)
        button.setObjectName("nav-rail-item")
        button.setCheckable(True)
        button.setEnabled(destination.enabled)
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
