"""ASGI entrypoint: builds the app from env vars (used by uvicorn)."""
import os
from pathlib import Path

from .app import create_app

_base = Path(os.environ.get("CAPEVOLVE_BASE_DIR", ".capevolve"))
_static = os.environ.get("CAPEVOLVE_STATIC_DIR")
app = create_app(_base, static_dir=Path(_static) if _static else None)
