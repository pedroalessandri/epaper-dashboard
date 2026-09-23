"""Interfaz común de los tiles.

Cada tile dibuja dentro de un rectángulo que le asigna el layout. Ningún tile
conoce sus coordenadas absolutas: eso vive en un solo lugar (``render.py``),
así mover un bloque es cambiar una línea.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from PIL import ImageDraw


@dataclass(frozen=True)
class Box:
    """Rectángulo donde un tile tiene permitido dibujar."""

    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    def inset(self, padding: int) -> "Box":
        """Devuelve el mismo rectángulo con margen interno."""
        return Box(
            self.x + padding,
            self.y + padding,
            self.width - 2 * padding,
            self.height - 2 * padding,
        )


class Tile(ABC):
    """Un bloque del dashboard."""

    #: nombre con el que se referencia desde config.yaml
    name: str = "tile"

    @abstractmethod
    def draw(self, draw: ImageDraw.ImageDraw, box: Box, ctx: dict[str, Any]) -> None:
        """Dibuja el tile dentro de ``box``.

        ``ctx`` trae los datos ya resueltos (clima, tareas, hora). Un tile no
        hace llamadas de red: si el dato no está, dibuja un estado degradado.
        """
