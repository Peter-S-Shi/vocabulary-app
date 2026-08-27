from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.collections import CROSS_CARD_CONFIRMATION_MESSAGE, CrossCardMoveConfirmationRequired
from src.template_quiz import TEMPLATE_FIELD_MATCHING, TEMPLATE_FIELD_MCQ, TEMPLATE_FIELD_SELF_GRADED
from src.time_utils import format_local_timestamp
from src.ui_desktop.controllers.review_controller import QUIZ_TYPE_LABELS, QUICK_QUIZ_DEFAULT_TYPE, ReviewController
from src.ui_desktop.theming.metrics import SPACING

"""
Review / Study Mode -- Immersive Focus (DESIGN.md § 6.3 `VR-STUDY-001`:
`Review - Quiz.pdf` p4 Variant C; parent pattern P3 -- Immersive Study,
DESIGN.md § 8). Fresh implementation of M17 Feature 2, built against the
same replacement DESIGN authority that governs the accepted Today Command
Center -- not a Streamlit page port (``src/ui_streamlit/review_page.py``
is a behavioral reference only, per ARCHITECTURE.md's Streamlit-is-not-
the-desktop-authority rule).

Design → Implementation trace:

  Study Mode shell/chrome    -> MainWindow hides NavigationRail and its
                                 own generic ``_study_toolbar`` while this
                                 view supplies the one real session bar
                                 (composition rule: "a minimal session bar
                                 remains", singular -- not a second bar
                                 stacked above it).
  session bar                -> _build_session_bar(): Exit + Collection ·
                                 Card + Review i/N progress + the
                                 collapsed "Card contents" pill.
  dominant learning region   -> _build_main_surface(): term dominant,
                                 Meaning/Example quiet supporting text,
                                 generous whitespace, bounded column width
                                 so centered text stays readable at full
                                 window width (native adaptation, not a
                                 composition change).
  Collection/Card context    -> session bar label + _StudyCardSelectorDialog
                                 (P6 transient utility, DESIGN.md § 8 P6 /
                                 line ~681 "Study Collection/Card selector").
  Card/Entry navigation      -> Previous/Next walk Entries *within* the
                                 current Card, matching the canonical
                                 reference's "Review 3/8" progress
                                 (Entry position in an 8-Entry Card, not a
                                 Card-to-Card counter).
  Card Contents / History    -> _CardContentsDrawer: transient right
                                 drawer (DESIGN.md § 6.3), reveal/hide via
                                 the existing shared ``TransitionManager``
                                 (fade_in), never a permanent inspector.
  Quick Quiz                 -> real launch (M17 Feature 3): builds a
                                 QuizLaunchIntent (deterministic
                                 QUICK_QUIZ_DEFAULT_TYPE for the current
                                 Card) and emits ``quiz_launch_requested``;
                                 MainWindow starts the real QuizController
                                 session and switches to the Quiz
                                 workspace. Review itself still never calls
                                 src.quiz/src.template_quiz directly.
  Choose Quiz Type           -> _ChooseQuizTypeDialog (P6 utility): a real
                                 type picker (plain types, whole-Collection
                                 Matching with an item-count choice, and an
                                 optional template-aware section when the
                                 current Card has eligible template
                                 sources) whose "Start Quiz" builds a real
                                 QuizLaunchIntent and emits it -- no more
                                 temporary unavailable-message state (that
                                 was explicitly transitional, per the M17
                                 Feature 3 prompt § 1).
  interaction containers     -> P3 main surface + P6 transient drawer/
                                 dialogs, per DESIGN.md § 10's Editing
                                 Container Decision ("Study context is
                                 shown through transient drawers, not
                                 permanent inspectors").
  motion                     -> reuses ``TransitionManager.fade_in`` for
                                 the drawer reveal; no second animation
                                 system.
  canonical-reference         -> `Review - Quiz.pdf` p4 Variant C
  relationship                  (`VR-STUDY-001`), primary and frozen;
                                 Variant D (`VR-STUDY-002`, Flip Card +
                                 Filmstrip) is a separate optional surface
                                 this checkpoint does not build.
  native human-acceptance     -> default Review state, drawer open/closed,
  target                        Previous/Next bounds, Choose Quiz Type
                                 dialog, exit back to Management.

Deliberate semantic differences from the literal p4 mockup, and why:

- The mockup's "Play audio" / "Show notes" pills are not built: the
  current product has no Review-side audio playback wiring (Card Audio
  Export is a separate, later M18 workflow) and the existing Streamlit
  Review page already treats notes as a plain inline field rather than a
  toggle -- adding either pill here would fabricate functionality the
  product does not actually have (M17 Feature 2 prompt § "Functional
  honesty": "current product truth controls semantics").
- The mockup's frame 1 shows only a "Choose quiz type" link; a "Quick
  Quiz" action is added alongside it because DESIGN.md § 6.3 explicitly
  requires "explicit routes to Quick Quiz and Choose Quiz Type" both --
  the canonical frame is read as under-specifying one required action,
  not as forbidding it, and both already existed side-by-side in the
  Streamlit reference this migrates.
- Frame 2's per-Entry checkmarks are relabeled internally as "visited
  this session" rather than any completion claim: DESIGN.md's frozen
  learning semantics forbid Review from ever implying a Card or Entry is
  "done" outside a completed Card-scoped Quiz. The visual (a ✓ glyph,
  matching the canonical reference's own checkmark motif) is unchanged;
  only its meaning is kept honest and it is never persisted.
"""

