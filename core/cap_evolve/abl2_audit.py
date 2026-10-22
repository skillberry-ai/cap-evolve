"""ABL-V2 audit helpers: best-val candidate (B2) and per-session truncation report (B1)."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def best_val_candidate(run_dir) -> dict:
    """The evaluated candidate (tag cand_*) with the max val mean over all evaluate events; ties -> earliest.
    ``run_dir`` is a run directory (with events.jsonl) or the events file itself."""
    p = Path(run_dir if isinstance(run_dir, (str, Path)) else run_dir.root)
    ev = p if p.is_file() else p / "events.jsonl"
    best = {"candidate": None, "val": None}
    if not ev.is_file():
        return best
    for ln in ev.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(ln)
        except ValueError:
            continue
        tag = str(e.get("tag") or "")
        if e.get("kind") != "evaluate" or not tag.startswith("cand_") or e.get("reward") is None \
                or e.get("subset") or e.get("split", "val") != "val":
            continue
        if best["val"] is None or e["reward"] > best["val"]:     # strict > keeps the earliest on ties
            best = {"candidate": tag, "val": e["reward"]}
    return best


def _last_assistant(path: Path):
    last, n = None, 0
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            e = json.loads(ln)
        except ValueError:
            continue
        m = e.get("message") if isinstance(e, dict) else None
        if e.get("type") == "assistant" and isinstance(m, dict):
            n += 1
            last = m.get("stop_reason")
    return last, n


def truncation_report(root) -> dict:
    """Sessions under ``<arm dir>/claude_cfg/projects/**/*.jsonl` (or a claude_cfg dir); a session is cut
    when its last assistant message has stop_reason != 'end_turn'."""
    root = Path(root)
    base = root / "claude_cfg" if (root / "claude_cfg").is_dir() else root
    proj = base / "projects" if (base / "projects").is_dir() else base
    per = []
    for f in sorted(proj.rglob("*.jsonl")):
        last, n = _last_assistant(f)
        if n:
            per.append({"file": str(f.relative_to(proj)), "last_stop_reason": last, "n_assistant_msgs": n})
    return {"session_count": len(per), "cut_count": sum(1 for s in per if s["last_stop_reason"] != "end_turn"),
            "per_session": per}


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if len(a) == 2 and a[0] == "trunc":
        r = truncation_report(a[1])
        print(json.dumps({k: r[k] for k in ("session_count", "cut_count")}))
        for s in r["per_session"]:
            print(f"{s['last_stop_reason']!s:14} {s['n_assistant_msgs']:4d}  {s['file']}")
        return 0
    if len(a) == 2 and a[0] == "bestval":
        print(json.dumps(best_val_candidate(a[1])))
        return 0
    print("usage: python -m cap_evolve.abl2_audit trunc|bestval <dir>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
