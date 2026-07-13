"""ASGI entrypoint: builds the app from env vars (used by uvicorn)."""
import os
from pathlib import Path

from .app import create_app

_base = Path(os.environ.get("CAPEVOLVE_BASE_DIR", ".capevolve"))
_static = os.environ.get("CAPEVOLVE_STATIC_DIR")
if _static is None:
    # asgi.py(file) -> capevolve_dashboard[0] -> backend[1] -> dashboard[2].
    _auto = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if _auto.is_dir():
        _static = str(_auto)
app = create_app(_base, static_dir=Path(_static) if _static else None)
