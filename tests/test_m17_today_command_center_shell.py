from __future__ import annotations

import os
import re
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QWidget

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when PySide6 is absent
    PYSIDE6_AVAILABLE = False

from src import db
from src.collections import add_entries_to_collection, create_collection
from src.entries import add_entry

"""
Focused tests for the M17 fresh Today Command Center + shared Management
Rail (DESIGN.md § 5 `VR-SHELL-001`, § 6.1 `VR-TODAY-001`), implemented
from the replacement DESIGN authority after the controlled reset.

Per DESIGN.md § 2 Rule C, none of this proves the canonical composition
was *visually* realized -- only that the required regions/behaviors exist
structurally and that the desktop layer still reads real reusable-core
data without duplicating business logic. Native human visual acceptance
is a separate, required gate (see AGENTS.md).
"""

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if PYSIDE6_AVAILABLE:
    from src.ui_desktop.controllers.today_controller import TodayController
    from src.ui_desktop.main_window import MainWindow
    from src.ui_desktop.state.app_state import Workspace
    from src.ui_desktop.theming.metrics import CONTEXT_RAIL_WIDTH, NAV_RAIL_WIDTH
    from src.ui_desktop.state.handoff import QuizLaunchIntent
    from src.ui_desktop.views.today_view import TodayView
    from src.ui_desktop.theming.theme_manager import build_stylesheet
    from src.ui_desktop.theming.tokens import THEME_CALM_BLUE_DARK, THEME_CALM_BLUE_LIGHT
    from src.ui_desktop.widgets.navigation_rail import (
        PRIMARY_DESTINATIONS,
        SETTINGS_DESTINATION,
        NavDestination,
        NavigationRail,
    )

    def _qt_app() -> QApplication:
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app


