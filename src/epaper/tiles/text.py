"""Helpers de texto compartidos por los tiles."""

from __future__ import annotations

from datetime import datetime

from PIL import ImageDraw, ImageFont

from epaper import fonts

DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
DIAS_CORTOS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
    "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


def strftime_es(dt: datetime, fmt: str) -> str:
    """``strftime`` con nombres de día y mes en castellano.

    No depende del locale del sistema: en la notebook puede no estar generado
    y el preview tiene que salir igual que en la Pi.
    """
    fmt = (
        fmt.replace("%A", DIAS[dt.weekday()])
        .replace("%a", DIAS_CORTOS[dt.weekday()])
        .replace("%B", MESES[dt.month - 1])
        .replace("%b", MESES[dt.month - 1][:3])
    )
    return dt.strftime(fmt)


def width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    left, _, right, _ = draw.textbbox((0, 0), text, font=font)
    return right - left


def fit_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    size: int,
    min_size: int = fonts.MIN_SIZE,
    bold: bool = False,
) -> ImageFont.FreeTypeFont:
    """La fuente más grande (hasta ``size``) con la que ``text`` entra."""
    while size > min_size:
        font = fonts.load(size, bold=bold)
        if width(draw, text, font) <= max_width:
            return font
        size -= 2
    return fonts.load(min_size, bold=bold)


def ellipsize(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int
) -> str:
    """Recorta ``text`` con "…" hasta que entre en ``max_width``."""
    if width(draw, text, font) <= max_width:
        return text
    while text and width(draw, text + "…", font) > max_width:
        text = text[:-1]
    return text.rstrip() + "…"