MAIN_COLUMN_MAX_WIDTH = 640
DRAWER_WIDTH = 260


class _WrappingLabel(QLabel):
    """A word-wrapped QLabel whose ``resizeEvent`` pins its own
    ``minimumHeight`` to ``heightForWidth(width())`` (VR-STUDY-001
    corrective pass § 1). Plain ``setWordWrap(True)`` is not sufficient
    inside these nested Study layouts: a QScrollArea's own resizable-
    widget height negotiation for a ``hasHeightForWidth()`` subtree
    converges on a height a few pixels short of the wrapped text's actual
    needs (confirmed empirically -- a Qt box-layout/QScrollArea sizeHint-
    search imprecision, not a missing word-wrap flag). Explicitly pinning
    ``minimumHeight`` here is what actually stops the final line from
    being clipped, regardless of how the ambient container's own
    heightForWidth search resolves."""

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        w = self.width()
        if w > 0:
            needed = self.heightForWidth(w)
            if needed >= 0 and self.minimumHeight() != needed:
                self.setMinimumHeight(needed)


class ReviewView(QWidget):
    exit_requested = Signal()
    navigate_to_entries_requested = Signal()
    quiz_launch_requested = Signal(object)  # QuizLaunchIntent

    def __init__(self, controller: ReviewController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("review-root")
        self._controller = controller
        self._motion = None  # set via set_motion(); optional so tests can construct without one

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_session_bar())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_main_surface(), 1)

        self._drawer = _CardContentsDrawer(self)
        self._drawer.setFixedWidth(DRAWER_WIDTH)
        self._drawer.setVisible(False)
        self._drawer.close_requested.connect(self._close_drawer)
        self._drawer.entry_selected.connect(self._on_drawer_entry_selected)
        self._drawer.browse_cards_requested.connect(self._open_card_selector)
        body.addWidget(self._drawer, 0)

        root.addLayout(body, 1)

        controller.state_changed.connect(self._render)
        controller.starred_changed.connect(self._on_starred_changed)

    def set_motion(self, motion) -> None:
        """Injected by MainWindow (shared ``TransitionManager``, DESIGN.md
        § 23 / Motion Foundation) -- optional so unit tests can construct a
        ``ReviewView`` without building the whole shell."""
        self._motion = motion

    # -- construction ------------------------------------------------------

    def _build_session_bar(self) -> QWidget:
        bar = QWidget(self)
        bar.setObjectName("review-session-bar")
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(SPACING.md, SPACING.sm, SPACING.md, SPACING.sm)
        layout.setSpacing(SPACING.md)

        exit_button = QPushButton("← Exit", bar)
        exit_button.setObjectName("review-exit-button")
        exit_button.setFlat(True)
        exit_button.clicked.connect(self.exit_requested.emit)
        layout.addWidget(exit_button, 0)

        self._context_label = QLabel("", bar)
        self._context_label.setObjectName("review-context-label")
        layout.addWidget(self._context_label, 0)

        layout.addStretch(1)

        self._progress_label = QLabel("", bar)
        self._progress_label.setObjectName("review-progress-label")
        layout.addWidget(self._progress_label, 0)

        self._drawer_toggle = QPushButton("Card contents", bar)
        self._drawer_toggle.setObjectName("review-drawer-toggle")
        self._drawer_toggle.setCheckable(True)
        self._drawer_toggle.clicked.connect(self._toggle_drawer)
        layout.addWidget(self._drawer_toggle, 0)

        return bar

    def _build_main_surface(self) -> QWidget:
        # Long wrapped Meaning/Example text must receive its natural
        # vertical height rather than being squeezed toward a QLabel's
        # much-shorter minimumSizeHint whenever the column's sizeHint
        # exceeds the window's available height (VR-STUDY-001 corrective
        # pass § 1: this is what actually clipped the final line, not
        # missing setWordWrap(True)). Wrapping the centered column in a
        # QScrollArea guarantees the column is never asked to shrink below
        # its natural height -- short content still centers via the
        # stretches below, tall content scrolls instead of overlapping the
        # nav/Quiz actions that follow it.
        surface = QWidget(self)
        surface.setObjectName("review-main-surface")
        outer = QVBoxLayout(surface)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea(surface)
        scroll.setObjectName("review-main-scroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(SPACING.xl, SPACING.xl, SPACING.xl, SPACING.xl)
        content_layout.setSpacing(0)

        column = QWidget(content)
        column.setMinimumWidth(min(MAIN_COLUMN_MAX_WIDTH, 560))
        column.setMaximumWidth(MAIN_COLUMN_MAX_WIDTH)
        self._column_layout = QVBoxLayout(column)
        self._column_layout.setContentsMargins(0, 0, 0, 0)
        # Looser than any one group's *internal* spacing (e.g.
        # _build_entry_content's term/Meaning/Example) so the canvas reads
        # as deliberate groups -- prompt block, then nav, then Quiz
        # actions, then the safety caption -- rather than a uniform stack
        # of equally-spaced rows (visual-calibration corrective pass).
        self._column_layout.setSpacing(SPACING.lg)
        self._column_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        content_layout.addStretch(1)
        content_layout.addWidget(column, 0, Qt.AlignmentFlag.AlignHCenter)
        content_layout.addStretch(1)

        scroll.setWidget(content)
        outer.addWidget(scroll)

        return surface

    # -- rendering ---------------------------------------------------------

    def _render(self) -> None:
        _clear_layout(self._column_layout)

        card = self._controller.current_card()
        if card is None:
            self._context_label.setText("")
            self._progress_label.setText("")
            self._drawer_toggle.setEnabled(False)
            self._column_layout.addWidget(self._build_empty_state())
            self._drawer.render(self._controller)
            return

        self._drawer_toggle.setEnabled(True)
        self._context_label.setText(f"{card['collection_name']} · Card {card['card_number']}")
        position, total = self._controller.entry_progress()
        self._progress_label.setText(f"Review {position}/{total}" if total else "Review")

        entry = self._controller.current_entry()
        if entry is None:
            if self._controller.is_current_card_all_proficient():
                self._column_layout.addWidget(
                    _empty_state_label("All entries in this Card are marked as proficient. No regular study content needed.")
                )
            else:
                self._column_layout.addWidget(_empty_state_label("This Card has no Entries."))
            self._drawer.render(self._controller)
            return

        self._column_layout.addWidget(self._build_entry_content(entry))
        self._column_layout.addWidget(self._build_nav_row())
        self._column_layout.addWidget(self._build_quiz_actions_row())
        self._column_layout.addWidget(self._build_safety_caption())

        self._drawer.render(self._controller)

    def _build_entry_content(self, entry: dict) -> QWidget:
        block = QWidget()
        layout = QVBoxLayout(block)
        # Deliberately looser than review-field-caption's own tight 2px
        # caption-to-value pairing (_field_block) -- the term is the
        # dominant learning object and needs visible separation from the
        # supporting Meaning/Example group below it, not a uniform gap.
        layout.setSpacing(SPACING.md)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        star_button = QPushButton(block)
        star_button.setObjectName("review-current-entry-star-button")
        star_button.setProperty("learningStar", True)
        star_button.setMinimumSize(112, 40)
        self._set_star_button_state(star_button, self._controller.is_entry_starred(int(entry["id"])))
        star_button.clicked.connect(lambda: self._toggle_current_entry_star(confirm_cross_card=False))
        layout.addWidget(star_button, 0, Qt.AlignmentFlag.AlignHCenter)

        term = _WrappingLabel(str(entry.get("term") or ""), block)
        term.setObjectName("review-term-label")
        term.setAlignment(Qt.AlignmentFlag.AlignCenter)
        term.setWordWrap(True)
        layout.addWidget(term)

        meaning = str(entry.get("meaning") or "")
        if meaning:
            layout.addWidget(_field_block("Meaning", meaning, block))

        example = str(entry.get("example") or "")
        if example:
            layout.addWidget(_field_block("Example", example, block))

        return block

    @staticmethod
    def _set_star_button_state(button: QPushButton, starred: bool) -> None:
        button.setProperty("starred", starred)
        button.setText("★ Starred" if starred else "☆ Star")
        button.setAccessibleName("Unstar current Entry" if starred else "Star current Entry")
        button.style().unpolish(button)
        button.style().polish(button)

    def _on_starred_changed(self, entry_id: int, starred: bool) -> None:
        current = self._controller.current_entry()
        if current is None or int(current["id"]) != entry_id:
            return
        button = self.findChild(QPushButton, "review-current-entry-star-button")
        if button is not None:
            self._set_star_button_state(button, starred)

    def _toggle_current_entry_star(self, *, confirm_cross_card: bool) -> None:
        try:
            self._controller.toggle_current_entry_star(confirm_cross_card=confirm_cross_card)
        except CrossCardMoveConfirmationRequired:
            if _confirm_cross_card_reorganization(self):
                self._toggle_current_entry_star(confirm_cross_card=True)

    def _build_nav_row(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setSpacing(SPACING.md)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        previous_button = QPushButton("← Previous", row)
        previous_button.setObjectName("review-nav-previous")
        previous_button.setFlat(True)
        previous_button.setEnabled(self._controller.can_go_previous())
        previous_button.clicked.connect(self._controller.go_previous)
        layout.addWidget(previous_button)

        next_button = QPushButton("Next →", row)
        next_button.setObjectName("review-nav-next")
        next_button.setEnabled(self._controller.can_go_next())
        next_button.clicked.connect(self._controller.go_next)
        layout.addWidget(next_button)

        return row

    def _build_quiz_actions_row(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setSpacing(SPACING.sm)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        quick_quiz_button = QPushButton("Quick Quiz", row)
        quick_quiz_button.setObjectName("review-quick-quiz-button")
        quick_quiz_button.clicked.connect(self._start_quick_quiz)
        layout.addWidget(quick_quiz_button)

        choose_type_button = QPushButton("Choose quiz type", row)
        choose_type_button.setObjectName("review-choose-quiz-type-button")
        choose_type_button.setFlat(True)
        choose_type_button.clicked.connect(self._open_choose_quiz_type)
        layout.addWidget(choose_type_button)

        return row

    def _build_safety_caption(self) -> QWidget:
        caption = _WrappingLabel(
            "Browsing prepares this Card. Completing a Quiz records the learning event.",
            self,
        )
        caption.setObjectName("review-safety-caption")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        caption.setWordWrap(True)
        return caption

    def _build_empty_state(self) -> QWidget:
        block = QWidget()
        layout = QVBoxLayout(block)
        layout.setSpacing(SPACING.sm)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        message = _empty_state_label("No Cards are available to review yet.")
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(message)

        open_entries_button = QPushButton("Open Entries", block)
        open_entries_button.setObjectName("review-empty-open-entries")
        open_entries_button.clicked.connect(self.navigate_to_entries_requested.emit)
        layout.addWidget(open_entries_button, 0, Qt.AlignmentFlag.AlignHCenter)

        return block

    # -- drawer --------------------------------------------------------------

    def _toggle_drawer(self, checked: bool) -> None:
        self._drawer.setVisible(checked)
        if checked and self._motion is not None:
            self._motion.fade_in(self._drawer)

    def _close_drawer(self) -> None:
        self._drawer_toggle.setChecked(False)
        self._drawer.setVisible(False)

    def _on_drawer_entry_selected(self, index: int) -> None:
        self._controller.go_to_entry_index(index)

    def _open_card_selector(self) -> None:
        dialog = _StudyCardSelectorDialog(self._controller, self)
        dialog.exec()

    def _start_quick_quiz(self) -> None:
        intent = self._controller.build_quick_quiz_intent()
        if intent is not None:
            self.quiz_launch_requested.emit(intent)

    def _open_choose_quiz_type(self) -> None:
        dialog = _ChooseQuizTypeDialog(self._controller, self)
        dialog.launch_requested.connect(self.quiz_launch_requested.emit)
        dialog.exec()


class _CardContentsDrawer(QWidget):
    """Transient right drawer (DESIGN.md § 6.3): current Card's Entries
    with a session-local "visited" mark, plus factual completed-Quiz
    history. Never a permanent inspector -- ``ReviewView`` only shows it
    while the "Card contents" pill is toggled on."""

    close_requested = Signal()
    entry_selected = Signal(int)
    browse_cards_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("review-drawer")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(SPACING.md, SPACING.md, SPACING.md, SPACING.md)
        outer.setSpacing(SPACING.sm)

        header = QHBoxLayout()
        title = QLabel("Card contents", self)
        title.setObjectName("review-drawer-header")
        header.addWidget(title, 1)
        close_button = QPushButton("×", self)
        close_button.setObjectName("review-drawer-close")
        close_button.setFixedSize(20, 20)
        close_button.setFlat(True)
        close_button.clicked.connect(self.close_requested.emit)
        header.addWidget(close_button, 0)
        outer.addLayout(header)

        entries_scroll = QScrollArea(self)
        entries_scroll.setWidgetResizable(True)
        entries_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        entries_content = QWidget()
        self._entries_column = QVBoxLayout(entries_content)
        self._entries_column.setContentsMargins(0, 0, 0, 0)
        self._entries_column.setSpacing(2)
        entries_scroll.setWidget(entries_content)
        outer.addWidget(entries_scroll, 1)

        outer.addWidget(_section_divider(self))

        history_heading = QLabel("Quiz history", self)
        history_heading.setObjectName("review-drawer-history-heading")
        outer.addWidget(history_heading)
        self._history_column = QVBoxLayout()
        self._history_column.setSpacing(2)
        outer.addLayout(self._history_column)

        browse_button = QPushButton("Browse Cards…", self)
        browse_button.setObjectName("review-drawer-browse-button")
        browse_button.clicked.connect(self.browse_cards_requested.emit)
        outer.addWidget(browse_button)

    def render(self, controller: ReviewController) -> None:
        _clear_layout(self._entries_column)
        current_index = controller.entry_index()
        for index, entry in enumerate(controller.entries()):
            self._entries_column.addWidget(self._build_entry_row(controller, entry, index, current_index))

        _clear_layout(self._history_column)
        sessions = controller.history()[:5]
        if not sessions:
            self._history_column.addWidget(_empty_state_label("No completed Quiz yet for this Card."))
        else:
            for session in sessions:
                self._history_column.addWidget(self._build_history_row(session))

    def _build_entry_row(self, controller: ReviewController, entry: dict, index: int, current_index: int) -> QWidget:
        term = str(entry.get("term") or "")
        is_current = index == current_index
        visited = controller.is_entry_visited(entry["id"])
        suffix = " ✓" if visited and not is_current else ""
        button = QPushButton(f"{index + 1}. {term}{suffix}", self)
        button.setObjectName("review-drawer-entry-current" if is_current else "review-drawer-entry")
        button.setFlat(True)
        button.clicked.connect(lambda _checked=False, i=index: self.entry_selected.emit(i))
        return button

    def _build_history_row(self, session: dict) -> QWidget:
        completed_at = format_local_timestamp(session.get("completed_at"))
        correct = session.get("correct_count", 0)
        total = session.get("total_items", 0)
        label = QLabel(f"{completed_at} · {correct}/{total} correct", self)
        label.setObjectName("review-drawer-history-row")
        label.setWordWrap(True)
        return label


class _StudyCardSelectorDialog(QDialog):
    """P6 transient utility (DESIGN.md § 8): choose a different Study
    Card without turning Review into a management screen."""

    def __init__(self, controller: ReviewController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("review-card-selector-dialog")
        self.setWindowTitle("Choose a Card to review")
        self._controller = controller
        self._cards = controller.study_cards()

        layout = QVBoxLayout(self)

        collection_label = QLabel("Collection", self)
        layout.addWidget(collection_label)
        self._collection_combo = QComboBox(self)
        layout.addWidget(self._collection_combo)

        card_label = QLabel("Card", self)
        layout.addWidget(card_label)
        self._card_combo = QComboBox(self)
        layout.addWidget(self._card_combo)

        self._warning_label = QLabel("", self)
        self._warning_label.setObjectName("review-selector-warning")
        self._warning_label.setWordWrap(True)
        layout.addWidget(self._warning_label)

        buttons = QHBoxLayout()
        cancel_button = QPushButton("Cancel", self)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(cancel_button)
        buttons.addStretch(1)
        select_button = QPushButton("Select", self)
        select_button.setObjectName("review-selector-select-button")
        select_button.clicked.connect(self._select)
        buttons.addWidget(select_button)
        layout.addLayout(buttons)

        self._collections: list[tuple[int, str]] = []
        seen: set[int] = set()
        for card in self._cards:
            if card["collection_id"] not in seen:
                seen.add(card["collection_id"])
                self._collections.append((card["collection_id"], card["collection_name"]))
        for collection_id, collection_name in self._collections:
            self._collection_combo.addItem(collection_name, collection_id)

        self._collection_combo.currentIndexChanged.connect(self._populate_cards)
        if self._collections:
            self._populate_cards(0)

    def _populate_cards(self, _index: int) -> None:
        self._card_combo.clear()
        collection_id = self._collection_combo.currentData()
        for card in self._cards:
            if card["collection_id"] != collection_id:
                continue
            status_label = "never quizzed" if card["status"] == "never_quizzed" else "quizzed"
            label = f"Card {card['card_number']} · {card['entry_count']} entries · {status_label}"
            self._card_combo.addItem(label, card["card_number"])

    def _select(self) -> None:
        collection_id = self._collection_combo.currentData()
        card_number = self._card_combo.currentData()
        if collection_id is None or card_number is None:
            self._warning_label.setText("Choose a Collection and Card first.")
            return
        if self._controller.open_card(collection_id, card_number):
            self.accept()
        else:
            self._warning_label.setText("That Card is no longer available.")


class _ChooseQuizTypeDialog(QDialog):
    """P6 transient utility (DESIGN.md § 8): choose and start a real Quiz
    for the current Card -- or, for Matching, the current Collection,
    since plain Matching is whole-Collection only in the current product
    (M17 Feature 3's compatibility check; see ``ReviewController.
    build_choose_quiz_type_intent``). The optional template-aware section
    only appears when the current Card actually has entries using a
    template with defined quiz rules -- it is never shown as a fabricated
    capability."""

    launch_requested = Signal(object)  # QuizLaunchIntent

    def __init__(self, controller: ReviewController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("review-choose-quiz-type-dialog")
        self.setWindowTitle("Choose quiz type")
        self._controller = controller
        self._rule_checks: list[QCheckBox] = []

        layout = QVBoxLayout(self)

        card = controller.current_card()
        context_text = f"{card['collection_name']} · Card {card['card_number']}" if card else ""
        context_label = QLabel(context_text, self)
        layout.addWidget(context_label)

        self._type_combo = QComboBox(self)
        for quiz_type in controller.quiz_type_options():
            self._type_combo.addItem(QUIZ_TYPE_LABELS.get(quiz_type, quiz_type), quiz_type)
        default_index = self._type_combo.findData(QUICK_QUIZ_DEFAULT_TYPE)
        if default_index >= 0:
            self._type_combo.setCurrentIndex(default_index)
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        layout.addWidget(self._type_combo)

        self._matching_count_combo = QComboBox(self)
        self._matching_count_combo.setObjectName("review-matching-count-combo")
        for count in controller.matching_item_count_options():
            self._matching_count_combo.addItem(f"{count} items", count)
        self._matching_count_combo.setVisible(False)
        layout.addWidget(self._matching_count_combo)

        self._template_sources = controller.available_template_sources()
        self._template_checkbox: QCheckBox | None = None
        self._template_section: QWidget | None = None
        if self._template_sources:
            self._build_template_section(layout)

        self._warning_label = QLabel("", self)
        self._warning_label.setObjectName("review-selector-warning")
        self._warning_label.setWordWrap(True)
        layout.addWidget(self._warning_label)

        buttons = QHBoxLayout()
        cancel_button = QPushButton("Cancel", self)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(cancel_button)
        buttons.addStretch(1)
        start_button = QPushButton("Start Quiz", self)
        start_button.setObjectName("review-choose-quiz-type-start-button")
        start_button.clicked.connect(self._start)
        buttons.addWidget(start_button)
        layout.addLayout(buttons)

        self._on_type_changed()

    def _build_template_section(self, layout: QVBoxLayout) -> None:
        self._template_checkbox = QCheckBox("Use a template-aware quiz instead", self)
        self._template_checkbox.toggled.connect(self._on_template_toggled)
        layout.addWidget(self._template_checkbox)

        self._template_section = QWidget(self)
        template_layout = QVBoxLayout(self._template_section)
        template_layout.setContentsMargins(0, 0, 0, 0)

        self._template_combo = QComboBox(self._template_section)
        for source in self._template_sources:
            self._template_combo.addItem(f"{source['template_name']} ({source['entry_count']} entries)", source)
        self._template_combo.currentIndexChanged.connect(self._on_template_source_changed)
        template_layout.addWidget(self._template_combo)

        self._template_mode_combo = QComboBox(self._template_section)
        self._template_mode_combo.addItem("Self-graded", TEMPLATE_FIELD_SELF_GRADED)
        self._template_mode_combo.addItem("Multiple choice", TEMPLATE_FIELD_MCQ)
        self._template_mode_combo.addItem("Matching", TEMPLATE_FIELD_MATCHING)
        template_layout.addWidget(self._template_mode_combo)

        self._rules_container = QVBoxLayout()
        template_layout.addLayout(self._rules_container)

        self._template_section.setVisible(False)
        layout.addWidget(self._template_section)

        self._on_template_source_changed(0)

    def _on_type_changed(self) -> None:
        self._matching_count_combo.setVisible(self._type_combo.currentData() == "matching")

    def _on_template_toggled(self, checked: bool) -> None:
        self._type_combo.setEnabled(not checked)
        self._matching_count_combo.setEnabled(not checked)
        if self._template_section is not None:
            self._template_section.setVisible(checked)

    def _on_template_source_changed(self, _index: int) -> None:
        for checkbox in self._rule_checks:
            checkbox.setParent(None)
        self._rule_checks = []
        source = self._template_combo.currentData()
        if source is None:
            return
        for rule in self._controller.template_rules(source["template_type"]):
            checkbox = QCheckBox(rule["label"], self._template_section)
            checkbox.setProperty("rule_id", rule["id"])
            self._rules_container.addWidget(checkbox)
            self._rule_checks.append(checkbox)

    def _using_template(self) -> bool:
        return bool(self._template_sources) and self._template_checkbox is not None and self._template_checkbox.isChecked()

    def _start(self) -> None:
        self._warning_label.setText("")
        if self._using_template():
            source = self._template_combo.currentData()
            rule_ids = [checkbox.property("rule_id") for checkbox in self._rule_checks if checkbox.isChecked()]
            if source is None or not rule_ids:
                self._warning_label.setText("Choose a template and at least one rule.")
                return
            intent = self._controller.build_template_quiz_intent(
                source["template_id"],
                source["template_type"],
                rule_ids,
                self._template_mode_combo.currentData(),
            )
        else:
            quiz_type = self._type_combo.currentData()
            matching_count = self._matching_count_combo.currentData() if quiz_type == "matching" else None
            if quiz_type == "matching" and matching_count is None:
                self._warning_label.setText("This Collection does not have enough entries for Matching.")
                return
            intent = self._controller.build_choose_quiz_type_intent(quiz_type, matching_item_count=matching_count)

        if intent is None:
            self._warning_label.setText("No Card is currently selected.")
            return
        self.launch_requested.emit(intent)
        self.accept()


def _field_block(caption_text: str, value_text: str, parent: QWidget) -> QWidget:
    block = QWidget(parent)
    layout = QVBoxLayout(block)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

    caption = QLabel(caption_text, block)
    caption.setObjectName("review-field-caption")
    caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(caption)

    value = _WrappingLabel(value_text, block)
    value.setObjectName("review-field-text")
    value.setAlignment(Qt.AlignmentFlag.AlignCenter)
    value.setWordWrap(True)
    layout.addWidget(value)

    return block


def _empty_state_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("review-empty-state")
    return label


def _section_divider(parent: QWidget) -> QWidget:
    divider = QWidget(parent)
    divider.setObjectName("review-drawer-divider")
    divider.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    divider.setFixedHeight(1)
    return divider


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()


def _confirm_cross_card_reorganization(parent: QWidget) -> bool:
    result = QMessageBox.question(
        parent,
        "Confirm Card Reorganization",
        CROSS_CARD_CONFIRMATION_MESSAGE,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    return result == QMessageBox.StandardButton.Yes
