"""Tiny pure-Python PNG writer + bar chart.

The project has no plotting dependency, and the evaluation report wants a
readable picture, so this module writes an RGBA PNG entirely with ``zlib`` and
``struct`` and renders a small bitmap font by hand. No third-party packages.
"""
from __future__ import annotations

import struct
import zlib


# --------------------------------------------------------------------------- #
# 5x7 bitmap font (MSB = leftmost column)
# --------------------------------------------------------------------------- #

_FONT = {
    "A": (0b01110, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b00000),
    "B": (0b11110, 0b10001, 0b10001, 0b11110, 0b10001, 0b10001, 0b11110),
    "C": (0b01110, 0b10001, 0b10000, 0b10000, 0b10000, 0b10001, 0b01110),
    "D": (0b11100, 0b10010, 0b10001, 0b10001, 0b10001, 0b10010, 0b11100),
    "E": (0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b11111),
    "F": (0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b10000),
    "G": (0b01110, 0b10001, 0b10000, 0b10111, 0b10001, 0b10001, 0b01111),
    "H": (0b10001, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001),
    "I": (0b01110, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110),
    "J": (0b00111, 0b00010, 0b00010, 0b00010, 0b00010, 0b10010, 0b01100),
    "K": (0b10001, 0b10010, 0b10100, 0b11000, 0b10100, 0b10010, 0b10001),
    "L": (0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b11111),
    "M": (0b10001, 0b11011, 0b10101, 0b10101, 0b10001, 0b10001, 0b10001),
    "N": (0b10001, 0b11001, 0b10101, 0b10011, 0b10001, 0b10001, 0b10001),
    "O": (0b01110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110),
    "P": (0b11110, 0b10001, 0b10001, 0b11110, 0b10000, 0b10000, 0b10000),
    "Q": (0b01110, 0b10001, 0b10001, 0b10001, 0b10101, 0b10010, 0b01101),
    "R": (0b11110, 0b10001, 0b10001, 0b11110, 0b10100, 0b10010, 0b10001),
    "S": (0b01111, 0b10000, 0b10000, 0b01110, 0b00001, 0b00001, 0b11110),
    "T": (0b11111, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100),
    "U": (0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110),
    "V": (0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01010, 0b00100),
    "W": (0b10001, 0b10001, 0b10001, 0b10101, 0b10101, 0b10001, 0b10010),
    "X": (0b10001, 0b10001, 0b01010, 0b00100, 0b01010, 0b10001, 0b10001),
    "Y": (0b10001, 0b10001, 0b01010, 0b00100, 0b00100, 0b00100, 0b00100),
    "Z": (0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b10000, 0b11111),
    "0": (0b01110, 0b10001, 0b10011, 0b10101, 0b11001, 0b10001, 0b01110),
    "1": (0b00100, 0b01100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110),
    "2": (0b01110, 0b10001, 0b00001, 0b00110, 0b01000, 0b10000, 0b11111),
    "3": (0b11110, 0b00001, 0b00001, 0b01110, 0b00001, 0b00001, 0b11110),
    "4": (0b00010, 0b00110, 0b01010, 0b10010, 0b11111, 0b00010, 0b00010),
    "5": (0b11111, 0b10000, 0b10000, 0b11110, 0b00001, 0b00001, 0b11110),
    "6": (0b01110, 0b10000, 0b10000, 0b11110, 0b10001, 0b10001, 0b01110),
    "7": (0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b01000, 0b01000),
    "8": (0b01110, 0b10001, 0b10001, 0b01110, 0b10001, 0b10001, 0b01110),
    "9": (0b01110, 0b10001, 0b10001, 0b01111, 0b00001, 0b00001, 0b01110),
    " ": (0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00000),
    ".": (0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00110, 0b00110),
    "-": (0b00000, 0b00000, 0b00000, 0b11111, 0b00000, 0b00000, 0b00000),
    ":": (0b00000, 0b00110, 0b00110, 0b00000, 0b00110, 0b00110, 0b00000),
    "/": (0b00001, 0b00010, 0b00010, 0b00100, 0b01000, 0b01000, 0b10000),
    "%": (0b11001, 0b11010, 0b00010, 0b00100, 0b01000, 0b01011, 0b10011),
    "&": (0b01100, 0b10010, 0b10100, 0b01000, 0b10101, 0b10010, 0b01101),
    "_": (0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b11111),
    "(": (0b00100, 0b01000, 0b01000, 0b01000, 0b01000, 0b01000, 0b00100),
    ")": (0b00100, 0b00010, 0b00010, 0b00010, 0b00010, 0b00010, 0b00100),
}

# Warm, muted palette (no hardcoded chart-specific colors beyond these).
_BG = (31, 36, 33, 255)
_GRID = (61, 68, 64, 255)
_TEXT = (237, 231, 220, 255)
_FADED = (176, 168, 155, 255)
_PALETTE = (
    (232, 168, 124, 255),
    (221, 190, 120, 255),
    (151, 187, 138, 255),
    (138, 173, 199, 255),
    (199, 143, 168, 255),
    (160, 148, 199, 255),
)


