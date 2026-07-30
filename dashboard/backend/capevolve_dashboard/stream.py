"""Server-Sent-Events helpers: format frames and tail events.jsonl by byte offset.

The tail itself lives in ``cap_evolve.eventstream`` (core, stdlib-only) so the SSE
route, ``cap-evolve run --follow`` and ``cap-evolve tail`` all read the run's event
log through the same code — the web view and the terminal can't disagree.
``read_new_events`` is re-exported here for the existing callers/tests.
"""
from __future__ import annotations

import json

from cap_evolve.eventstream import read_new_events  # noqa: F401 — re-export

__all__ = ["sse_format", "read_new_events"]


def sse_format(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
