from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath
from PySide6.QtWidgets import QApplication

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.ui_desktop.theming.tokens import ACCENT_CALM_BLUE_LIGHT  # noqa: E402

"""
One-time/regenerable repository asset generator: draws a small, calm,
desktop-native "V" monogram badge using the frozen default Calm Blue
accent-primary/on-accent-primary token pair (DESIGN.md § 11.2), and saves
it as a multi-resolution ICO (16x16, 24x24, 32x32, 48x48, 64x64, 128x128, 256x256)
so Windows title bar, taskbar, Alt+Tab, and desktop shortcuts render crisp
native icons without downscaling artifacts.

Run to (re)generate the tracked asset:
    python tools/generate_app_icon.py
"""

OUTPUT_PATH = PROJECT_ROOT / "assets" / "icons" / "vocabulary_app.ico"
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


def render_icon_png_bytes(size: int) -> bytes:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 0))

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

    background = QColor(ACCENT_CALM_BLUE_LIGHT.primary.background)
    foreground = QColor(ACCENT_CALM_BLUE_LIGHT.primary.foreground)

    margin = max(1.0, size * 0.06)
    rect = QRectF(margin, margin, size - 2 * margin, size - 2 * margin)
    radius = max(2.0, size * 0.22)

    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    painter.fillPath(path, background)

    font = QFont("Segoe UI", 0, QFont.Weight.Bold)
    font.setPixelSize(max(8, int(size * 0.54)))
    painter.setFont(font)
    painter.setPen(foreground)
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "V")
    painter.end()

    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buf, "PNG")
    return bytes(buf.data())


def build_multi_size_ico(sizes: tuple[int, ...] = ICON_SIZES) -> bytes:
    frames = [(s, render_icon_png_bytes(s)) for s in sizes]

    header = struct.pack("<HHH", 0, 1, len(frames))
    offset = 6 + 16 * len(frames)
    entries = bytearray()
    payloads = bytearray()

    for s, data in frames:
        w_byte = 0 if s == 256 else s
        h_byte = 0 if s == 256 else s
        entry = struct.pack("<BBBBHHII", w_byte, h_byte, 0, 0, 1, 32, len(data), offset)
        entries.extend(entry)
        payloads.extend(data)
        offset += len(data)

    return header + entries + payloads


def main() -> int:
    _app = QApplication.instance() or QApplication([])

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ico_bytes = build_multi_size_ico()
    OUTPUT_PATH.write_bytes(ico_bytes)

    print(f"Wrote {OUTPUT_PATH} ({len(ico_bytes)} bytes across {len(ICON_SIZES)} resolutions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