class _SyntheticDatabaseTestCase(unittest.TestCase):
    """Shared setup matching the existing repository pattern (see
    tests/test_m16_2_desktop_vertical_slice.py): swap db.DB_PATH to a
    temporary synthetic database, never the user's personal data/vocab.db."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp_dir.name)
        self.original_db_path = db.DB_PATH
        db.DB_PATH = self.root / "m17_today_shell.sqlite3"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class NavigationRailStructureTests(unittest.TestCase):
    """`VR-SHELL-001`: only implemented destinations were functional
    while the desktop product was still being built, with every other
    approved-IA destination still represented but honestly disabled
    (M17 Feature 1 fresh-implementation prompt § 6/§ 9). As of M18 Phase
    D, every destination in the approved product IA has a real
    workspace; the disabled-rendering mechanism itself remains covered
    via a synthetic destination for whenever a future IA item needs it
    again."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_every_approved_ia_destination_is_now_enabled(self) -> None:
        """Updated for M17 Feature 2 (Review): "study" is the rail's real
        entry point into Study Mode / Review now that real Study content
        exists, per the M17 Feature 2 prompt's "smallest shared-shell
        wiring genuinely required to make Review reachable". Updated for
        M17 Feature 3B: Settings now has a real minimum workspace (Quiz
        presentation), so it is enabled too. Updated for M17 Minimum
        Collection Integration: Collections now has a real minimum
        workspace (Collections Navigator), so it is enabled too. Updated
        for M18.1 Template Manager: Templates now has a real workspace
        too. Updated for M18 Phase C1/C3: Review Calendar and Data Tools
        now have real workspaces too. Updated for M18 Phase D: Analytics
        now has a real workspace too -- every destination in the approved
        product IA (DESIGN.md § 4.1) is now enabled; the "honestly
        disabled placeholder" mechanism itself remains real product code
        (see the synthetic-destination tests below) for whenever a future
        IA item is added ahead of its own workspace, but has zero live
        instances in the shipped rail as of this checkpoint."""
        rail = NavigationRail()
        self.addCleanup(rail.deleteLater)

        enabled = {d.key for d in PRIMARY_DESTINATIONS if d.enabled} | (
            {SETTINGS_DESTINATION.key} if SETTINGS_DESTINATION.enabled else set()
        )
        disabled = {d.key for d in PRIMARY_DESTINATIONS if not d.enabled} | (
            set() if SETTINGS_DESTINATION.enabled else {SETTINGS_DESTINATION.key}
        )

        self.assertEqual(
            enabled,
            {
                "today",
                "entries",
                "collections",
                "templates",
                "review_calendar",
                "data_tools",
                "analytics",
                "study",
                "settings",
            },
        )
        self.assertEqual(disabled, set())
        for key in enabled:
            self.assertTrue(rail.is_enabled_destination(key), key)

    def test_a_disabled_destination_carries_an_honest_tooltip(self) -> None:
        """No destination is currently disabled (see the test above); this
        exercises the still-real disabled-rendering mechanism directly via
        a synthetic destination, the same way `_build_button` renders any
        real one, so the contract stays covered for whenever it is next
        needed."""
        rail = NavigationRail()
        self.addCleanup(rail.deleteLater)

        button = rail._build_button(NavDestination("synthetic_test_destination", "Synthetic", False))

        self.assertFalse(button.isEnabled())
        self.assertIn("not implemented yet", button.toolTip())

    def test_set_active_checks_exactly_one_button(self) -> None:
        rail = NavigationRail()
        self.addCleanup(rail.deleteLater)

        rail.set_active("entries")
        checked = [key for key, button in rail._buttons.items() if button.isChecked()]
        self.assertEqual(checked, ["entries"])

        rail.set_active("today")
        checked = [key for key, button in rail._buttons.items() if button.isChecked()]
        self.assertEqual(checked, ["today"])

    def test_clicking_enabled_button_emits_destination_activated(self) -> None:
        rail = NavigationRail()
        self.addCleanup(rail.deleteLater)

        received: list[str] = []
        rail.destination_activated.connect(received.append)

        rail._buttons["entries"].click()

        self.assertEqual(received, ["entries"])

    def test_clicking_disabled_button_emits_nothing(self) -> None:
        """No destination is currently disabled; this documents Qt's
        guarantee that a disabled QPushButton never delivers clicked()
        using a synthetic destination, the same way the mechanism above
        does."""
        rail = NavigationRail()
        self.addCleanup(rail.deleteLater)

        received: list[str] = []
        rail.destination_activated.connect(received.append)
        button = rail._build_button(NavDestination("synthetic_test_destination", "Synthetic", False))

        button.click()

        self.assertEqual(received, [])


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class NavigationRailReliableStateTests(unittest.TestCase):
    """Corrective follow-up to the M17 Theme Completion Typography
    Corrective Patch: the mark/label's active/normal/disabled color no
    longer depends on a QSS descendant-pseudo-state selector against
    `nav-rail-item`'s dynamic checked/disabled state (confirmed
    unreliable -- see navigation_rail.py's module docstring). These
    tests cover what actually determines the rendered color now: object
    name (static, disabled) and the `navActive` dynamic property
    (runtime, active vs normal), plus the QSS that resolves them."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_disabled_destinations_get_static_disabled_object_names(self) -> None:
        """No destination is currently disabled; this exercises the
        still-real static-object-name mechanism via a synthetic
        destination, the same way `NavigationRailStructureTests` above
        does for the tooltip/click-suppression contract."""
        rail = NavigationRail()
        self.addCleanup(rail.deleteLater)

        rail._build_button(NavDestination("synthetic_test_destination", "Synthetic", False))

        self.assertEqual(rail._labels["synthetic_test_destination"].objectName(), "nav-rail-label-disabled")
        self.assertEqual(rail._marks["synthetic_test_destination"].objectName(), "nav-rail-mark-disabled")

    def test_enabled_destinations_get_the_plain_object_names(self) -> None:
        rail = NavigationRail()
        self.addCleanup(rail.deleteLater)

        for key in ("today", "entries", "collections", "study", "settings"):
            self.assertEqual(rail._labels[key].objectName(), "nav-rail-label")
            self.assertEqual(rail._marks[key].objectName(), "nav-rail-mark")

    def test_set_active_sets_navActive_true_only_on_the_target_destination(self) -> None:
        rail = NavigationRail()
        self.addCleanup(rail.deleteLater)

        rail.set_active("entries")

        for key in ("today", "entries", "collections", "study", "settings"):
            expected = key == "entries"
            self.assertEqual(rail._labels[key].property("navActive"), expected, key)
            self.assertEqual(rail._marks[key].property("navActive"), expected, key)

    def test_set_active_moves_navActive_off_the_previously_active_destination(self) -> None:
        rail = NavigationRail()
        self.addCleanup(rail.deleteLater)

        rail.set_active("today")
        self.assertTrue(rail._labels["today"].property("navActive"))

        rail.set_active("study")
        self.assertFalse(rail._labels["today"].property("navActive"))
        self.assertTrue(rail._labels["study"].property("navActive"))

    def test_set_active_never_touches_disabled_destinations(self) -> None:
        """Disabled destinations render statically and are never part of
        the active/normal distinction (module docstring); ``navActive``
        is never even set on them. No destination is currently disabled,
        so this registers a synthetic one first (`set_active()` iterates
        whatever `self._buttons` actually holds, so a button registered
        via `_build_button()` alone -- never added to the rail's layout --
        still exercises the same live code path)."""
        rail = NavigationRail()
        self.addCleanup(rail.deleteLater)
        rail._build_button(NavDestination("synthetic_test_destination", "Synthetic", False))

        rail.set_active("today")
        rail.set_active("entries")

        self.assertIsNone(rail._labels["synthetic_test_destination"].property("navActive"))
        self.assertIsNone(rail._marks["synthetic_test_destination"].property("navActive"))

    def test_navigation_rail_qss_no_longer_uses_the_unreliable_descendant_selectors(self) -> None:
        """Regression guard against the fixed mechanism silently coming
        back: the old `QPushButton:checked/:disabled/:hover
        QLabel#nav-rail-*` compound selectors must not reappear."""
        stylesheet = build_stylesheet(THEME_CALM_BLUE_LIGHT)
        for broken_selector in (
            "QPushButton#nav-rail-item:checked QLabel#nav-rail-mark",
            "QPushButton#nav-rail-item:checked QLabel#nav-rail-label",
            "QPushButton#nav-rail-item:disabled QLabel#nav-rail-mark",
            "QPushButton#nav-rail-item:disabled QLabel#nav-rail-label",
            "QPushButton#nav-rail-item:hover:enabled QLabel#nav-rail-mark",
        ):
            self.assertNotIn(broken_selector, stylesheet, broken_selector)

    def test_navigation_rail_qss_resolves_active_normal_disabled_to_distinct_tokens(self) -> None:
        for name, tokens in {"Light": THEME_CALM_BLUE_LIGHT, "Dark": THEME_CALM_BLUE_DARK}.items():
            stylesheet = build_stylesheet(tokens)
            self.assertIn(f'QLabel#nav-rail-label[navActive="true"] {{\n        color: {tokens.neutral.text_primary};', stylesheet, name)
            self.assertIn(f"QLabel#nav-rail-label {{\n        background-color: transparent;\n        color: {tokens.neutral.text_secondary};", stylesheet, name)
            self.assertIn(f"QLabel#nav-rail-label-disabled {{\n        background-color: transparent;\n        color: {tokens.neutral.text_disabled};", stylesheet, name)
            self.assertIn(f'QLabel#nav-rail-mark[navActive="true"] {{\n        background-color: {tokens.accent.primary.background};\n        border-color: {tokens.accent.primary.background};', stylesheet, name)
            self.assertIn(f"QLabel#nav-rail-mark-disabled {{\n        background-color: transparent;\n        border: 1.5px solid {tokens.neutral.border_subtle};", stylesheet, name)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class MainWindowShellStructureTests(_SyntheticDatabaseTestCase):
    """`VR-SHELL-001` Global Management Shell Contract: vertical left rail
    + workspace, rail subordinate/fixed-width, workspace dominant."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_rail_is_fixed_width_and_workspace_dominates(self) -> None:
        window = MainWindow()
        self.addCleanup(window.close)

        # setFixedWidth() pins min==max immediately; .width() only reflects
        # it after a layout pass, so assert the pinned bounds directly
        # rather than depending on show()/processEvents() timing.
        self.assertEqual(window._navigation_rail.minimumWidth(), NAV_RAIL_WIDTH)
        self.assertEqual(window._navigation_rail.maximumWidth(), NAV_RAIL_WIDTH)
        shell_layout = window.centralWidget().layout()
        self.assertEqual(shell_layout.stretch(0), 0)  # rail
        self.assertEqual(shell_layout.stretch(1), 1)  # workspace stack

    def test_clicking_rail_destination_navigates_and_updates_selection(self) -> None:
        window = MainWindow()
        self.addCleanup(window.close)

        window._navigation_rail._buttons["entries"].click()

        self.assertIs(window.current_workspace(), Workspace.ENTRIES)
        self.assertIs(window._workspace_stack.currentWidget(), window.entries_view)
        self.assertTrue(window._navigation_rail._buttons["entries"].isChecked())

        window._navigation_rail._buttons["today"].click()

        self.assertIs(window.current_workspace(), Workspace.TODAY)
        self.assertTrue(window._navigation_rail._buttons["today"].isChecked())

    def test_today_view_entries_handoff_navigates_through_appstate(self) -> None:
        """The Today -> Entries handoff (Organize / Open Entries buttons)
        must go through AppState like every other navigation, never touch
        the widget stack directly."""
        window = MainWindow()
        self.addCleanup(window.close)

        window.today_view.navigate_to_entries_requested.emit()

        self.assertIs(window.app_state.workspace, Workspace.ENTRIES)
        self.assertIs(window.current_workspace(), Workspace.ENTRIES)
        self.assertIs(window._workspace_stack.currentWidget(), window.entries_view)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class TodayViewRegionStructureTests(_SyntheticDatabaseTestCase):
    """`VR-TODAY-001` § 6.1 frozen composition: Center Command Workspace
    (dominant) + right Context Rail (secondary, fixed width)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_command_workspace_dominates_context_rail(self) -> None:
        controller = TodayController()
        view = TodayView(controller)
        self.addCleanup(view.deleteLater)

        layout = view.layout()
        self.assertEqual(layout.count(), 2)
        self.assertGreater(layout.stretch(0), layout.stretch(1))

    def test_context_rail_has_fixed_secondary_width(self) -> None:
        controller = TodayController()
        view = TodayView(controller)
        self.addCleanup(view.deleteLater)

        context_rail = next(
            child
            for child in view.children()
            if getattr(child, "objectName", lambda: "")() == "today-context-rail"
        )
        self.assertEqual(context_rail.minimumWidth(), CONTEXT_RAIL_WIDTH)
        self.assertEqual(context_rail.maximumWidth(), CONTEXT_RAIL_WIDTH)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class TodayViewFunctionalHonestyTests(_SyntheticDatabaseTestCase):
    """M17 Feature 1 fresh-implementation prompt § 9, updated by M17
    Feature 3: a Learning Queue "quiz" action now has a real, data-complete
    target and launches a real Quiz; only genuinely under-specified/
    unsupported actions stay honestly disabled."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qt_app()

    def test_never_quizzed_queue_item_renders_enabled_quiz_button_that_launches(self) -> None:
        entry_a = add_entry("French", "English", "word", "chat", "cat")
        entry_b = add_entry("French", "English", "word", "chien", "dog")
        collection_id = create_collection("Shell Test Collection", card_size=2)
        add_entries_to_collection([entry_a, entry_b], collection_id)

        controller = TodayController()
        view = TodayView(controller)
        self.addCleanup(view.deleteLater)
        controller.refresh()

        cards = [
            child
            for child in view.findChildren(QWidget)
            if getattr(child, "objectName", lambda: "")() == "today-queue-card"
        ]
        self.assertGreater(len(cards), 0)

        quiz_buttons = [
            button
            for card in cards
            for button in card.findChildren(QWidget)
            if getattr(button, "objectName", lambda: "")() == "today-action-button"
            and button.text() == "Quiz"
        ]
        self.assertGreater(len(quiz_buttons), 0)
        for button in quiz_buttons:
            self.assertTrue(button.isEnabled())

        received: list[object] = []
        view.quiz_launch_requested.connect(received.append)
        quiz_buttons[0].click()

        self.assertEqual(len(received), 1)
        intent = received[0]
        self.assertIsInstance(intent, QuizLaunchIntent)
        self.assertEqual(intent.collection_id, collection_id)
        self.assertEqual(intent.card_number, 1)
        self.assertEqual(intent.source, "today_queue")

    def test_organize_suggestion_button_is_enabled_and_navigates_to_entries(self) -> None:
        add_entry("French", "English", "word", "loup", "wolf")  # uncollected -> recent-entries suggestion

        controller = TodayController()
        view = TodayView(controller)
        self.addCleanup(view.deleteLater)
        controller.refresh()

        received: list[int] = []
        view.navigate_to_entries_requested.connect(lambda: received.append(1))

        organize_buttons = [
            button
            for card in view.findChildren(QWidget)
            if getattr(card, "objectName", lambda: "")() == "today-queue-card"
            for button in card.findChildren(QWidget)
            if getattr(button, "objectName", lambda: "")() == "today-action-button" and button.isEnabled()
        ]
        self.assertGreater(len(organize_buttons), 0)
        organize_buttons[0].click()

        self.assertEqual(received, [1])

    def test_empty_database_produces_honest_empty_states_not_a_crash(self) -> None:
        controller = TodayController()
        view = TodayView(controller)
        self.addCleanup(view.deleteLater)

        controller.refresh()  # empty synthetic DB: no queue items, no activity

        empty_labels = [
            child
            for child in view.findChildren(QWidget)
            if getattr(child, "objectName", lambda: "")() == "today-empty-state"
        ]
        self.assertGreater(len(empty_labels), 0)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 is not installed; see requirements-desktop.txt.")
