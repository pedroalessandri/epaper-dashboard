"""Control de la cadencia del panel.

Waveshare recomienda al menos 180 s entre refrescos. Este módulo es la única
fuente de verdad de cuándo fue el último: ``main`` lo marca después de cada
refresco real y lo consulta antes de hacer otro; el panel web lo usa para
decidir si refresca ya o agenda el refresco para más tarde.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

MIN_INTERVAL_S = 180

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


def mark() -> None:
    STAMP_PATH.parent.mkdir(parents=True, exist_ok=True)
    STAMP_PATH.touch()
