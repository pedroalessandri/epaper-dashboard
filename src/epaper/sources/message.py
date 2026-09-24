"""Modo de pantalla y mensaje para la familia.

Estado en ``message.json`` (raíz del repo, o ``$EPAPER_MESSAGE``): qué se
muestra (``dashboard`` o ``message``) y el texto del mensaje. Lo escribe el
panel web y lo lee ``main`` en cada refresco.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from epaper.storage import atomic_write_text

log = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PATH = _REPO_ROOT / "message.json"

DASHBOARD = "dashboard"
MESSAGE = "message"
MAX_TEXT = 400


@dataclass(frozen=True)
class ScreenState:
    mode: str = DASHBOARD
    text: str = ""

    @property
    def shows_message(self) -> bool:
        """Un mensaje vacío nunca deja la pantalla en blanco: cae al dashboard."""
        return self.mode == MESSAGE and bool(self.text.strip())


class MessageStore:
    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path or os.environ.get("EPAPER_MESSAGE") or DEFAULT_PATH)
        self._lock = threading.Lock()

    def get(self) -> ScreenState:
        """Nunca lanza: ante un archivo roto o ausente, dashboard sin mensaje."""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            mode = data.get("mode") if data.get("mode") in (DASHBOARD, MESSAGE) else DASHBOARD
            return ScreenState(mode=mode, text=str(data.get("text", "")))
        except FileNotFoundError:
            return ScreenState()
        except Exception as exc:
            log.error("No se pudo leer %s (%s: %s)", self.path, type(exc).__name__, exc)
            return ScreenState()

    def show_message(self, text: str) -> ScreenState:
        return self._update(mode=MESSAGE, text=_clean(text))

    def save_text(self, text: str) -> ScreenState:
        return self._update(text=_clean(text))

    def show_dashboard(self) -> ScreenState:
        return self._update(mode=DASHBOARD)

    def _update(self, **changes) -> ScreenState:
        with self._lock:
            state = replace(self.get(), **changes)
            atomic_write_text(self.path, json.dumps(asdict(state), ensure_ascii=False, indent=1))
            return state


def _clean(text: str) -> str:
    # Se respetan los saltos de línea; se normalizan los finales de línea y los
    # espacios sobrantes de cada renglón.
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    return "\n".join(lines).strip()[:MAX_TEXT]
