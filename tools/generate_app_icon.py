from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QImageWriter, QPainter, QPainterPath
from PySide6.QtWidgets import QApplication

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.ui_desktop.theming.tokens import ACCENT_CALM_BLUE_LIGHT  # noqa: E402

"""
One-time/regenerable repository asset generator: draws a small, calm,
desktop-native "V" monogram badge using the frozen default Calm Blue
accent-primary/on-accent-primary token pair (DESIGN.md § 11.2), and saves
it as a single 256x256 ICO -- no external image-editing dependency, no
Pillow. This is a local development/build tool, not a runtime dependency:
the PySide6 application does not import this module.

Run to (re)generate the tracked asset:
    python tools/generate_app_icon.py

The output, assets/icons/vocabulary_app.ico, is committed to the
repository like any other project asset; contributors do not need to
re-run this unless the icon design changes.
"""

OUTPUT_PATH = PROJECT_ROOT / "assets" / "icons" / "vocabulary_app.ico"
SIZE = 256


def build_icon_image(size: int = SIZE) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 0))

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    background = QColor(ACCENT_CALM_BLUE_LIGHT.primary.background)
    foreground = QColor(ACCENT_CALM_BLUE_LIGHT.primary.foreground)

    margin = size * 0.06
    rect = QRectF(margin, margin, size - 2 * margin, size - 2 * margin)
    radius = size * 0.22

    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    painter.fillPath(path, background)

    font = QFont("Segoe UI", 0, QFont.Weight.Bold)
    font.setPixelSize(int(size * 0.52))
    painter.setFont(font)
    painter.setPen(foreground)
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "V")

    painter.end()
    return image


def main() -> int:
    # QFont/QPainter text rendering needs an initialized font database,
    # which requires a constructed QGuiApplication/QApplication instance.
    application = QApplication.instance() or QApplication([])

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    image = build_icon_image()
    writer = QImageWriter(str(OUTPUT_PATH), b"ico")
    if not writer.write(image):
        print(f"Failed to write icon: {writer.errorString()}")
        return 1

    print(f"Wrote {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
