"""Control de la cadencia del panel.

Waveshare recomienda al menos 180 s entre refrescos. Este módulo es la única
fuente de verdad de cuándo fue el último: ``main`` lo marca después de cada
refresco real y lo consulta antes de hacer otro; el panel web lo usa para
decidir si refresca ya o agenda el refresco para más tarde.

La marca guarda además una firma de la última imagen enviada: si la nueva es
idéntica (un mensaje fijo), no se refresca, salvo una vez por día para que el
panel no retenga la imagen (regla 3 de CLAUDE.md).
"""

from __future__ import annotations

import os
import time
from pathlib import Path

MIN_INTERVAL_S = 180
MAX_UNCHANGED_S = 24 * 3600

_REPO_ROOT = Path(__file__).resolve().parents[2]
STAMP_PATH = Path(os.environ.get("EPAPER_REFRESH_STAMP") or _REPO_ROOT / "out" / "last_refresh")


def seconds_since_last() -> float | None:
    try:
        return time.time() - STAMP_PATH.stat().st_mtime
    except FileNotFoundError:
        return None


def seconds_until_allowed() -> float:
    """0 si ya se puede refrescar; si no, cuánto falta."""
    since = seconds_since_last()
    if since is None or since < 0:  # sin marca, o reloj que saltó para atrás
        return 0.0
    return max(0.0, MIN_INTERVAL_S - since)


def last_signature() -> str:
    try:
        return STAMP_PATH.read_text().strip()
    except OSError:
        return ""


def is_redundant(signature: str) -> bool:
    """¿La imagen es igual a la que ya está en el panel, y es reciente?"""
    since = seconds_since_last()
    return (
        bool(signature)
        and signature == last_signature()
        and since is not None
        and 0 <= since < MAX_UNCHANGED_S
    )


def mark(signature: str = "") -> None:
    STAMP_PATH.parent.mkdir(parents=True, exist_ok=True)
    # No hace falta fsync: si se pierde, lo peor es un refresco de más.
    STAMP_PATH.write_text(signature)
