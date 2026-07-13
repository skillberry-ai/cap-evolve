"""ASGI entrypoint: builds the app from env vars (used by uvicorn)."""
import os
from pathlib import Path

from .app import create_app
from .server import resolve_static_dir

_base = Path(os.environ.get("CAPEVOLVE_BASE_DIR", ".capevolve"))
_static = os.environ.get("CAPEVOLVE_STATIC_DIR")
if _static is None:
    _auto = resolve_static_dir()
    if _auto is not None:
        _static = str(_auto)
app = create_app(_base, static_dir=Path(_static) if _static else None)
