"""Server-Sent-Events helpers: format frames and tail events.jsonl by byte offset."""
from __future__ import annotations

import json
from pathlib import Path


def sse_format(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def read_new_events(path: Path, offset: int) -> tuple[list[dict], int]:
    """Return (new events, new byte offset). A partial trailing line (no newline)
    is left unconsumed so the next read picks it up once complete."""
    p = Path(path)
    if not p.exists():
        return [], offset
    if offset >= p.stat().st_size:
        return [], offset
    # Seek-and-read so each poll costs O(new bytes), not O(file size) — the stream
    # route calls this twice a second per client over a growing events.jsonl.
    with p.open("rb") as fh:
        fh.seek(offset)
        chunk = fh.read()
    last_nl = chunk.rfind(b"\n")
    if last_nl == -1:
        return [], offset  # only a partial line so far
    complete = chunk[: last_nl + 1]
    events = []
    for line in complete.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events, offset + last_nl + 1
