"""Optional per-run custom view — an algorithm-shipped UI mounted as an extra tab.

Data-driven, with NO per-algorithm branching in the dashboard: an algorithm may
drop a ``custom_view.json`` in its run dir declaring a view to embed:

    {"title": "Weakness graph", "url": "http://127.0.0.1:7878/"}

The dashboard reads it and mounts an iframe tab pointing at ``url`` (the algorithm's
own server, or any served bundle). Absent/invalid file -> ``{}`` (no extra tab), so
runs that ship no view are unaffected.
"""
from __future__ import annotations

import json
from pathlib import Path


def read_custom_view(run_dir: Path) -> dict:
    """Return ``{"title", "url"}`` if the run declares a valid custom view, else ``{}``.

    Tolerant: a missing file, invalid JSON, a non-object, or a missing/blank ``url``
    all yield ``{}`` so a malformed declaration can never break the dashboard.
    """
    f = Path(run_dir) / "custom_view.json"
    if not f.exists():
        return {}
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    url = data.get("url")
    if not isinstance(url, str) or not url.strip():
        return {}
    title = data.get("title")
    title = title.strip() if isinstance(title, str) and title.strip() else "Custom view"
    return {"title": title, "url": url.strip()}
