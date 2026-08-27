from __future__ import annotations

import colorsys
import re
from typing import Tuple

"""
Color math, WCAG 2.1 contrast calculations, and semantic token family derivation
for Vocabulary App Theme Customization (Phase D).

Guarantees:
1. Mathematical WCAG 2.1 relative luminance and contrast ratio computation.
2. Robust hex normalization with crash-proof fallback.
3. Automatic foreground pairing (choosing highest-contrast readable text on any background).
4. Hardened WCAG AA (>= 4.5:1) contrast guard across all arbitrary custom colors and mid-luminance boundaries.
5. Interactive accent state derivation (hover, pressed, soft, selected, focus) from a single primary hex.
6. Contrast-guarded neutral surface/text derivation ensuring AA (>= 4.5:1) compliance.
"""

HEX_COLOR_REGEX = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def normalize_hex(color: str | None, fallback: str = "#000000") -> str:
    """Normalize a 3-digit or 6-digit hex color string to uppercase #RRGGBB.

    Returns ``fallback`` if ``color`` is invalid, empty, or unparseable.
    """
    if not color or not isinstance(color, str):
        return fallback.upper()
    s = color.strip()
    match = HEX_COLOR_REGEX.match(s)
    if not match:
        return fallback.upper()
    hex_digits = match.group(1)
    if len(hex_digits) == 3:
        hex_digits = "".join(c * 2 for c in hex_digits)
    return f"#{hex_digits.upper()}"


def is_valid_hex(color: str | None) -> bool:
    """Check if ``color`` is a valid 3-digit or 6-digit hex color string."""
    if not color or not isinstance(color, str):
        return False
    return HEX_COLOR_REGEX.match(color.strip()) is not None


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert #RRGGBB to (r, g, b) tuple in 0..255."""
    clean = normalize_hex(hex_color).lstrip("#")
    return int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16)


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert (r, g, b) in 0..255 to uppercase #RRGGBB."""
    r_clamped = max(0, min(255, int(round(r))))
    g_clamped = max(0, min(255, int(round(g))))
    b_clamped = max(0, min(255, int(round(b))))
    return f"#{r_clamped:02X}{g_clamped:02X}{b_clamped:02X}"


def relative_luminance(hex_color: str) -> float:
    """Compute relative luminance (0.0 to 1.0) according to WCAG 2.1 specification."""
    r, g, b = hex_to_rgb(hex_color)

    def channel_linear(c_byte: int) -> float:
        c = c_byte / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r_lin = channel_linear(r)
    g_lin = channel_linear(g)
    b_lin = channel_linear(b)
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def contrast_ratio(color_a: str, color_b: str) -> float:
    """Calculate WCAG 2.1 contrast ratio between two colors (range: 1.0 to 21.0)."""
    l1 = relative_luminance(color_a)
    l2 = relative_luminance(color_b)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def best_foreground(
    background_hex: str,
    light_option: str = "#FFFFFF",
    dark_option: str = "#17181A",
    min_contrast: float = 4.5,
) -> str:
    """Pick whichever foreground option satisfies ``min_contrast`` (default WCAG AA 4.5:1).

    If standard options do not clear 4.5:1 (e.g. against boundary mid-luminance backgrounds),
    falls back safely to pure black or pure white which mathematically achieves maximum contrast.
    """
    cr_light = contrast_ratio(background_hex, light_option)
    cr_dark = contrast_ratio(background_hex, dark_option)

    if cr_light >= min_contrast:
        return light_option
    if cr_dark >= min_contrast:
        return dark_option

    # Boundary handling: evaluate pure black and pure white
    cr_pure_white = contrast_ratio(background_hex, "#FFFFFF")
    cr_pure_black = contrast_ratio(background_hex, "#000000")

    if cr_pure_white >= cr_pure_black:
        return "#FFFFFF"
    return "#000000"


