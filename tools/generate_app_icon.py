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
it as a standard Windows multi-resolution ICO (16x16, 24x24, 32x32, 48x48,
64x64, 128x128, 256x256).

Windows Explorer Compatibility:
- Sizes <= 128x128 are encoded as standard uncompressed 32-bit DIB bitmaps
  (BITMAPINFOHEADER + BGRA XOR mask + 1bpp AND mask). This ensures native
  GDI compatibility in Windows File Explorer folder views, list views,
  and desktop icon views without rendering placeholder bounding boxes.
- Size 256x256 is encoded as PNG per the official Vista+ icon standard.

Run to (re)generate the tracked asset:
    python tools/generate_app_icon.py
"""

OUTPUT_PATH = PROJECT_ROOT / "assets" / "icons" / "vocabulary_app.ico"
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


def render_icon_image(size: int) -> QImage:
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

    return image


def encode_frame_png(image: QImage) -> bytes:
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buf, "PNG")
    return bytes(buf.data())


def encode_frame_dib(image: QImage) -> bytes:
    """Encode QImage as standard Windows 32-bit ICO DIB bitmap (BITMAPINFOHEADER + XOR + AND)."""
    w = image.width()
    h = image.height()

    # BITMAPINFOHEADER: biSize(40), biWidth(w), biHeight(h*2), biPlanes(1), biBitCount(32),
    # biCompression(BI_RGB=0), biSizeImage(w*h*4), biXPels(0), biYPels(0), biClrUsed(0), biClrImp(0)
    bih = struct.pack("<IIIHHIIIIII", 40, w, h * 2, 1, 32, 0, w * h * 4, 0, 0, 0, 0)

    # 32-bit BGRA pixels, bottom-up order
    xor_mask = bytearray()
    for y in range(h - 1, -1, -1):
        for x in range(w):
            c = image.pixelColor(x, y)
            xor_mask.extend([c.blue(), c.green(), c.red(), c.alpha()])

    # 1-bit transparency AND mask, bottom-up order (row padded to 32-bit boundary)
    row_bytes = (w + 7) // 8
    padded_row_bytes = (row_bytes + 3) & ~3
    and_mask = bytearray()
    for y in range(h - 1, -1, -1):
        row = bytearray(padded_row_bytes)
        for x in range(w):
            c = image.pixelColor(x, y)
            if c.alpha() == 0:
                row[x // 8] |= 1 << (7 - (x % 8))
        and_mask.extend(row)

    return bih + xor_mask + and_mask


def build_multi_size_ico(sizes: tuple[int, ...] = ICON_SIZES) -> bytes:
    frames: list[tuple[int, bytes]] = []
    for s in sizes:
        img = render_icon_image(s)
        if s == 256:
            frames.append((s, encode_frame_png(img)))
        else:
            frames.append((s, encode_frame_dib(img)))

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

    print(f"Wrote {OUTPUT_PATH} ({len(ico_bytes)} bytes across {len(ICON_SIZES)} resolutions with native DIB+PNG)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
