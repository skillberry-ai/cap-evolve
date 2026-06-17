"""Thin shim: the dashboard builder lives in ``cap_evolve.dashboard`` (Wave 4).

The report skill imports this module so the reducer/renderers stay engine-owned
and unit-tested under ``core/tests`` while the skill keeps a stable import name.
"""

from __future__ import annotations

import _bootstrap  # noqa: F401

from cap_evolve.dashboard import (  # noqa: F401
    build_diffs,
    reduce_run,
    redact,
    render_ansi,
    render_html,
    write_dashboard,
)
