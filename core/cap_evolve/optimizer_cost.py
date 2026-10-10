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

import glob
import json
import os
import re
from datetime import datetime
from pathlib import Path

from .pricing import token_cost


NO_TRANSCRIPT_MSG = (
    "no optimizer transcript found: optimizer cost is NOT metered (recorded $0 is unknown, not "
    "free) and max_optimizer_usd is inert. A subagent optimizer: run `python -m "
    "cap_evolve.optimizer_cost register --run-dir R --transcript "
    "~/.claude/projects/<launch-dir-slug>/<session-id>/subagents/agent-<id>.jsonl` or set "
    "CAPEVOLVE_OPTIMIZER_TRANSCRIPTS.")


def mode() -> str:
    m = os.environ.get("CAPEVOLVE_OPTIMIZER_COST", "window").strip().lower()
    return m if m in ("off", "window", "session") else "window"


def _slug(d) -> str:
    """Claude Code names a project dir after the session's launch cwd, every non-alphanumeric
    character replaced by ``-`` (``/a/b_c`` -> ``-a-b-c``)."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(Path(d).resolve()))


def _entries(run_dir) -> list[str]:
    try:
        v = json.loads((Path(run_dir.root) / "optimizer_sessions.json").read_text(encoding="utf-8"))
        return [str(x) for x in v] if isinstance(v, list) else []
    except (OSError, ValueError):
        return []


def _is_path(e: str) -> bool:
    return "/" in e or "\\" in e or e.endswith(".jsonl") or e.startswith("~")


def explicit_transcripts(run_dir) -> list[Path]:
    """Transcripts named explicitly: ``CAPEVOLVE_OPTIMIZER_TRANSCRIPTS`` (comma-separated paths or
    globs) plus the path entries of the run dir's ``optimizer_sessions.json``. A SUBAGENT optimizer
    must be metered this way: its tokens live in its own ``agent-*.jsonl``, and scoping by the
    lead's session id would bill every sibling agent of that session to this run."""
    pats = [x.strip() for x in os.environ.get("CAPEVOLVE_OPTIMIZER_TRANSCRIPTS", "").split(",")
            if x.strip()] + [e for e in _entries(run_dir) if _is_path(e)]
    out: set[Path] = set()
    for pat in pats:
        out.update(Path(h) for h in glob.glob(os.path.expanduser(pat), recursive=True)
                   if os.path.isfile(h))
    return sorted(out)


def _logs(dirs: list[Path], sids: list[str] | None) -> list[Path]:
    """Session logs under the cwd slug dirs; only ``sids`` when given (else EVERY session).

    A session id is unique, so for known ids the search also walks the ancestors of each dir (and
    ``CLAUDE_PROJECT_DIR`` / ``CAPEVOLVE_LAUNCH_DIR``): the log lives under the slug of the
    session's LAUNCH cwd, usually above the run dir. Unscoped reads stay inside ``dirs``."""
    root = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "projects"
    cand = [Path(d).resolve() for d in dirs]
    if sids is not None:
        cand += [a for d in cand for a in d.parents if len(a.parts) > 1]
        cand += [Path(os.environ[k]) for k in ("CLAUDE_PROJECT_DIR", "CAPEVOLVE_LAUNCH_DIR")
                 if os.environ.get(k)]
    out: list[Path] = []
    for d in dict.fromkeys(cand):
        proj = root / _slug(d)
        for sid in (sids if sids is not None else [None]):
            out += proj.glob(f"{sid or '*'}.jsonl")
            out += proj.glob(f"{sid or '*'}/subagents/*.jsonl")
    return sorted(set(out))


def _session_ids(run_dir) -> list[str] | None:
    """Session ids billed to this run: the current one (``CLAUDE_CODE_SESSION_ID``) added to
    the list recorded in the run dir. ``None`` = unknown, caller falls back to time-window.
    Not added when transcripts are registered explicitly (those replace whole-session scope)."""
    entries = _entries(run_dir)
    sids = [e for e in entries if not _is_path(e)]
    cur = os.environ.get("CLAUDE_CODE_SESSION_ID") or os.environ.get("CLAUDE_SESSION_ID")
    if cur and cur not in sids and not explicit_transcripts(run_dir):
        sids.append(cur)
        _write(Path(run_dir.root) / "optimizer_sessions.json", entries + [cur])
    return sids or None


def register(run_dir, transcript: str) -> None:
    """Bill ``transcript`` (a file or glob) to this run; idempotent."""
    t = os.path.expanduser(transcript)
    if not any(c in t for c in "*?["):
        t = str(Path(t).resolve())
    entries = _entries(run_dir)
    if t not in entries:
        _write(Path(run_dir.root) / "optimizer_sessions.json", entries + [t])


def _write(path: Path, obj) -> None:
    try:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(obj), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass


def _ts(s) -> float | None:
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def harvest(run_dir, dirs: list[Path], since: float, *, record: bool = True) -> dict | None:
    """New optimizer spend since ``since`` (epoch s), or ``None`` when no session log exists.

    Returns ``{usd, tokens, unpriced_tokens, models, scoped}`` (``scoped`` False = no session
    id known, so EVERY session in the dir was read — a heuristic); ``usd`` covers priced models only, so
    an unpriced model shows up as ``unpriced_tokens`` rather than as a silent $0.
    ``record=False`` reads without marking messages as counted (dry run).
    """
    explicit = explicit_transcripts(run_dir)
    sids = _session_ids(run_dir)
    # explicit transcripts alone never fall back to the unscoped "every session in dir" read
    logs = sorted(set(explicit) | (set() if explicit and sids is None else set(_logs(dirs, sids))))
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
        _write(seen_path, sorted(seen | set(by_msg)))
    return {"usd": round(usd, 6), "tokens": tokens, "unpriced_tokens": unpriced, "models": models,
            "scoped": sids is not None or bool(explicit), "transcripts": len(logs)}


def main(argv=None) -> int:
    import argparse

    from .rundir import RunDir
    ap = argparse.ArgumentParser(description="Optimizer-cost helpers")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("register", help="bill a transcript (file or glob) to the run")
    r.add_argument("--run-dir", required=True)
    r.add_argument("--transcript", required=True)
    a = ap.parse_args(argv)
    register(RunDir.open(Path(a.run_dir)), a.transcript)
    print(json.dumps({"registered": a.transcript}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
