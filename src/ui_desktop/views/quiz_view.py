from __future__ import annotations

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.collections import CROSS_CARD_CONFIRMATION_MESSAGE, CrossCardMoveConfirmationRequired
from src.ui_desktop.controllers.quiz_controller import MATCHING_FAMILY, MCQ_FAMILY, QuizController
from src.ui_desktop.state.handoff import QUIZ_TYPE_LABELS
from src.ui_desktop.state.preferences import (
    DEFAULT_QUIZ_PRESENTATION,
    QUIZ_PRESENTATION_FLIP_CARD,
    QUIZ_PRESENTATION_IMMERSIVE,
    parse_quiz_presentation,
)
from src.ui_desktop.theming.metrics import SPACING

"""
Quiz -- Immersive Focus (DESIGN.md § 6.3 `VR-STUDY-001`, parent pattern P3;
DESIGN.md § 7.2 coverage matrix: "Quiz Session -- primary/self-graded
state" and "Quiz Completion / Summary" are class A under the same
authority as Review). M17 Feature 3: migrates the existing Quiz engine
(``src/quiz.py``, ``src/template_quiz.py``) into this native surface --
``src/ui_streamlit/quiz_page.py`` is a behavioral reference only.

Design → Implementation trace:

  Study Mode shell/chrome  -> reuses Review's pattern exactly: MainWindow
                               hides NavigationRail/generic toolbar while
                               this view supplies the one session bar.
  session bar              -> _build_session_bar(): Exit + Collection ·
                               Card · quiz-type context + progress
                               (i/N, or "Complete").
  self-graded task         -> term dominant, a real answer draft field,
                               "Show Answer" reveal gate, then
                               Correct/Wrong self-grading -- the exact
                               Streamlit flow (`quiz_show_answer`), not a
                               redesign.
  MCQ task                 -> term + one exclusive option group + Submit;
                               after submit, options lock and feedback +
                               Next Question replace them (never both
                               interactive at once, matching Streamlit's
                               state-gated MCQ render).
  matching task             -> DESIGN.md § 7.2 "wider task canvas allowed"
                               -- not bounded to the narrow reading column
                               Review/self-graded/MCQ use; every pair is
                               visible at once (Streamlit submits the whole
                               set together, not per-item).
  progress                  -> session bar i/N; matching counts selections
                               made instead of a linear index, since every
                               item is already visible.
  answer feedback           -> quiz-correct/quiz-wrong semantic tokens
                               (DESIGN.md § 11.3), not ad hoc colors.
  recovery                  -> a blocked-session notice inside this P3
                               surface (DESIGN.md § 7.2 "Quiz
                               recovery/resume: P6 recovery -> P3") when
                               ``QuizController.start()`` finds a foreign
                               active session; offers only Cancel, exactly
                               like Streamlit -- no fake auto-resume.
  cancel/restart            -> _ExitQuizConfirmDialog (P6): leaving an
                               active session is a real choice, not a
                               silent abandon; already-logged answers stay
                               recorded either way (frozen semantics).
  completion                -> compact Total/Correct/Wrong + a factual
                               mistakes list + next actions, staying
                               inside Immersive Focus (DESIGN.md § 6.3:
                               never a KPI dashboard). Review Mistakes is
                               omitted (not disabled) when there are zero
                               mistakes.
  mistake review             -> VR-STUDY-001 corrective pass § 3: a
                               read-only in-place state reached from
                               completion's Review Mistakes action --
                               position, original prompt/context, the
                               submitted vs. expected answer, and
                               Previous/Next -- entirely inside
                               QuizController/QuizView (no MainWindow
                               involvement, no navigation away, no
                               mutation). "Back to summary" returns to the
                               completion state without clearing
                               ``completed_session``.
  exit/return                -> Return to Today exits Study Mode entirely;
                               Next Card returns to Review (Study Mode
                               stays active) rather than auto-starting
                               another Quiz -- MainWindow orchestrates
                               through AppState like every other
                               transition.

Frozen learning semantics (unchanged from Review, now load-bearing here):
starting Quiz, answering some items, or cancelling are never themselves a
completion event -- only ``QuizController._complete()`` (a fully-answered
session reaching ``mark_quiz_session_completed``) is. A whole-
Collection/random Quiz remains Entry-level evidence only; nothing here
fabricates a Card completion for one.

M17 Feature 3B (`VR-STUDY-002`, `Review - Quiz.pdf` p5 Variant D -- Quiz
presentation choice, Quiz-only): ``set_presentation()`` is called once by
``MainWindow`` per launch, before ``QuizController.start()``, resolving the
saved Settings preference into this session's presentation -- never a
second in-session switcher (prompt § 7). Self-graded/MCQ (including
template-linear types, which already map to those families) render inside
a bordered Flip Card + restrained orientation filmstrip when
``flip_card_filmstrip`` is selected; Matching always falls back to the
existing wider Immersive Matching presentation regardless of the saved
preference (a genuinely simultaneous whole-set interaction, not a linear
one -- prompt § 13), without ever altering the saved preference itself.
Both presentations share the exact same ``QuizController`` session/answer/
completion truth (``_fill_self_graded_content``/``_fill_mcq_content`` are
the one implementation each family's content uses either way), and
completion / mistake review stay the single shared Immersive-styled
surfaces for both presentations (prompt § 14/§ 15) -- VR-STUDY-002 governs
only the active self-graded/MCQ task surface. This view controls only
itself: Review, Today, Entries, and Management Mode are unaffected and
carry no Flip Card control of their own (prompt § 2).
"""

