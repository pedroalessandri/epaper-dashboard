"""Escritura segura de archivos de estado.

La Pi se desenchufa sin apagar: un archivo que quedó solo en la caché del
kernel aparece vacío al volver. Todo lo que el dashboard o el panel web
persisten pasa por acá: se escribe a un temporal, se fuerza a disco y se
renombra encima del original, así siempre queda la versión vieja o la nueva
completa, nunca una a medias.
"""

from __future__ import annotations

import os
from pathlib import Path


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    tmp.replace(path)
    # fsync del directorio para que el rename también quede en disco.
    dir_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)
