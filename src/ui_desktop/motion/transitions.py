from __future__ import annotations

from enum import Enum

from PySide6.QtCore import QEasingCurve, QObject, QPropertyAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

"""
Centralized desktop Motion / Transition Foundation (authorized additive
extension to the frozen DESIGN.md baseline; see DESIGN.md § 23 and the M17
Feature 1 prompt § 4). This is shared desktop-shell infrastructure, not
Today-owned business logic: ``MainWindow`` is the only caller in this
checkpoint, and any later Study Mode / Review / Quiz chrome reuses the same
``TransitionManager`` rather than inventing its own timers.

Design intent: subtle, responsive, calm, purposeful -- never flashy,
game-like, or decorative for its own sake. A single semantic policy
(``MotionPolicy``) controls every transition centrally so motion is never
inseparable from widget behavior.
"""


class MotionPolicy(str, Enum):
    NORMAL = "Normal"
    REDUCED = "Reduced"
    DISABLED = "Disabled"


DEFAULT_MOTION_POLICY = MotionPolicy.NORMAL

# Subtle, short durations per the design intent above -- not a decorative
# animation framework. Reduced is shorter still, not merely "off"; Disabled
# skips animation entirely (see fade_in()).
NORMAL_DURATION_MS = 160
REDUCED_DURATION_MS = 70


def parse_motion_policy(value: str) -> MotionPolicy:
    try:
        return MotionPolicy(value)
    except ValueError:
        return DEFAULT_MOTION_POLICY


class TransitionManager(QObject):
    """Single apply point for widget-reveal transitions.

    Correctness must never depend on this class: callers are required to
    finish the actual state change (e.g. ``QStackedWidget.setCurrentWidget``)
    synchronously *before* calling ``fade_in()``. This class only decorates
    an already-correct state with a subtle opacity reveal, and every code
    path here -- including interruption by a rapid repeated call -- always
    finalizes the target widget's opacity to fully visible.
    """

    def __init__(self, policy: MotionPolicy = DEFAULT_MOTION_POLICY) -> None:
        super().__init__()
        self._policy = policy
        # Keyed by the widget object itself, not id(widget): a bare id()
        # is a memory address that Python can and does reuse once an
        # unrelated object is garbage-collected, which would let a stale
        # dict entry silently apply to a different, later widget. Keying
        # by the widget keeps it referenced for exactly as long as it has
        # a tracked animation, which also cannot outlive this manager.
        self._animations: dict[QWidget, QPropertyAnimation] = {}

    @property
    def policy(self) -> MotionPolicy:
        return self._policy

    def set_policy(self, policy: MotionPolicy) -> None:
        self._policy = policy

    def is_animating(self, widget: QWidget) -> bool:
        return widget in self._animations

    def fade_in(self, widget: QWidget) -> QPropertyAnimation | None:
        """Reveal ``widget`` with a subtle opacity fade, or none at all.

        Safe to call repeatedly/rapidly on the same or different widgets:
        any animation already in flight for ``widget`` is stopped and its
        opacity immediately finalized to 1.0 before the new one starts, so
        no stale opacity or queued obsolete transition can remain -- the
        widget is always left fully visible whether a fade completes,
        is interrupted, or never starts (``DISABLED`` policy).
        """
        self._cancel(widget)

        if self._policy is MotionPolicy.DISABLED:
            widget.setGraphicsEffect(None)
            return None

        effect = QGraphicsOpacityEffect(widget)
        start_opacity = 0.35 if self._policy is MotionPolicy.REDUCED else 0.0
        effect.setOpacity(start_opacity)
        widget.setGraphicsEffect(effect)

        duration = (
            REDUCED_DURATION_MS if self._policy is MotionPolicy.REDUCED else NORMAL_DURATION_MS
        )
        # Parented to ``effect``, not to this long-lived manager: ``effect``
        # is owned by ``widget`` (QWidget.setGraphicsEffect() takes
        # ownership), so if the widget is ever destroyed while this
        # animation is still running -- something this manager cannot
        # prevent, since it does not own widget lifetimes -- Qt's normal
        # parent-child cascade destroys the animation along with its
        # target instead of leaving its timer ticking against a target
        # that no longer exists.
        animation = QPropertyAnimation(effect, b"opacity", effect)
        animation.setDuration(duration)
        animation.setStartValue(start_opacity)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(lambda: self._finalize(widget))

        self._animations[widget] = animation
        # Deliberately *not* QAbstractAnimation.DeletionPolicy.DeleteWhenStopped:
        # that policy schedules its own deferred deleteLater() the moment
        # the animation stops for any reason (including our own .stop()
        # calls below), independent of our bookkeeping. If this
        # TransitionManager (the animation's C++ parent) were ever torn
        # down before that deferred deletion is processed, Qt would try to
        # delete an animation whose parent had already cascade-deleted it
        # -- a double delete. Deletion is instead requested explicitly,
        # exactly once, in _cancel()/_finalize() below, whichever happens
        # first and only once.
        animation.start()
        return animation

    def _cancel(self, widget: QWidget) -> None:
        existing = self._animations.pop(widget, None)
        if existing is not None:
            existing.finished.disconnect()
            existing.stop()
            existing.deleteLater()
        effect = widget.graphicsEffect()
        if isinstance(effect, QGraphicsOpacityEffect):
            effect.setOpacity(1.0)

    def _finalize(self, widget: QWidget) -> None:
        animation = self._animations.pop(widget, None)
        if animation is not None:
            animation.deleteLater()
        effect = widget.graphicsEffect()
        if isinstance(effect, QGraphicsOpacityEffect):
            effect.setOpacity(1.0)
        widget.setGraphicsEffect(None)