MAIN_COLUMN_MAX_WIDTH = 640
MATCHING_COLUMN_MAX_WIDTH = 880


class _WrappingLabel(QLabel):
    """A word-wrapped QLabel whose ``resizeEvent`` pins its own
    ``minimumHeight`` to ``heightForWidth(width())`` (VR-STUDY-001
    corrective pass § 1) -- same fix as Review's identical class, applied
    here so long term/answer/expected text is never clipped inside this
    Study surface either. See ``review_view.py``'s ``_WrappingLabel`` for
    the full root-cause note (a QScrollArea/box-layout heightForWidth
    negotiation imprecision, not a missing word-wrap flag)."""

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        needed = self.heightForWidth(self.width())
        if needed >= 0 and self.minimumHeight() != needed:
            self.setMinimumHeight(needed)


class _MatchingComboBox(QComboBox):
    """Wheel events over a closed Matching combo must scroll the
    surrounding Matching list, never silently change the selected answer
    (VR-STUDY-001 corrective pass § 2A). Ignoring (never accepting) the
    event is the native Qt way to hand it to the enclosing QScrollArea
    instead -- no second interaction model, and the open dropdown popup
    (a separate widget) still scrolls/selects normally on deliberate
    click-to-open interaction."""

    def wheelEvent(self, event) -> None:  # noqa: N802 (Qt override)
        event.ignore()


