from __future__ import annotations

from dataclasses import dataclass

"""
Minimal reusable layout metrics for the Today Command Center + shared
Management Shell (DESIGN.md § 22: compact spacing scale, one restrained
small-to-moderate radius language). This is deliberately not the full
typography/spacing/radius/row-density/page-margin token layer that was
removed in the M17 Today UI reset -- only the metrics this checkpoint's
shared shell and Today composition genuinely need, derived from the
current replacement DESIGN authority rather than reused from the rejected
implementation.
"""


@dataclass(frozen=True)
class Spacing:
    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 24


SPACING = Spacing()

# One restrained small-to-moderate radius language (DESIGN.md § 22), used
# for the nav rail selection, cards, and buttons introduced this checkpoint.
RADIUS_DEFAULT = 6

NAV_RAIL_WIDTH = 188
CONTEXT_RAIL_WIDTH = 260
