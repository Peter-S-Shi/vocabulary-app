from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.ui_desktop.controllers.quiz_controller import MATCHING_FAMILY, MCQ_FAMILY, QuizController
from src.ui_desktop.state.handoff import QUIZ_TYPE_LABELS
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
                               mistakes list + three next actions, staying
                               inside Immersive Focus (DESIGN.md § 6.3:
                               never a KPI dashboard).
  exit/return                -> Return to Today exits Study Mode entirely;
                               Next Card / Review Mistakes both return to
                               Review (Study Mode stays active) rather than
                               auto-starting another Quiz -- MainWindow
                               orchestrates through AppState like every
                               other transition.

Frozen learning semantics (unchanged from Review, now load-bearing here):
starting Quiz, answering some items, or cancelling are never themselves a
completion event -- only ``QuizController._complete()`` (a fully-answered
session reaching ``mark_quiz_session_completed``) is. A whole-
Collection/random Quiz remains Entry-level evidence only; nothing here
fabricates a Card completion for one.
"""

MAIN_COLUMN_MAX_WIDTH = 640
MATCHING_COLUMN_MAX_WIDTH = 880


class QuizView(QWidget):
    exit_requested = Signal()
    return_to_today_requested = Signal()
    review_mistakes_requested = Signal()
    next_card_requested = Signal()

    def __init__(self, controller: QuizController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("quiz-root")
        self._controller = controller

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_session_bar())

        self._surface = QWidget(self)
        self._surface.setObjectName("quiz-main-surface")
        outer = QVBoxLayout(self._surface)
        outer.setContentsMargins(SPACING.xl, SPACING.xl, SPACING.xl, SPACING.xl)

        self._column = QWidget(self._surface)
        self._column_layout = QVBoxLayout(self._column)
        self._column_layout.setSpacing(SPACING.lg)
        self._column_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        outer.addStretch(1)
        outer.addWidget(self._column, 0, Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch(1)

        root.addWidget(self._surface, 1)

        controller.state_changed.connect(self._render)

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
        if family == MATCHING_FAMILY:
            self._column.setMaximumWidth(MATCHING_COLUMN_MAX_WIDTH)
            self._column_layout.addWidget(self._build_matching_task())
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
        controller = self._controller
        item = controller.current_item()
        block = QWidget()
        layout = QVBoxLayout(block)
        layout.setSpacing(SPACING.md)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        if item is None:
            layout.addWidget(_message_label("This Quiz has no items.", "quiz-empty-state"))
            return block

        term = QLabel(str(item.get("prompt") or ""), block)
        term.setObjectName("quiz-term-label")
        term.setAlignment(Qt.AlignmentFlag.AlignCenter)
        term.setWordWrap(True)
        layout.addWidget(term)
        # Extra separation on top of the uniform inter-item spacing above --
        # the prompt is its own group; the answer surface below it is a
        # distinct group (visual-calibration corrective pass § 15).
        layout.addSpacing(SPACING.lg)

        answer_input = QLineEdit(block)
        answer_input.setObjectName("quiz-answer-input")
        answer_input.setPlaceholderText("Your answer")
        answer_input.setText(controller.answer_draft)
        answer_input.setEnabled(not controller.show_answer)
        answer_input.textChanged.connect(controller.set_answer_draft)
        layout.addWidget(answer_input)

        if not controller.show_answer:
            show_button = QPushButton("Show Answer", block)
            show_button.setObjectName("quiz-show-answer-button")
            show_button.clicked.connect(controller.reveal_answer)
            layout.addWidget(show_button, 0, Qt.AlignmentFlag.AlignHCenter)
        else:
            layout.addWidget(_field_block("Your answer", controller.answer_draft or "(blank)", block))
            layout.addWidget(_field_block("Expected", str(item.get("expected_answer") or ""), block))

            grade_row = QWidget(block)
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

        return block

    # -- MCQ -------------------------------------------------------------

    def _build_mcq_task(self) -> QWidget:
        controller = self._controller
        item = controller.current_item()
        block = QWidget()
        layout = QVBoxLayout(block)
        layout.setSpacing(SPACING.md)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        if item is None:
            layout.addWidget(_message_label("This Quiz has no items.", "quiz-empty-state"))
            return block

        term = QLabel(str(item.get("prompt") or ""), block)
        term.setObjectName("quiz-term-label")
        term.setAlignment(Qt.AlignmentFlag.AlignCenter)
        term.setWordWrap(True)
        layout.addWidget(term)
        layout.addSpacing(SPACING.lg)

        feedback = controller.feedback
        if feedback is None:
            group = QButtonGroup(block)
            self._mcq_group = group
            for option in item.get("options") or []:
                button = QRadioButton(str(option), block)
                button.setObjectName("quiz-mcq-option")
                group.addButton(button)
                layout.addWidget(button)

            submit_button = QPushButton("Submit", block)
            submit_button.setObjectName("quiz-mcq-submit-button")
            submit_button.clicked.connect(lambda: self._submit_mcq(group))
            layout.addWidget(submit_button, 0, Qt.AlignmentFlag.AlignHCenter)
        else:
            is_correct = bool(feedback.get("is_correct"))
            feedback_label = QLabel("Correct" if is_correct else "Wrong", block)
            feedback_label.setObjectName("quiz-feedback-correct" if is_correct else "quiz-feedback-wrong")
            feedback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(feedback_label)

            layout.addWidget(_field_block("Your answer", str(feedback.get("selected") or ""), block))
            layout.addWidget(_field_block("Expected", str(feedback.get("expected_answer") or ""), block))

            next_button = QPushButton("Next Question", block)
            next_button.setObjectName("quiz-mcq-next-button")
            next_button.clicked.connect(controller.advance_after_mcq)
            layout.addWidget(next_button, 0, Qt.AlignmentFlag.AlignHCenter)

        return block

    def _submit_mcq(self, group: QButtonGroup) -> None:
        selected = group.checkedButton()
        if selected is None:
            return
        self._controller.submit_mcq(selected.text())

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

        return block

    def _build_matching_row(self, item: dict, choices: list[str]) -> QWidget:
        controller = self._controller
        row = QWidget()
        row.setObjectName("quiz-matching-row")
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(row)
        layout.setSpacing(SPACING.sm)

        term_label = QLabel(str(item.get("term") or ""), row)
        term_label.setObjectName("quiz-matching-term-label")
        layout.addWidget(term_label, 1)

        combo = QComboBox(row)
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
        mistakes_label = QLabel(mistakes_text, block)
        mistakes_label.setObjectName("quiz-completion-mistakes-list")
        mistakes_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mistakes_label.setWordWrap(True)
        layout.addWidget(mistakes_label)

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

        review_mistakes_button = QPushButton("Review Mistakes", actions_row)
        review_mistakes_button.setObjectName("quiz-completion-review-mistakes-button")
        review_mistakes_button.clicked.connect(self._on_review_mistakes)
        actions_layout.addWidget(review_mistakes_button)

        layout.addWidget(actions_row)

        return block

    def _on_return_to_today(self) -> None:
        # MainWindow reads quiz_controller.completed_session before it
        # resets state, so the signal fires first -- calling
        # acknowledge_completion() here first would erase that context.
        self.return_to_today_requested.emit()

    def _on_next_card(self) -> None:
        self.next_card_requested.emit()

    def _on_review_mistakes(self) -> None:
        self.review_mistakes_requested.emit()

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

    value = QLabel(value_text, block)
    value.setObjectName("quiz-field-text")
    value.setAlignment(Qt.AlignmentFlag.AlignCenter)
    value.setWordWrap(True)
    layout.addWidget(value)

    return block


def _message_label(text: str, object_name: str) -> QLabel:
    label = QLabel(text)
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
