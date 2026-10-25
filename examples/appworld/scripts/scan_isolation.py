"""Isolation scan after both searches (README: Isolation). Needs read access to root_full.

    python scan_isolation.py      # writes runs/isolation_scan.json

Greps the cape-hc run dir (optimizer workdirs, candidates, journals, rollouts), the claude-code
session transcripts of the optimizer (~/.claude/projects/*cape-hc*), and the ALTK store for:
test ids (test_normal + test_challenge), their canary strings, and the strings ``test_normal``,
``root_full``, ``answer.json``, ``ground_truth``. Counts are reported per pattern and location.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from awpaths import CAPE_NAME, CAPE_RUN, OPT_TRANSCRIPTS, ROOT_FULL, RUNS, read_split  # noqa: E402

LITERALS = ("test_normal", "root_full", "answer.json", "ground_truth")


def main() -> int:
    test_ids = read_split("test_normal") + read_split("test_challenge")
    canaries = []
    for t in test_ids:
        c = json.loads((ROOT_FULL / "data/tasks" / t / "specs.json").read_text()).get("canary_string", "")
        canaries.append(c.split(":")[-1] if c else "")
    id_re = re.compile("|".join(re.escape(t) for t in test_ids))
    can_re = re.compile("|".join(re.escape(c) for c in set(canaries) if c))
    locations = {
        "cape-hc run dir": CAPE_RUN,
        # optimizer transcripts written inside the namespace wrapper (README: Isolation)
        "optimizer transcripts (wrapper)": OPT_TRANSCRIPTS / CAPE_NAME,
        "altk store + outputs": RUNS / "altk",
    }
    claude_proj = Path.home() / ".claude/projects"
    tag = CAPE_NAME.replace("_", "-")
    transcripts = [p for p in claude_proj.glob("*") if tag in p.name or CAPE_NAME in p.name]
    out: dict = {"locations": {}, "transcript_dirs": [str(p) for p in transcripts]}
    for name, root in list(locations.items()) + [(f"claude transcripts {p.name}", p) for p in transcripts]:
        counts: Counter = Counter()
        files_hit: dict = {}
        if not root.exists():
            out["locations"][name] = {"missing": str(root)}
            continue
        for p in root.rglob("*"):
            if not p.is_file() or p.stat().st_size > 50_000_000:
                continue
            text = p.read_bytes().decode("utf-8", "ignore")
            hit = Counter()
            hit["test_id"] = len(id_re.findall(text))
            hit["canary"] = len(can_re.findall(text)) if can_re.pattern else 0
            for lit in LITERALS:
                hit[lit] = text.count(lit)
            hit = +hit
            if hit:
                counts.update(hit)
                files_hit[str(p.relative_to(root))] = dict(hit)
        out["locations"][name] = {"counts": dict(counts), "files": dict(list(files_hit.items())[:50]),
                                  "n_files_hit": len(files_hit)}
    # AppWorld 0.2.0 uses ONE canary string for every task in every split, so a canary hit only shows
    # that some task file was read; only a test id is evidence of test access (README: Isolation).
    out["canary_is_release_wide"] = len(set(canaries)) == 1
    out["test_data_breach"] = any(v.get("counts", {}).get("test_id") for v in out["locations"].values())
    out["breach"] = out["test_data_breach"] or (not out["canary_is_release_wide"] and any(
        v.get("counts", {}).get("canary") for v in out["locations"].values()))
    (RUNS / "isolation_scan.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: (v if k != "locations" else {n: x.get("counts", x) for n, x in v.items()}) for k, v in out.items()},
                     indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
