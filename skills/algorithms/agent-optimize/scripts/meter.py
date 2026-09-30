"""meter — the hosted optimizer's running token usage, read mid-session (issue #610).

What claude-code actually exposes, checked against real runs (Claude Code 2.1.x):

  * ``--output-format stream-json`` (``host/transcript.jsonl``): every ``assistant`` line
    carries ``message.usage``, but only ``input_tokens`` with ``output_tokens: 0`` and NO
    cache fields — it is the message-start snapshot. Summing it gave 43,095 tokens for a
    session whose ``result`` billed 16,745,016. Unusable.
  * No running USD anywhere in the stream: ``total_cost_usd`` exists only on the terminal
    ``result`` line (and the session log's one ``cost-state`` line, written at exit).
  * Claude Code's own session log, ``~/.claude/projects/<cwd-slug>/<session_id>.jsonl`` (plus
    ``<session_id>/subagents/*.jsonl``), carries each message's FULL usage as it lands.
    Summed per message id it matched that ``result.usage`` exactly (input 43,095, output
    97,496, cache_read 15,503,192, cache_creation 1,101,233).

So tokens are metered here, at each checkpoint, from the session log. USD is not knowable
until the session ends; ``attribute_usd`` spreads the session's real ``total_cost_usd`` over
its checkpoints afterwards (host.py calls it).
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

_FIELDS = ("input_tokens", "output_tokens", "cache_read_input_tokens",
           "cache_creation_input_tokens")
#: Anthropic's per-category price multipliers relative to base input (output 5x, 5-minute
#: cache write 1.25x, cache read 0.1x). Only used to SPLIT a real total, never to price one.
#: Checked: these weights reproduce run v17's $7.349974 exactly at claude-sonnet-5's $2/MTok.
# ponytail: one weight set for every model; a session mixing models with different ratios
# (or 1h cache writes at 2x) splits approximately. Per-model weights if that ever matters.
_WEIGHTS = (1.0, 5.0, 0.1, 1.25)


def _session_id(run_dir: Path) -> str | None:
    try:
        with (run_dir / "host" / "transcript.jsonl").open(encoding="utf-8") as f:
            for line in f:
                try:
                    sid = json.loads(line).get("session_id")
                except (ValueError, AttributeError):
                    continue
                if sid:
                    return str(sid)
    except OSError:
        pass
    return None


def _session_logs(sid: str) -> list[Path]:
    root = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "projects"
    mains = sorted(root.glob(f"*/{sid}.jsonl"))
    if not mains:
        return []
    return [mains[0], *sorted(mains[0].with_suffix("").glob("subagents/*.jsonl"))]


def usage(run_dir: Path) -> dict | None:
    """Cumulative usage of the host's CURRENT claude-code session, or None when there is
    none to read (conversational mode, another agent CLI, or no session log on this box)."""
    sid = _session_id(Path(run_dir))
    logs = _session_logs(sid) if sid else []
    if not logs:
        return None
    by_msg: dict[str, dict] = {}
    start = None
    for path in logs:
        with path.open(encoding="utf-8") as f:
            for n, line in enumerate(f):
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                if start is None and o.get("timestamp"):
                    start = o["timestamp"]
                msg = o.get("message") if o.get("type") == "assistant" else None
                if isinstance(msg, dict) and isinstance(msg.get("usage"), dict):
                    # A message is logged once per content block; the last copy is final.
                    by_msg[msg.get("id") or f"{path.name}:{n}"] = msg["usage"]
    tokens, units = 0, 0.0
    for u in by_msg.values():
        vals = [int(u.get(k) or 0) for k in _FIELDS]
        tokens += sum(vals)
        units += sum(v * w for v, w in zip(vals, _WEIGHTS))
    try:
        started = datetime.fromisoformat(str(start).replace("Z", "+00:00")).timestamp()
    except ValueError:
        started = None
    return {"session": sid, "tokens": tokens, "units": units, "started": started}


def _checkpoints(run_dir: Path, sid: str) -> list[dict]:
    out = []
    try:
        with (Path(run_dir) / "events.jsonl").open(encoding="utf-8") as f:
            for line in f:
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                m = ev.get("opt_meter")
                if isinstance(m, dict) and m.get("session") == sid:
                    out.append(ev)
    except OSError:
        pass
    return out


def checkpoint(run_dir: Path, now: float) -> dict | None:
    """The optimizer spend since this session's previous checkpoint (or its start).

    Returns ``{tokens, seconds, meter}``; ``meter`` goes on the decision event so the NEXT
    checkpoint diffs against it."""
    cur = usage(run_dir)
    if cur is None:
        return None
    prev = _checkpoints(run_dir, cur["session"])
    last = prev[-1]["opt_meter"] if prev else {"tokens": 0, "units": 0.0,
                                               "t": cur["started"] or now}
    return {"tokens": max(0, cur["tokens"] - int(last.get("tokens") or 0)),
            "seconds": max(0.0, now - float(last.get("t") or now)),
            "meter": {"session": cur["session"], "tokens": cur["tokens"],
                      "units": cur["units"], "t": now}}


def attribute_usd(run_dir: Path, total_usd: float) -> dict | None:
    """Split a finished session's real ``total_cost_usd`` over its checkpoints by each one's
    price-weighted token delta. ``residual_usd`` is the spend after the last checkpoint (and
    anything the session log never showed, e.g. compaction calls), so the parts sum to the
    total."""
    cur = usage(run_dir)
    if cur is None or not total_usd or not cur["units"]:
        return None
    by_candidate: dict[str, float] = {}
    prev = 0.0
    for ev in _checkpoints(run_dir, cur["session"]):
        u = float(ev["opt_meter"].get("units") or 0.0)
        cid = str(ev.get("candidate"))
        by_candidate[cid] = round(by_candidate.get(cid, 0.0)
                                  + total_usd * max(0.0, u - prev) / cur["units"], 6)
        prev = max(prev, u)
    return {"session": cur["session"], "by_candidate": by_candidate,
            "residual_usd": round(total_usd - sum(by_candidate.values()), 6)}
