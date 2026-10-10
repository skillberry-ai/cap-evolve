"""Optimizer-cost metering for conversational (agent-mode) runs.

``meter.py`` only reads the session of the headless ``host.py`` driver. A conversational run
has no such transcript, but Claude Code logs every message with full usage to
``~/.claude/projects/<cwd-slug>/<session>.jsonl`` (+ ``subagents/``). ``harvest`` sums the
messages not yet seen, prices them at list price (``pricing.token_cost``) and returns the
delta; the caller feeds it to ``RunDir.update_spent``. Idempotent: counted message ids live in
``<run>/optimizer_cost_seen.json``, so re-running a commit never double-charges.

Modes (``CAPEVOLVE_OPTIMIZER_COST``): ``window`` (default) = messages since the previous
decision; ``session`` = everything since the run began; ``off`` = legacy (no metering).
The log format is a Claude Code internal: anything unreadable yields ``None`` (metering
unavailable), never an exception.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

from .pricing import token_cost


def mode() -> str:
    m = os.environ.get("CAPEVOLVE_OPTIMIZER_COST", "window").strip().lower()
    return m if m in ("off", "window", "session") else "window"


def _logs(dirs: list[Path]) -> list[Path]:
    root = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "projects"
    out: list[Path] = []
    for d in dirs:
        proj = root / re.sub(r"[^A-Za-z0-9]", "-", str(Path(d).resolve()))
        out += proj.glob("*.jsonl")
        out += proj.glob("*/subagents/*.jsonl")
    return sorted(set(out))


def _ts(s) -> float | None:
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def harvest(run_dir, dirs: list[Path], since: float, *, record: bool = True) -> dict | None:
    """New optimizer spend since ``since`` (epoch s), or ``None`` when no session log exists.

    Returns ``{usd, tokens, unpriced_tokens, models}``; ``usd`` covers priced models only, so
    an unpriced model shows up as ``unpriced_tokens`` rather than as a silent $0.
    ``record=False`` reads without marking messages as counted (dry run).
    """
    logs = _logs(dirs)
    if not logs:
        return None
    seen_path = Path(run_dir.root) / "optimizer_cost_seen.json"
    try:
        seen = set(json.loads(seen_path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        seen = set()
    by_msg: dict[str, dict] = {}
    for path in logs:
        try:
            with path.open(encoding="utf-8") as f:
                for line in f:
                    try:
                        o = json.loads(line)
                    except ValueError:
                        continue
                    msg = o.get("message") if o.get("type") == "assistant" else None
                    if not (isinstance(msg, dict) and isinstance(msg.get("usage"), dict)
                            and msg.get("id")):
                        continue
                    t = _ts(o.get("timestamp"))
                    if t is not None and t >= since and msg["id"] not in seen:
                        by_msg[msg["id"]] = msg  # logged once per content block; last is final
        except OSError:
            continue
    usd, tokens, unpriced, models = 0.0, 0, 0, {}
    for msg in by_msg.values():
        u = msg["usage"]
        v = [int(u.get(k) or 0) for k in ("input_tokens", "output_tokens",
                                          "cache_read_input_tokens", "cache_creation_input_tokens")]
        model = str(msg.get("model") or "")
        if model == "<synthetic>":
            continue
        c = token_cost(model, *v)
        tokens += sum(v)
        models[model] = models.get(model, 0) + sum(v)
        if c is None:
            unpriced += sum(v)
        else:
            usd += c
    if record:
        try:
            seen_path.write_text(json.dumps(sorted(seen | set(by_msg))), encoding="utf-8")
        except OSError:
            pass
    return {"usd": round(usd, 6), "tokens": tokens, "unpriced_tokens": unpriced, "models": models}
