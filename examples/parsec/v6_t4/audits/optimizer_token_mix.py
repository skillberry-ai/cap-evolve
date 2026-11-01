#!/usr/bin/env python3
"""Token mix of the optimizer sessions (Global vs T-opt): cache-read, cache-write, output, fresh input.

Reads the Claude Code session transcripts under $CLAUDE_CONFIG_DIR/projects (default ~/.claude/projects)
for each candidate work directory. A message is logged once per content block with cumulative usage, so
each message id is counted once, at its last record. Only the transcripts still on disk are covered
(Global: 6 sessions; T-opt: 12 of its 59), so these are shares, not totals; the totals are in
cost_table.json.

Why it matters: cache reads are billed at 0.1x the input price but counted at full weight in a token
total, so a token total is not an effort measure across arms.

Usage:  python3 optimizer_token_mix.py [--t-opt-glob '<repo>/.capevolve/v6_t2_e1_*/run_*/work/cand_*']
"""
import argparse
import glob
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C  # noqa: E402

ROOT = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "projects"


def sessions(work_dirs):
    slugs = {"-" + str(Path(w).resolve()).strip("/").replace("/", "-").replace("_", "-").replace(".", "-") for w in work_dirs}
    out = []
    for proj in ROOT.iterdir():
        if proj.name not in slugs:
            continue
        for f in proj.glob("*.jsonl"):
            last = {}
            for line in f.read_text(errors="ignore").splitlines():
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                m = o.get("message") if o.get("type") == "assistant" else None
                if isinstance(m, dict) and isinstance(m.get("usage"), dict) and m.get("id") and m.get("model") != "<synthetic>":
                    last[m["id"]] = m["usage"]
            if last:
                out.append(list(last.values()))
    return out


def summarize(name, sess):
    t = dict.fromkeys(("in", "out", "cr", "cw"), 0)
    turns = 0
    for us in sess:
        for u in us:
            t["in"] += u.get("input_tokens") or 0
            t["out"] += u.get("output_tokens") or 0
            t["cr"] += u.get("cache_read_input_tokens") or 0
            t["cw"] += u.get("cache_creation_input_tokens") or 0
            turns += 1
    total = sum(t.values())
    print(f"{name:7s} sessions {len(sess):2d} turns {turns:5d} | cache-read {t['cr'] / total:.1%}  cache-write {t['cw'] / total:.1%}  "
          f"output {t['out'] / total:.2%}  fresh input {t['in'] / total:.2%} | tokens/turn {total / turns / 1e3:.0f}k")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--t-opt-glob", default=str(C.REPO / ".capevolve/v6_t2_e1_*/run_*/work/cand_*"))
    a = ap.parse_args()
    summarize("Global", sessions(glob.glob(str(C.G2_RUN / "work" / "cand_*"))))
    summarize("T-opt", sessions(glob.glob(a.t_opt_glob)))
