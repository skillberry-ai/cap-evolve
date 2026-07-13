"""ASGI entrypoint: builds the app from env vars (used by uvicorn)."""
import os
from pathlib import Path

from .app import create_app

_base = Path(os.environ.get("CAPEVOLVE_BASE_DIR", ".capevolve"))
_static = os.environ.get("CAPEVOLVE_STATIC_DIR")
if _static is None:
    # parents[0]=capevolve_dashboard, parents[1]=backend, parents[2]=dashboard.
    _auto = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if _auto.is_dir():
        _static = str(_auto)
app = create_app(_base, static_dir=Path(_static) if _static else None)
