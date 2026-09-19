"""Carga de tipografías.

En 1 bit no hay antialiasing útil: el texto chico con bordes suavizados queda
sucio. Por eso se usa DejaVu (bien hinteada) y no se baja de ~16 px.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

log = logging.getLogger(__name__)

# DejaVu viene con Raspberry Pi OS (paquete fonts-dejavu-core) y con la
# mayoría de las distros de escritorio.
_CANDIDATES = {
    "regular": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/Library/Fonts/DejaVuSans.ttf",
    ],
    "bold": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/Library/Fonts/DejaVuSans-Bold.ttf",
    ],
}

# Tamaño mínimo legible en el panel. Por debajo de esto el texto se ensucia.
MIN_SIZE = 14


def _find(style: str) -> str | None:
    for path in _CANDIDATES[style]:
        if Path(path).is_file():
            return path
    return None


@lru_cache(maxsize=64)
def load(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Devuelve una fuente del tamaño pedido.

    Si DejaVu no está instalada, cae a la fuente por defecto de Pillow, que es
    fea pero no rompe el render.
    """
    if size < MIN_SIZE:
        log.warning("Tamaño %d px por debajo del mínimo legible (%d)", size, MIN_SIZE)
    path = _find("bold" if bold else "regular")
    if path is None:
        log.warning(
            "DejaVu no encontrada; usando la fuente por defecto de Pillow. "
            "Instalar con: sudo apt install -y fonts-dejavu-core"
        )
        return ImageFont.load_default()
    return ImageFont.truetype(path, size)