# --------------------------------------------------------------------------- #
# PNG primitives
# --------------------------------------------------------------------------- #

def _chunk(tag: bytes, data: bytes) -> bytes:
    payload = tag + data
    return struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload))


def write_png(path, width: int, height: int, pixels) -> None:
    """Serialize RGBA pixel rows ((r,g,b,a) tuples) to a PNG file."""
    raw = bytearray()
    for row in pixels:
        raw.append(0)  # filter: none
        for r, g, b, a in row:
            raw.extend((r, g, b, a))
    header = (
        struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)  # RGBA8, non-interlaced
    )
    out = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _chunk(b"IEND", b"")
    )
    with open(path, "wb") as fh:
        fh.write(out)


class Canvas:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.pixels = [[_BG for _ in range(width)] for _ in range(height)]

    def set(self, x: int, y: int, color) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixels[y][x] = color if color is not None else (_BG if False else color)

    def rect(self, x0: int, y0: int, x1: int, y1: int, color) -> None:
        for y in range(y0, y1 + 1):
            row = self.pixels[y] if 0 <= y < self.height else None
            if row is None:
                continue
            for x in range(max(0, x0), min(self.width, x1 + 1)):
                row[x] = color

    def hline(self, x0: int, x1: int, y: int, color) -> None:
        self.rect(x0, y, x1, y, color)

    def vline(self, x: int, y0: int, y1: int, color) -> None:
        self.rect(x, y0, x, y1, color)

    def text(self, x: int, y: int, text: str, color, scale: int = 1) -> None:
        text = (text or "").upper()
        cursor = x
        for char in text:
            glyph = _FONT.get(char)
            if glyph is None:
                cursor += 6 * scale
                continue
            for row, bits in enumerate(glyph):
                for col in range(5):
                    if bits & (1 << (4 - col)):
                        px, py = cursor + col * scale, y + row * scale
                        self.rect(px, py, px + scale - 1, py + scale - 1, color)
            cursor += 6 * scale  # 5 px glyph + 1 px spacing


# --------------------------------------------------------------------------- #
# Bar chart
# --------------------------------------------------------------------------- #

def render_bar_chart(path, items: list[tuple[str, int]], title: str, subtitle: str, footer: str = "") -> str:
    """Render ``[(label, score0-100), ...]`` to a 1000x560 PNG bar chart.

    Returns the path written.
    """
    W, H = 1000, 560
    canvas = Canvas(W, H)

    # Title + subtitle
    title_y = 26
    _center_text(canvas, title, title_y, _TEXT, scale=2)
    _center_text(canvas, subtitle, title_y + 34, _FADED, scale=1)
    if footer:
        _center_text(canvas, footer, H - 16, _FADED, scale=1)

    # Plot area
    L, R, T, B = 90, W - 40, title_y + 70, H - 46
    n = max(len(items), 1)
    for value in (0, 25, 50, 75, 100):
        y = T + int((B - T) * (100 - value) / 100)
        canvas.hline(L, R, y, _GRID)
        _right_align(canvas, L - 8, y - 3, str(value), _FADED, scale=1)

    col_w = (R - L) / n
    bar_w = min(46, col_w * 0.5)
    for i, (label, score) in enumerate(items):
        score = max(0, min(100, int(round(score))))
        cx = L + int(col_w * i + col_w / 2)
        bar_h = int((B - T) * score / 100)
        bar_color = _PALETTE[i % len(_PALETTE)]
        x0 = max(L, cx - int(bar_w / 2))
        canvas.rect(x0, B - bar_h, x0 + int(bar_w), B, bar_color)
        # value label
        _center_text(canvas, str(score), B - bar_h - 16, _TEXT, scale=1)
        # wrapped x label
        lines = _wrap_label(label)
        gap = 18
        for j, line in enumerate(lines):
            _center_text(canvas, line, B + 8 + j * gap, _TEXT, scale=1)

    write_png(path, W, H, canvas.pixels)
    return path


def _center_text(canvas, text: str, y: int, color, scale: int = 1) -> None:
    width = len(text) * 6 * scale
    canvas.text((canvas.width - width) // 2, y, text, color, scale)


def _right_align(canvas, x_right: int, y: int, text: str, color, scale: int = 1) -> None:
    width = len(text) * 6 * scale
    canvas.text(x_right - width, y, text, color, scale)


def _wrap_label(label: str) -> list[str]:
    words = label.replace("-", " - ").split()
    lines: list[str] = []
    current = ""
    for word in words:
        if current and len(current) + 1 + len(word) > 10:
            lines.append(current.strip("- "))
            current = word
        else:
            current = (current + " " + word).strip()
    if current:
        lines.append(current.strip("- "))
    return lines or [label]