class QuizView(QWidget):
    exit_requested = Signal()
    return_to_today_requested = Signal()
    next_card_requested = Signal()

    def __init__(self, controller: QuizController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("quiz-root")
        self._controller = controller

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_session_bar())

        # Same robustness principle as Review's main surface (VR-STUDY-001
        # corrective pass § 1): the centered column must never be squeezed
        # below its natural height. A QScrollArea keeps short tasks
        # centered via the stretches below while tall ones (long wrapped
        # term/answer/expected text) scroll instead of clipping or
        # overlapping the grading/submit controls that follow.
        self._surface = QWidget(self)
        self._surface.setObjectName("quiz-main-surface")
        outer = QVBoxLayout(self._surface)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = QScrollArea(self._surface)
        self._scroll.setObjectName("quiz-main-scroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(SPACING.xl, SPACING.xl, SPACING.xl, SPACING.xl)
        content_layout.setSpacing(0)

        self._column = QWidget(content)
        self._column_layout = QVBoxLayout(self._column)
        self._column_layout.setSpacing(SPACING.lg)
        self._column_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        content_layout.addStretch(1)
        content_layout.addWidget(self._column, 0, Qt.AlignmentFlag.AlignHCenter)
        content_layout.addStretch(1)

        self._scroll.setWidget(content)
        outer.addWidget(self._scroll)

        root.addWidget(self._surface, 1)

        self._matching_submit_button: QPushButton | None = None
        self._presentation = DEFAULT_QUIZ_PRESENTATION
        controller.state_changed.connect(self._render)
        controller.matching_selection_changed.connect(self._on_matching_selection_changed)
        controller.starred_changed.connect(self._on_starred_changed)

    def set_presentation(self, quiz_presentation: str) -> None:
        """Resolve this Quiz session's presentation once, at launch time
        (module docstring / M17 Feature 3B prompt § 7) -- ``MainWindow``
        calls this before ``QuizController.start()`` so the very first
        render already uses the saved choice."""
        self._presentation = parse_quiz_presentation(quiz_presentation)

    def _effective_presentation(self, family: str | None) -> str:
        # Matching compatibility fallback (M17 Feature 3B prompt § 13):
        # never Flip Card + Filmstrip, regardless of the saved preference,
        # and this never mutates ``self._presentation`` itself.
        if family == MATCHING_FAMILY:
            return QUIZ_PRESENTATION_IMMERSIVE
        return self._presentation

    # -- construction ------------------------------------------------------

    def _build_session_bar(self) -> QWidget:
        bar = QWidget(self)
        bar.setObjectName("quiz-session-bar")
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(SPACING.md, SPACING.sm, SPACING.md, SPACING.sm)
        layout.setSpacing(SPACING.md)

        exit_button = QPushButton("← Exit", bar)
        exit_button.setObjectName("quiz-exit-button")
        exit_button.setFlat(True)
        exit_button.clicked.connect(self._on_exit_clicked)
        layout.addWidget(exit_button, 0)

        self._context_label = QLabel("", bar)
        self._context_label.setObjectName("quiz-context-label")
        layout.addWidget(self._context_label, 0)

        layout.addStretch(1)

        self._progress_label = QLabel("", bar)
        self._progress_label.setObjectName("quiz-progress-label")
        layout.addWidget(self._progress_label, 0)

        return bar

    # -- rendering ---------------------------------------------------------

    def _render(self) -> None:
        _clear_layout(self._column_layout)
        self._column.setMaximumWidth(16777215)
        # Only _build_matching_task() below re-populates this -- every other
        # branch renders a widget tree with no live Matching submit button,
        # so a stale reference must never survive into a later selection-
        # only refresh (_on_matching_selection_changed).
        self._matching_submit_button = None

        controller = self._controller

        if controller.blocked_session is not None:
            self._render_context(controller.blocked_session, complete=False)
            self._column.setMaximumWidth(MAIN_COLUMN_MAX_WIDTH)
            self._column_layout.addWidget(self._build_blocked_state())
            return

        if controller.start_error is not None:
            self._context_label.setText("")
            self._progress_label.setText("")
            self._column.setMaximumWidth(MAIN_COLUMN_MAX_WIDTH)
            self._column_layout.addWidget(_message_label(controller.start_error, "quiz-error-message"))
            return

        if controller.completed_session is not None:
            self._render_context(controller.completed_session, complete=True)
            self._column.setMaximumWidth(MAIN_COLUMN_MAX_WIDTH)
            if controller.reviewing_mistakes:
                self._column_layout.addWidget(self._build_mistake_review_state())
            else:
                self._column_layout.addWidget(self._build_completion_state())
            return

        if controller.intent is None:
            self._context_label.setText("")
            self._progress_label.setText("")
            self._column.setMaximumWidth(MAIN_COLUMN_MAX_WIDTH)
            self._column_layout.addWidget(_message_label("No Quiz is active.", "quiz-empty-state"))
            return

        self._render_context(None, complete=False)
        family = controller.quiz_family()
        presentation = self._effective_presentation(family)
        if family == MATCHING_FAMILY:
            self._column.setMaximumWidth(MATCHING_COLUMN_MAX_WIDTH)
            self._column_layout.addWidget(self._build_matching_task())
        elif presentation == QUIZ_PRESENTATION_FLIP_CARD:
            self._column.setMaximumWidth(MAIN_COLUMN_MAX_WIDTH)
            self._column_layout.addWidget(self._build_flip_card_task(family))
        elif family == MCQ_FAMILY:
            self._column.setMaximumWidth(MAIN_COLUMN_MAX_WIDTH)
            self._column_layout.addWidget(self._build_mcq_task())
        else:
            self._column.setMaximumWidth(MAIN_COLUMN_MAX_WIDTH)
            self._column_layout.addWidget(self._build_self_graded_task())

    def _render_context(self, session_like: dict | None, *, complete: bool) -> None:
        controller = self._controller
        intent = controller.intent
        if complete and session_like is not None:
            collection_name = intent.collection_name if intent else ""
            card_number = session_like.get("card_number") or 0
            card_label = f"Card {card_number}" if card_number else "Whole Collection"
            self._context_label.setText(f"{collection_name} · {card_label}")
            self._progress_label.setText("Complete")
            return
        if session_like is not None:
            # Blocked (foreign active) session: only the DB row's own facts.
            card_number = session_like.get("card_number") or 0
            card_label = f"Card {card_number}" if card_number else "Whole Collection"
            type_label = QUIZ_TYPE_LABELS.get(session_like.get("quiz_type"), session_like.get("quiz_type") or "")
            self._context_label.setText(f"Unfinished · {card_label} · {type_label}")
            self._progress_label.setText("")
            return
        if intent is None:
            return
        card_label = f"Card {intent.card_number}" if intent.card_number else "Whole Collection"
        type_label = QUIZ_TYPE_LABELS.get(intent.quiz_type, intent.quiz_type)
        self._context_label.setText(f"{intent.collection_name} · {card_label} · {type_label}")
        position, total = controller.progress()
        self._progress_label.setText(f"Quiz {position}/{total}" if total else "Quiz")

    def _on_matching_selection_changed(self) -> None:
        """A Matching answer selection is transient item state, not a
        reason to rebuild the whole task surface (VR-STUDY-001 corrective
        pass § 2B) -- rebuilding on every selection is exactly what reset
        the user's scroll position and made completing lower rows
        frustrating. Only the session-bar progress count and the Submit
        Matching button's enabled state actually change; every QComboBox
        keeps its own widget-owned value untouched, so already-selected
        answers stay visible and stable without any extra bookkeeping."""
        if self._controller.quiz_family() != MATCHING_FAMILY:
            return
        self._render_context(None, complete=False)
        if self._matching_submit_button is not None:
            self._matching_submit_button.setEnabled(self._controller.can_submit_matching())

    # -- blocked / recovery --------------------------------------------------

    def _build_blocked_state(self) -> QWidget:
        block = QWidget()
        layout = QVBoxLayout(block)
        layout.setSpacing(SPACING.sm)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        message = _message_label(
            "An unfinished Quiz session exists. Automatic recovery is limited -- "
            "already-answered questions stay recorded, but this session cannot be "
            "resumed here. Cancel it to start a new Quiz.",
            "quiz-blocked-message",
        )
        layout.addWidget(message)

        cancel_button = QPushButton("Cancel unfinished Quiz", block)
        cancel_button.setObjectName("quiz-blocked-cancel-button")
        cancel_button.clicked.connect(self._controller.cancel_blocked_and_retry)
        layout.addWidget(cancel_button, 0, Qt.AlignmentFlag.AlignHCenter)

        return block

    # -- self-graded ---------------------------------------------------------

    def _build_self_graded_task(self) -> QWidget:
        block = QWidget()
        layout = QVBoxLayout(block)
        layout.setSpacing(SPACING.md)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._fill_self_graded_content(layout, block)
        return block

    def _fill_self_graded_content(self, layout: QVBoxLayout, parent: QWidget) -> bool:
        """Builds the self-graded prompt/answer/grade content into
        ``layout`` (a plain open column for Immersive Focus, or a bordered
        Flip Card's own layout for VR-STUDY-002 -- M17 Feature 3B module
        docstring). Returns whether an item existed to render."""
        controller = self._controller
        item = controller.current_item()
        if item is None:
            layout.addWidget(_message_label("This Quiz has no items.", "quiz-empty-state"))
            return False

        layout.addWidget(
            self._build_star_button(
                int(item["entry_id"]),
                parent,
                object_name="quiz-current-entry-star-button",
            ),
            0,
            Qt.AlignmentFlag.AlignHCenter,
        )

        term = _WrappingLabel(str(item.get("prompt") or ""), parent)
        term.setObjectName("quiz-term-label")
        term.setAlignment(Qt.AlignmentFlag.AlignCenter)
        term.setWordWrap(True)
        layout.addWidget(term)
        # Extra separation on top of the uniform inter-item spacing above --
        # the prompt is its own group; the answer surface below it is a
        # distinct group (visual-calibration corrective pass § 15).
        layout.addSpacing(SPACING.lg)

        answer_input = QLineEdit(parent)
        answer_input.setObjectName("quiz-answer-input")
        answer_input.setPlaceholderText("Your answer")
        answer_input.setText(controller.answer_draft)
        answer_input.setEnabled(not controller.show_answer)
        answer_input.textChanged.connect(controller.set_answer_draft)
        layout.addWidget(answer_input)

        if not controller.show_answer:
            show_button = QPushButton("Show Answer", parent)
            show_button.setObjectName("quiz-show-answer-button")
            show_button.clicked.connect(controller.reveal_answer)
            layout.addWidget(show_button, 0, Qt.AlignmentFlag.AlignHCenter)
        else:
            layout.addWidget(_field_block("Your answer", controller.answer_draft or "(blank)", parent))
            layout.addWidget(_field_block("Expected", str(item.get("expected_answer") or ""), parent))

            grade_row = QWidget(parent)
            grade_layout = QHBoxLayout(grade_row)
            grade_layout.setSpacing(SPACING.sm)
            grade_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

            wrong_button = QPushButton("Wrong", grade_row)
            wrong_button.setObjectName("quiz-grade-wrong-button")
            wrong_button.clicked.connect(lambda: controller.submit_self_graded(False))
            grade_layout.addWidget(wrong_button)

            correct_button = QPushButton("Correct", grade_row)
            correct_button.setObjectName("quiz-grade-correct-button")
            correct_button.clicked.connect(lambda: controller.submit_self_graded(True))
            grade_layout.addWidget(correct_button)

            layout.addWidget(grade_row)

        return True

    # -- MCQ -------------------------------------------------------------

    def _build_mcq_task(self) -> QWidget:
        block = QWidget()
        layout = QVBoxLayout(block)
        layout.setSpacing(SPACING.md)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._fill_mcq_content(layout, block)
        return block

    def _fill_mcq_content(self, layout: QVBoxLayout, parent: QWidget) -> bool:
        """MCQ counterpart to ``_fill_self_graded_content`` -- see that
        method's docstring. Returns whether an item existed to render."""
        controller = self._controller
        item = controller.current_item()
        if item is None:
            layout.addWidget(_message_label("This Quiz has no items.", "quiz-empty-state"))
            return False

        layout.addWidget(
            self._build_star_button(
                int(item["entry_id"]),
                parent,
                object_name="quiz-current-entry-star-button",
            ),
            0,
            Qt.AlignmentFlag.AlignHCenter,
        )

        term = _WrappingLabel(str(item.get("prompt") or ""), parent)
        term.setObjectName("quiz-term-label")
        term.setAlignment(Qt.AlignmentFlag.AlignCenter)
        term.setWordWrap(True)
        layout.addWidget(term)
        layout.addSpacing(SPACING.lg)

        feedback = controller.feedback
        if feedback is None:
            group = QButtonGroup(parent)
            self._mcq_group = group
            for option in item.get("options") or []:
                button = QRadioButton(str(option), parent)
                button.setObjectName("quiz-mcq-option")
                group.addButton(button)
                layout.addWidget(button)

            submit_button = QPushButton("Submit", parent)
            submit_button.setObjectName("quiz-mcq-submit-button")
            submit_button.clicked.connect(lambda: self._submit_mcq(group))
            layout.addWidget(submit_button, 0, Qt.AlignmentFlag.AlignHCenter)
        else:
            is_correct = bool(feedback.get("is_correct"))
            feedback_label = QLabel("Correct" if is_correct else "Wrong", parent)
            feedback_label.setObjectName("quiz-feedback-correct" if is_correct else "quiz-feedback-wrong")
            feedback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(feedback_label)

            layout.addWidget(_field_block("Your answer", str(feedback.get("selected") or ""), parent))
            layout.addWidget(_field_block("Expected", str(feedback.get("expected_answer") or ""), parent))

            next_button = QPushButton("Next Question", parent)
            next_button.setObjectName("quiz-mcq-next-button")
            next_button.clicked.connect(controller.advance_after_mcq)
            layout.addWidget(next_button, 0, Qt.AlignmentFlag.AlignHCenter)

        return True

    def _submit_mcq(self, group: QButtonGroup) -> None:
        selected = group.checkedButton()
        if selected is None:
            return
        self._controller.submit_mcq(selected.text())

    # -- Flip Card + Filmstrip (VR-STUDY-002, M17 Feature 3B) ---------------

    def _build_flip_card_task(self, family: str) -> QWidget:
        """Same ``QuizController`` state as Immersive Focus, presented as a
        strong centered card + a restrained orientation filmstrip below it
        (`Review - Quiz.pdf` p5 Variant D), instead of the wide open
        Immersive column. Matching never reaches here -- ``_render()``'s
        compatibility fallback keeps it on the existing wider Immersive
        Matching presentation."""
        controller = self._controller
        outer = QWidget()
        outer_layout = QVBoxLayout(outer)
        outer_layout.setSpacing(SPACING.lg)
        outer_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        if controller.current_item() is None:
            outer_layout.addWidget(_message_label("This Quiz has no items.", "quiz-empty-state"))
            return outer

        # Front = prompt/answer-entry (or unanswered MCQ options); revealed
        # = Your answer/Expected + grading (or MCQ feedback) -- the same
        # front/back distinction the canonical reference uses for Review's
        # own flip card (prompt § 10/§ 18).
        revealed = controller.feedback is not None if family == MCQ_FAMILY else controller.show_answer

        card = QWidget(outer)
        card.setObjectName("quiz-flip-card-revealed" if revealed else "quiz-flip-card-front")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(SPACING.xl, SPACING.xl, SPACING.xl, SPACING.xl)
        card_layout.setSpacing(SPACING.md)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        if family == MCQ_FAMILY:
            self._fill_mcq_content(card_layout, card)
        else:
            self._fill_self_graded_content(card_layout, card)

        outer_layout.addWidget(card, 0, Qt.AlignmentFlag.AlignHCenter)
        outer_layout.addWidget(self._build_filmstrip(), 0, Qt.AlignmentFlag.AlignHCenter)

        return outer

    def _build_filmstrip(self) -> QWidget:
        """Orientation/progress only (prompt § 8B/§ 9): total item count,
        current item, already-answered items, remaining items. Tiles are
        plain ``QLabel``s, not buttons -- deliberately non-interactive
        (never a jump-to-item control), so the visual affordance never
        promises navigation the existing linear Quiz engine cannot safely
        offer without session/scoring changes this checkpoint does not
        make."""
        controller = self._controller
        strip = QWidget()
        strip.setObjectName("quiz-filmstrip")
        strip.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(strip)
        layout.setContentsMargins(SPACING.sm, SPACING.sm, SPACING.sm, SPACING.sm)
        layout.setSpacing(SPACING.xs)

        for index in range(len(controller.items)):
            layout.addWidget(self._build_filmstrip_tile(index))

        return strip

    def _build_filmstrip_tile(self, index: int) -> QLabel:
        controller = self._controller
        result = controller.item_status(index)
        if result is True:
            text = f"{index + 1} ✓"
            object_name = "quiz-filmstrip-tile-correct"
        elif result is False:
            text = f"{index + 1} ×"
            object_name = "quiz-filmstrip-tile-wrong"
        elif index == controller.current_index:
            text = str(index + 1)
            object_name = "quiz-filmstrip-tile-current"
        else:
            text = str(index + 1)
            object_name = "quiz-filmstrip-tile-future"

        tile = QLabel(text)
        tile.setObjectName(object_name)
        tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return tile

    # -- matching ------------------------------------------------------------

    def _build_matching_task(self) -> QWidget:
        controller = self._controller
        items = controller.matching_items()
        choices = controller.matching_choices()
        block = QWidget()
        layout = QVBoxLayout(block)
        layout.setSpacing(SPACING.sm)

        if not items:
            layout.addWidget(_message_label("This Quiz has no items.", "quiz-empty-state"))
            return block

        heading = QLabel("Match each term with its meaning", block)
        heading.setObjectName("quiz-matching-heading")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(heading)

        rows_scroll = QScrollArea(block)
        rows_scroll.setWidgetResizable(True)
        rows_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        rows_content = QWidget()
        rows_layout = QVBoxLayout(rows_content)
        rows_layout.setSpacing(SPACING.xs)

        for item in items:
            rows_layout.addWidget(self._build_matching_row(item, choices))
        rows_scroll.setWidget(rows_content)
        rows_scroll.setMaximumHeight(360)
        layout.addWidget(rows_scroll)

        submit_button = QPushButton("Submit Matching", block)
        submit_button.setObjectName("quiz-matching-submit-button")
        submit_button.setEnabled(controller.can_submit_matching())
        submit_button.clicked.connect(controller.submit_matching)
        layout.addWidget(submit_button, 0, Qt.AlignmentFlag.AlignHCenter)
        self._matching_submit_button = submit_button

        return block

    def _build_matching_row(self, item: dict, choices: list[str]) -> QWidget:
        controller = self._controller
        row = QWidget()
        row.setObjectName("quiz-matching-row")
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(row)
        layout.setSpacing(SPACING.sm)

        layout.addWidget(
            self._build_star_button(
                int(item["entry_id"]),
                row,
                object_name=f"quiz-matching-star-button-{int(item['entry_id'])}",
            ),
            0,
        )

        term_label = QLabel(str(item.get("term") or ""), row)
        term_label.setObjectName("quiz-matching-term-label")
        layout.addWidget(term_label, 1)

        combo = _MatchingComboBox(row)
        combo.setObjectName("quiz-matching-combo")
        combo.addItem("", "")
        for choice in choices:
            combo.addItem(choice, choice)
        current = controller.matching_selection_for(item)
        index = combo.findData(current)
        if index >= 0:
            combo.setCurrentIndex(index)
        combo.currentIndexChanged.connect(lambda _i, i=item, c=combo: controller.set_matching_selection(i, c.currentData() or ""))
        layout.addWidget(combo, 1)

        return row

    def _build_star_button(self, entry_id: int, parent: QWidget, *, object_name: str) -> QPushButton:
        button = QPushButton(parent)
        button.setObjectName(object_name)
        button.setProperty("entryId", entry_id)
        button.setProperty("learningStar", True)
        button.setMinimumSize(112, 40)
        self._set_star_button_state(button, self._controller.is_entry_starred(entry_id))
        button.clicked.connect(lambda: self._toggle_entry_star(entry_id, confirm_cross_card=False))
        return button

    @staticmethod
    def _set_star_button_state(button: QPushButton, starred: bool) -> None:
        button.setProperty("starred", starred)
        button.setText("★ Starred" if starred else "☆ Star")
        button.setAccessibleName("Unstar Entry" if starred else "Star Entry")
        button.style().unpolish(button)
        button.style().polish(button)

    def _on_starred_changed(self, entry_id: int, starred: bool) -> None:
        for button in self.findChildren(QPushButton):
            if button.property("entryId") == entry_id:
                self._set_star_button_state(button, starred)

    def _toggle_entry_star(self, entry_id: int, *, confirm_cross_card: bool) -> None:
        try:
            self._controller.toggle_entry_star(entry_id, confirm_cross_card=confirm_cross_card)
        except CrossCardMoveConfirmationRequired:
            if _confirm_cross_card_reorganization(self):
                self._toggle_entry_star(entry_id, confirm_cross_card=True)

    # -- completion ------------------------------------------------------

    def _build_completion_state(self) -> QWidget:
        controller = self._controller
        session = controller.completed_session or {}
        block = QWidget()
        layout = QVBoxLayout(block)
        layout.setSpacing(SPACING.md)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        card_number = session.get("card_number") or 0
        title_text = f"Card {card_number} complete" if card_number else "Quiz complete"
        title = QLabel(title_text, block)
        title.setObjectName("quiz-completion-title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        stats_row = QWidget(block)
        stats_layout = QHBoxLayout(stats_row)
        stats_layout.setSpacing(SPACING.lg)
        stats_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        stats_layout.addWidget(_stat_block(str(session.get("total_items") or 0), "Total", block))
        stats_layout.addWidget(_stat_block(str(session.get("correct_count") or 0), "Correct", block))
        stats_layout.addWidget(_stat_block(str(session.get("wrong_count") or 0), "Wrong", block))
        layout.addWidget(stats_row)

        layout.addWidget(_section_divider(block))

        mistakes_heading = QLabel("Mistakes from this quiz", block)
        mistakes_heading.setObjectName("quiz-completion-mistakes-heading")
        mistakes_heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(mistakes_heading)

        mistake_terms = [str(row.get("term") or "") for row in controller.mistakes]
        mistakes_text = ", ".join(term for term in mistake_terms if term) or "None"
        mistakes_label = _WrappingLabel(mistakes_text, block)
        mistakes_label.setObjectName("quiz-completion-mistakes-list")
        mistakes_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mistakes_label.setWordWrap(True)
        layout.addWidget(mistakes_label)

        if controller.completion_schedule() is not None:
            layout.addWidget(_section_divider(block))
            schedule_heading = QLabel("Next Review", block)
            schedule_heading.setObjectName("quiz-completion-schedule-heading")
            schedule_heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(schedule_heading)

            schedule = controller.completion_schedule()
            schedule_status = QLabel(
                str(schedule.get("next_due_at") or "Unscheduled"),
                block,
            )
            schedule_status.setObjectName("quiz-completion-schedule-status")
            schedule_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(schedule_status)

            preset_row = QWidget(block)
            preset_layout = QHBoxLayout(preset_row)
            preset_layout.setSpacing(SPACING.sm)
            preset_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            for label, days, suffix in (
                ("Again Today", 0, "today"),
                ("+1 day", 1, "1-day"),
                ("+2 days", 2, "2-days"),
                ("+7 days", 7, "7-days"),
            ):
                button = QPushButton(label, preset_row)
                button.setObjectName(f"quiz-completion-schedule-{suffix}")
                button.clicked.connect(
                    lambda _checked=False, days=days: controller.schedule_next_review_after_days(days)
                )
                preset_layout.addWidget(button)
            layout.addWidget(preset_row)

            custom_row = QWidget(block)
            custom_layout = QHBoxLayout(custom_row)
            custom_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            custom_date = QDateEdit(custom_row)
            custom_date.setObjectName("quiz-completion-schedule-custom-date")
            custom_date.setCalendarPopup(True)
            custom_date.setDisplayFormat("yyyy-MM-dd")
            custom_date.setMinimumDate(QDate.currentDate())
            custom_date.setDate(QDate.currentDate().addDays(1))
            custom_layout.addWidget(custom_date)
            custom_button = QPushButton("Set custom date", custom_row)
            custom_button.setObjectName("quiz-completion-schedule-custom-button")
            custom_button.clicked.connect(
                lambda: controller.schedule_next_review(
                    custom_date.date().toString("yyyy-MM-dd")
                )
            )
            custom_layout.addWidget(custom_button)
            layout.addWidget(custom_row)

        actions_row = QWidget(block)
        actions_layout = QHBoxLayout(actions_row)
        actions_layout.setSpacing(SPACING.sm)
        actions_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        return_button = QPushButton("Return to Today", actions_row)
        return_button.setObjectName("quiz-completion-return-today-button")
        return_button.clicked.connect(self._on_return_to_today)
        actions_layout.addWidget(return_button)

        next_card_button = QPushButton("Next Card", actions_row)
        next_card_button.setObjectName("quiz-completion-next-card-button")
        next_card_button.clicked.connect(self._on_next_card)
        actions_layout.addWidget(next_card_button)

        # Honest omission, not a disabled dead control (VR-STUDY-001
        # corrective pass § 3): with zero mistakes there is nothing to
        # review, so the action simply is not offered.
        if controller.mistakes:
            review_mistakes_button = QPushButton("Review Mistakes", actions_row)
            review_mistakes_button.setObjectName("quiz-completion-review-mistakes-button")
            review_mistakes_button.clicked.connect(self._on_review_mistakes)
            actions_layout.addWidget(review_mistakes_button)

        layout.addWidget(actions_row)

        return block

    def _build_mistake_review_state(self) -> QWidget:
        """Read-only inspection of the Quiz that just completed (DESIGN.md
        § 6.3 `VR-STUDY-001`, VR-STUDY-001 corrective pass § 3) -- stays
        inside this same Quiz/Immersive Focus surface rather than routing
        back to Review, and performs no re-grading, no new
        ``quiz_item_log``, and no new session/completion event: it only
        reads ``QuizController.mistakes``, the log rows ``_complete()``
        already fetched for the completion summary's own mistakes list."""
        controller = self._controller
        mistake = controller.current_mistake()
        block = QWidget()
        layout = QVBoxLayout(block)
        layout.setSpacing(SPACING.md)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        if mistake is None:
            layout.addWidget(_message_label("No mistakes to review.", "quiz-empty-state"))
            back_button = QPushButton("Back to summary", block)
            back_button.setObjectName("quiz-mistake-back-button")
            back_button.clicked.connect(controller.exit_mistake_review)
            layout.addWidget(back_button, 0, Qt.AlignmentFlag.AlignHCenter)
            return block

        position, total = controller.mistake_progress()
        position_label = QLabel(f"Mistake {position}/{total}", block)
        position_label.setObjectName("quiz-mistake-position-label")
        position_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(position_label)

        term_text = str(mistake.get("term") or "")
        quiz_type_label = QUIZ_TYPE_LABELS.get(mistake.get("quiz_type"), mistake.get("quiz_type") or "")
        context_bits = [bit for bit in (quiz_type_label, term_text) if bit]
        if context_bits:
            context_label = QLabel(" · ".join(context_bits), block)
            context_label.setObjectName("quiz-mistake-context-label")
            context_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(context_label)

        prompt = _WrappingLabel(str(mistake.get("prompt") or ""), block)
        prompt.setObjectName("quiz-term-label")
        prompt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        prompt.setWordWrap(True)
        layout.addWidget(prompt)
        layout.addSpacing(SPACING.lg)

        is_correct = bool(mistake.get("is_correct"))
        status_label = QLabel("Correct" if is_correct else "Wrong", block)
        status_label.setObjectName("quiz-feedback-correct" if is_correct else "quiz-feedback-wrong")
        status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(status_label)

        layout.addWidget(_field_block("Submitted answer", str(mistake.get("user_answer") or "(blank)"), block))
        layout.addWidget(_field_block("Expected", str(mistake.get("expected_answer") or ""), block))

        nav_row = QWidget(block)
        nav_layout = QHBoxLayout(nav_row)
        nav_layout.setSpacing(SPACING.md)
        nav_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        previous_button = QPushButton("← Previous", nav_row)
        previous_button.setObjectName("quiz-mistake-previous-button")
        previous_button.setFlat(True)
        previous_button.setEnabled(controller.can_go_previous_mistake())
        previous_button.clicked.connect(controller.go_previous_mistake)
        nav_layout.addWidget(previous_button)

        next_button = QPushButton("Next →", nav_row)
        next_button.setObjectName("quiz-mistake-next-button")
        next_button.setEnabled(controller.can_go_next_mistake())
        next_button.clicked.connect(controller.go_next_mistake)
        nav_layout.addWidget(next_button)

        layout.addWidget(nav_row)

        back_button = QPushButton("Back to summary", block)
        back_button.setObjectName("quiz-mistake-back-button")
        back_button.clicked.connect(controller.exit_mistake_review)
        layout.addWidget(back_button, 0, Qt.AlignmentFlag.AlignHCenter)

        return block

    def _on_return_to_today(self) -> None:
        # MainWindow reads quiz_controller.completed_session before it
        # resets state, so the signal fires first -- calling
        # acknowledge_completion() here first would erase that context.
        self.return_to_today_requested.emit()

    def _on_next_card(self) -> None:
        self.next_card_requested.emit()

    def _on_review_mistakes(self) -> None:
        # Stays inside QuizController/QuizView -- unlike Return to Today /
        # Next Card, this is not a workspace transition, so MainWindow is
        # never involved (VR-STUDY-001 corrective pass § 3).
        self._controller.review_mistakes()

    # -- exit / cancel / restart --------------------------------------------

    def _on_exit_clicked(self) -> None:
        controller = self._controller
        has_unfinished_active_quiz = (
            controller.intent is not None
            and controller.completed_session is None
            and controller.blocked_session is None
        )
        if not has_unfinished_active_quiz:
            # Nothing active to lose -- exit is unambiguous.
            if controller.completed_session is not None:
                controller.acknowledge_completion()
            self.exit_requested.emit()
            return
        dialog = _ExitQuizConfirmDialog(self)
        result = dialog.exec()
        if result == _ExitQuizConfirmDialog.RESULT_CANCEL_QUIZ:
            controller.exit_active()
            self.exit_requested.emit()
        elif result == _ExitQuizConfirmDialog.RESULT_RESTART_QUIZ:
            controller.restart_active()
        # RESULT_KEEP_QUIZZING (or a dismissed dialog): do nothing.


class _ExitQuizConfirmDialog(QDialog):
    """P6 restart/cancel session confirmation (DESIGN.md § 7.2). Leaving an
    active Quiz is a real choice with real consequences the user should see
    stated plainly, not a silent abandon."""

    RESULT_KEEP_QUIZZING = 0
    RESULT_CANCEL_QUIZ = 1
    RESULT_RESTART_QUIZ = 2

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("quiz-exit-confirm-dialog")
        self.setWindowTitle("Leave this Quiz?")
        self._result_code = self.RESULT_KEEP_QUIZZING

        layout = QVBoxLayout(self)
        message = _message_label(
            "Already-answered questions in this Quiz stay recorded. Unanswered "
            "questions will not be logged.",
            "quiz-exit-confirm-message",
        )
        layout.addWidget(message)

        buttons = QHBoxLayout()
        keep_button = QPushButton("Keep Quizzing", self)
        keep_button.clicked.connect(self.reject)
        buttons.addWidget(keep_button)

        restart_button = QPushButton("Restart Quiz", self)
        restart_button.setObjectName("quiz-exit-confirm-restart-button")
        restart_button.clicked.connect(self._choose_restart)
        buttons.addWidget(restart_button)

        cancel_button = QPushButton("Cancel Quiz", self)
        cancel_button.setObjectName("quiz-exit-confirm-cancel-button")
        cancel_button.setProperty("destructive", "true")
        cancel_button.clicked.connect(self._choose_cancel)
        buttons.addWidget(cancel_button)

        layout.addLayout(buttons)

    def _choose_restart(self) -> None:
        self._result_code = self.RESULT_RESTART_QUIZ
        self.accept()

    def _choose_cancel(self) -> None:
        self._result_code = self.RESULT_CANCEL_QUIZ
        self.accept()

    def exec(self) -> int:  # type: ignore[override]
        super().exec()
        return self._result_code


def _stat_block(value_text: str, label_text: str, parent: QWidget) -> QWidget:
    block = QWidget(parent)
    layout = QVBoxLayout(block)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

    value = QLabel(value_text, block)
    value.setObjectName("quiz-completion-stat-value")
    value.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(value)

    label = QLabel(label_text, block)
    label.setObjectName("quiz-completion-stat-label")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(label)

    return block


def _field_block(caption_text: str, value_text: str, parent: QWidget) -> QWidget:
    block = QWidget(parent)
    layout = QVBoxLayout(block)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

    caption = QLabel(caption_text, block)
    caption.setObjectName("quiz-field-caption")
    caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(caption)

    value = _WrappingLabel(value_text, block)
    value.setObjectName("quiz-field-text")
    value.setAlignment(Qt.AlignmentFlag.AlignCenter)
    value.setWordWrap(True)
    layout.addWidget(value)

    return block


def _message_label(text: str, object_name: str) -> QLabel:
    label = _WrappingLabel(text)
    label.setObjectName(object_name)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setWordWrap(True)
    return label


def _section_divider(parent: QWidget) -> QWidget:
    divider = QWidget(parent)
    divider.setObjectName("quiz-completion-divider")
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
