"""Regenerate $AW_EVAL/progress/PROGRESS.md, a one-table view of all trials (README: Running).

    python status.py            # once
    python status.py --every 300   # loop
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from awpaths import CAPE_RUN as RUN, PROGRESS, RUNS  # noqa: E402


def last_line(p: Path) -> str:
    try:
        lines = [l for l in p.read_text().splitlines() if l.strip()]
        return lines[-1] if lines else ""
    except FileNotFoundError:
        return ""


def cape_row() -> list[str]:
    ev = RUN / "events.jsonl"
    if not ev.is_file():
        return ["cape-hc", "not started", "0%", "", "0", "", ""]
    events = [json.loads(l) for l in ev.read_text().splitlines() if l.strip()]
    state = json.loads((RUN / "state.json").read_text()) if (RUN / "state.json").is_file() else {}
    spent = state.get("spent", {})
    steps = [e for e in events if e.get("kind") == "step"]
    base = next((e for e in events if e.get("kind") == "baseline"), None)
    fin = next((e for e in events if e.get("kind") == "finalize"), None)
    phase = "finalized" if fin else (f"iteration {len(steps) + 1}/6" if base else "baseline")
    pct = 100 if fin else round(100 * (1 + len(steps)) / 7 * (1 if base else 0.5))
    last = steps[-1] if steps else base
    detail = ""
    if last:
        detail = (f"{last.get('candidate', 'baseline')} {'ACCEPT' if last.get('accept') else ('' if not steps else 'reject')} "
                  f"val={last.get('val')}").strip()
    detail += f" · {last_line(PROGRESS / 'cape_hc.log').split(' | ')[-1]}"
    best = spent.get("best_val", base.get("val") if base else "")
    return ["cape-hc", phase, f"{pct}%", detail, str(spent.get("metric_calls", 0)),
            f"${spent.get('optimizer_usd', 0):.2f}, {spent.get('optimizer_tokens', 0):,} tok", f"best val {best}"]


def altk_row() -> list[str]:
    a = RUNS / "altk"
    mined = json.loads((a / "mined.json").read_text()) if (a / "mined.json").is_file() else {}
    sel = json.loads((a / "dose_selection.json").read_text()) if (a / "dose_selection.json").is_file() else None
    usage = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0}
    if (a / "optimizer_usage.jsonl").is_file():
        for l in (a / "optimizer_usage.jsonl").read_text().splitlines():
            r = json.loads(l)
            usage["calls"] += 1
            usage["prompt_tokens"] += int(r.get("prompt_tokens") or 0)
            usage["completion_tokens"] += int(r.get("completion_tokens") or 0)
    phase = "done" if sel else ("dose selection" if (a / "cand_ret_dev").is_dir() else
                                ("mining" if mined else "waiting for cape-hc baseline"))
    pct = 100 if sel else round(60 * len(mined) / 90)
    rollouts = 90 + (114 if sel else 0)
    return ["altk", phase, f"{pct}%", last_line(PROGRESS / "altk.log").split(" | ")[-1], str(rollouts),
            f"{usage['calls']} calls, {usage['prompt_tokens']:,}/{usage['completion_tokens']:,} in/out tok",
            f"chosen {sel['chosen']}" if sel else ""]


def final_row() -> list[str]:
    st = RUNS / "final" / "status.json"
    if not st.is_file():
        return ["final", "not started", "0%", "", "0", "-", ""]
    s = json.loads(st.read_text())
    return ["final", s.get("phase", ""), f"{round(100 * s.get('done', 0) / max(1, s.get('total', 1)))}%",
            last_line(PROGRESS / "final.log").split(" | ")[-1], str(s.get("done", 0)), "-", s.get("eta", "")]


def render() -> str:
    head = ["trial", "phase", "% done", "last event", "rollouts used", "optimizer usage", "note"]
    rows = [cape_row(), altk_row(), final_row()]
    out = [f"# AppWorld smoke test progress — {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}", "",
           "| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(c.replace("|", "/") for c in r) + " |" for r in rows]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    every = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[1] == "--every" else 0
    while True:
        (PROGRESS / "PROGRESS.md").write_text(render())
        if not every:
            break
        time.sleep(every)
