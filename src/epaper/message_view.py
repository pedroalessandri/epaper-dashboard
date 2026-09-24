"""Pantalla del modo mensaje: texto grande, centrado, dentro de un marco.

El tamaño de letra se ajusta solo: se prueba de mayor a menor hasta que el
texto, cortado por palabras, entra en el recuadro. Los saltos de línea que
escribió la persona se respetan.
"""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from epaper import fonts
from epaper.display import BLACK, HEIGHT, WIDTH, new_canvas
from epaper.tiles.text import ellipsize, width

MARGIN = 14  # del borde de la pantalla al marco exterior
PADDING = 44  # del marco interior al texto
MAX_SIZE = 112
MIN_SIZE = 24
LINE_SPACING = 1.18


def render_message(text: str) -> Image.Image:
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    _frame(draw)

    inner = PADDING + MARGIN
    max_w = WIDTH - 2 * inner
    max_h = HEIGHT - 2 * inner

    font, lines = _fit(draw, text, max_w, max_h)
    line_h = round(font.size * LINE_SPACING)
    total_h = line_h * len(lines)
    y = (HEIGHT - total_h) // 2 + line_h // 2
    for line in lines:
        draw.text((WIDTH // 2, y), line, font=font, fill=BLACK, anchor="mm")
        y += line_h
    return img


def _frame(draw: ImageDraw.ImageDraw) -> None:
    """Marco doble (grueso afuera, fino adentro) con esquinas marcadas."""
    x0, y0, x1, y1 = MARGIN, MARGIN, WIDTH - 1 - MARGIN, HEIGHT - 1 - MARGIN
    draw.rectangle((x0, y0, x1, y1), outline=BLACK, width=5)
    gap = 10
    ix0, iy0, ix1, iy1 = x0 + gap, y0 + gap, x1 - gap, y1 - gap
    draw.rectangle((ix0, iy0, ix1, iy1), outline=BLACK, width=2)
    # Un cuadradito lleno en cada esquina del marco interior.
    s = 7
    for cx, cy in ((ix0, iy0), (ix1, iy0), (ix0, iy1), (ix1, iy1)):
        draw.rectangle((cx - s, cy - s, cx + s, cy + s), fill=BLACK)


def _fit(
    draw: ImageDraw.ImageDraw, text: str, max_w: int, max_h: int
) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    size = MAX_SIZE
    while size >= MIN_SIZE:
        font = fonts.load(size, bold=True)
        lines = _wrap(draw, text, font, max_w)
        if round(size * LINE_SPACING) * len(lines) <= max_h:
            return font, lines
        size -= 4 if size > 48 else 2

    # Ni al mínimo entra: se cortan las líneas que sobran y se marca con "…".
    font = fonts.load(MIN_SIZE, bold=True)
    lines = _wrap(draw, text, font, max_w)
    fit = max(1, max_h // round(MIN_SIZE * LINE_SPACING))
    if len(lines) > fit:
        lines = lines[:fit]
        lines[-1] = ellipsize(draw, lines[-1] + " …", font, max_w)
    return font, lines


def _wrap(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int
) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        start = len(lines)
        current = ""
        for word in paragraph.split():
            # Una palabra que sola no entra se parte por caracteres.
            while width(draw, word, font) > max_w:
                cut = len(word)
                while cut > 1 and width(draw, word[:cut], font) > max_w:
                    cut -= 1
                if current:
                    lines.append(current)
                    current = ""
                lines.append(word[:cut])
                word = word[cut:]
            candidate = f"{current} {word}".strip()
            if width(draw, candidate, font) <= max_w:
                current = candidate
            else:
                lines.append(current)
                current = word
        # Sin palabras huérfanas: si el párrafo termina con una sola palabra
        # en su renglón, se baja la última del renglón anterior
        # ("Vuelvo a las 20 / hs." -> "Vuelvo a las / 20 hs.").
        prev = lines[-1].split() if len(lines) > start else []
        if len(current.split()) == 1 and len(prev) >= 3:
            moved = f"{prev[-1]} {current}"
            if width(draw, moved, font) <= max_w:
                lines[-1] = " ".join(prev[:-1])
                current = moved
        lines.append(current)  # un renglón vacío se respeta como espacio
    while lines and not lines[-1]:
        lines.pop()
    return lines