class ShellCoreBoundaryTests(unittest.TestCase):
    """Reusable-core boundary guards (M16.1 contract): the new shell/Today
    widgets orchestrate presentation only, they do not reimplement domain
    behavior or touch the database directly."""

    FILES = (
        PROJECT_ROOT / "src" / "ui_desktop" / "widgets" / "navigation_rail.py",
        PROJECT_ROOT / "src" / "ui_desktop" / "widgets" / "panels.py",
        PROJECT_ROOT / "src" / "ui_desktop" / "views" / "today_view.py",
    )

    def test_no_raw_sql_and_no_direct_db_import(self) -> None:
        for path in self.FILES:
            text = path.read_text(encoding="utf-8")
            upper = text.upper()
            for forbidden in ("SELECT ", "INSERT INTO ", "DELETE FROM "):
                with self.subTest(path=path.name, forbidden=forbidden):
                    self.assertNotIn(forbidden, upper)
            # Match SQL UPDATE statements (e.g. UPDATE <table> SET ...)
            self.assertFalse(re.search(r"\bUPDATE\s+\w+\s+SET\b", upper), f"Raw SQL UPDATE statement found in {path.name}")
            with self.subTest(path=path.name):
                self.assertNotIn("import sqlite3", text)
                self.assertNotIn("from src import db", text)


if __name__ == "__main__":
    unittest.main()
