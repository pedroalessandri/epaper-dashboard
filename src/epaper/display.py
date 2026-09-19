"""Capa de salida del dashboard.

Expone una interfaz única (`Display.show(image)`) con dos backends:

- ``mock``:      guarda la imagen en ``out/preview.png``. Corre en cualquier
                 máquina, sin hardware. Es el modo de desarrollo.
- ``waveshare``: manda la imagen al panel e-paper real vía SPI.

El backend se elige con la variable de entorno ``EPAPER_BACKEND``.
Por defecto es ``mock``, a propósito: si alguien corre esto en la notebook
sin querer, no pasa nada.

Reglas del panel que este módulo garantiza (ver CLAUDE.md):
  1. Siempre se llama a ``epd.sleep()``, incluso si el render falla.
  2. La imagen se normaliza a 1 bit, 800x480, antes de mandarla.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path

from PIL import Image

log = logging.getLogger(__name__)

# Resolución del panel Waveshare 7.5" V2. Fija.
WIDTH = 800
HEIGHT = 480

# Valores de píxel en modo "1": 255 es blanco (fondo), 0 es negro (tinta).
WHITE = 255
BLACK = 0

# Rutas por defecto, relativas a la raíz del repo.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_OUT_DIR = _REPO_ROOT / "out"


def new_canvas() -> Image.Image:
    """Devuelve un lienzo en blanco del tamaño del panel, en modo 1 bit."""
    return Image.new("1", (WIDTH, HEIGHT), WHITE)


def _normalize(image: Image.Image) -> Image.Image:
    """Lleva la imagen al formato exacto que espera el panel.

    El panel no tiene grises: cualquier cosa que no sea modo "1" se convierte,
    y si el tamaño no coincide se avisa fuerte en vez de deformar en silencio.
    """
    if image.size != (WIDTH, HEIGHT):
        raise ValueError(
            f"La imagen mide {image.size}, se esperaba ({WIDTH}, {HEIGHT})"
        )
    if image.mode != "1":
        log.warning("Imagen en modo %r, convirtiendo a 1 bit", image.mode)
        image = image.convert("1")
    return image


class Display(ABC):
    """Interfaz común a todos los backends de salida."""

    width = WIDTH
    height = HEIGHT

    @abstractmethod
    def show(self, image: Image.Image) -> None:
        """Muestra la imagen. Bloquea hasta terminar."""

    @abstractmethod
    def clear(self) -> None:
        """Deja la superficie en blanco."""

    def __enter__(self) -> "Display":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def close(self) -> None:
        """Libera el hardware. Por defecto no hace nada."""


class MockDisplay(Display):
    """Backend de desarrollo: escribe un PNG en vez de usar el panel."""

    def __init__(self, out_path: Path | str | None = None) -> None:
        if out_path is None:
            out_path = os.environ.get(
                "EPAPER_PREVIEW_PATH", _DEFAULT_OUT_DIR / "preview.png"
            )
        self.out_path = Path(out_path)

    def show(self, image: Image.Image) -> None:
        image = _normalize(image)
        self.out_path.parent.mkdir(parents=True, exist_ok=True)
        # Se guarda en modo "1": el PNG resultante es fiel a lo que vería
        # el panel, sin grises intermedios que engañen la vista.
        image.save(self.out_path)
        log.info("Preview escrito en %s", self.out_path)

    def clear(self) -> None:
        self.show(new_canvas())


class WaveshareDisplay(Display):
    """Backend real: panel Waveshare 7.5" V2 sobre el Driver HAT rev 2.3.

    La librería de Waveshare no se importa a nivel de módulo a propósito:
    así este archivo se puede importar en la notebook, donde ``spidev`` y
    ``gpiozero`` no están disponibles.
    """

    def __init__(self) -> None:
        self._epd = None

    def _get_epd(self):
        if self._epd is None:
            from waveshare_epd import epd7in5_V2  # import diferido

            self._epd = epd7in5_V2.EPD()
        return self._epd

    def show(self, image: Image.Image) -> None:
        image = _normalize(image)
        epd = self._get_epd()
        try:
            epd.init()
            epd.display(epd.getbuffer(image))
        finally:
            # Regla 1 de CLAUDE.md: el panel nunca queda energizado,
            # ni siquiera si display() levanta una excepción.
            self._sleep_quietly(epd)

    def clear(self) -> None:
        epd = self._get_epd()
        try:
            epd.init()
            epd.Clear()
        finally:
            self._sleep_quietly(epd)

    @staticmethod
    def _sleep_quietly(epd) -> None:
        """Duerme el panel sin dejar que un fallo acá tape el error original."""
        try:
            epd.sleep()
        except Exception:  # noqa: BLE001 - best effort
            log.exception("Falló epd.sleep(); el panel puede haber quedado activo")

    def close(self) -> None:
        if self._epd is None:
            return
        try:
            from waveshare_epd import epdconfig

            epdconfig.module_exit(cleanup=True)
        except Exception:  # noqa: BLE001 - best effort
            log.exception("Falló la limpieza del módulo de Waveshare")
        finally:
            self._epd = None


_BACKENDS = {
    "mock": MockDisplay,
    "waveshare": WaveshareDisplay,
}


def get_display(backend: str | None = None) -> Display:
    """Devuelve el backend configurado.

    Orden de precedencia: argumento explícito > ``EPAPER_BACKEND`` > ``mock``.
    """
    name = (backend or os.environ.get("EPAPER_BACKEND") or "mock").strip().lower()
    try:
        cls = _BACKENDS[name]
    except KeyError:
        raise ValueError(
            f"Backend desconocido: {name!r}. Opciones: {sorted(_BACKENDS)}"
        ) from None
    log.info("Backend de display: %s", name)
    return cls()