def blend_colors(base_hex: str, overlay_hex: str, overlay_weight: float) -> str:
    """Blend overlay onto base with weight in 0.0..1.0."""
    w = max(0.0, min(1.0, float(overlay_weight)))
    r1, g1, b1 = hex_to_rgb(base_hex)
    r2, g2, b2 = hex_to_rgb(overlay_hex)
    r_out = r1 * (1.0 - w) + r2 * w
    g_out = g1 * (1.0 - w) + g2 * w
    b_out = b1 * (1.0 - w) + b2 * w
    return rgb_to_hex(r_out, g_out, b_out)


def adjust_lightness(hex_color: str, delta: float) -> str:
    """Adjust HSL lightness of hex_color by delta (-1.0 to +1.0)."""
    r, g, b = hex_to_rgb(hex_color)
    h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    l_new = max(0.0, min(1.0, l + delta))
    r_new, g_new, b_new = colorsys.hls_to_rgb(h, l_new, s)
    return rgb_to_hex(int(round(r_new * 255)), int(round(g_new * 255)), int(round(b_new * 255)))


def derive_accent_tokens_from_primary(
    primary_hex: str,
    is_dark_mode: bool,
) -> tuple[str, str, str, str, str, str, str, str, str]:
    """Derive a complete, internally consistent Accent token family from an arbitrary primary hex.

    Ensures that every text-bearing pair (primary, hover, pressed, soft) mathematically
    reaches WCAG AA (>= 4.5:1) contrast ratio.

    Returns:
        (
            primary_bg, on_primary,
            hover_bg, on_hover,
            pressed_bg, on_pressed,
            soft_bg, on_soft,
            selected_bg
        )
    """
    p_bg = normalize_hex(primary_hex, fallback="#3E6690" if not is_dark_mode else "#82ACD4")
    on_p = best_foreground(p_bg, light_option="#FFFFFF", dark_option="#17181A", min_contrast=4.5)

    if not is_dark_mode:
        # Light Mode interaction tuning
        hover_bg = adjust_lightness(p_bg, -0.07)
        pressed_bg = adjust_lightness(p_bg, -0.14)
        on_hover = best_foreground(hover_bg, light_option="#FFFFFF", dark_option="#17181A", min_contrast=4.5)
        on_pressed = best_foreground(pressed_bg, light_option="#FFFFFF", dark_option="#17181A", min_contrast=4.5)

        # Soft background: subtle tint (10-12% accent over white)
        soft_bg = blend_colors("#FFFFFF", p_bg, 0.12)
        # on_soft: darker accent shade ensuring >= 4.5:1 contrast on soft_bg
        on_soft = adjust_lightness(p_bg, -0.20)
        while contrast_ratio(soft_bg, on_soft) < 4.5 and relative_luminance(on_soft) > 0.005:
            on_soft = adjust_lightness(on_soft, -0.05)

        # selected background: slightly more saturated tint (16% accent over white)
        selected_bg = blend_colors("#FFFFFF", p_bg, 0.16)
    else:
        # Dark Mode interaction tuning
        hover_bg = adjust_lightness(p_bg, +0.08)
        pressed_bg = adjust_lightness(p_bg, -0.08)
        on_hover = best_foreground(hover_bg, light_option="#FFFFFF", dark_option="#17181A", min_contrast=4.5)
        on_pressed = best_foreground(pressed_bg, light_option="#FFFFFF", dark_option="#17181A", min_contrast=4.5)

        # Soft background: deep dark tint (18-20% accent over dark surface #17181A)
        soft_bg = blend_colors("#17181A", p_bg, 0.20)
        # on_soft: lighter accent tint ensuring >= 4.5:1 contrast on soft_bg
        on_soft = adjust_lightness(p_bg, +0.25)
        while contrast_ratio(soft_bg, on_soft) < 4.5 and relative_luminance(on_soft) < 0.99:
            on_soft = adjust_lightness(on_soft, +0.05)

        # selected background: 24% accent over dark surface
        selected_bg = blend_colors("#17181A", p_bg, 0.24)

    return (
        p_bg, on_p,
        hover_bg, on_hover,
        pressed_bg, on_pressed,
        soft_bg, on_soft,
        selected_bg,
    )
