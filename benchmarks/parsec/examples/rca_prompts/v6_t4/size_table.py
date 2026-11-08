#!/usr/bin/env python3
"""Table 3: skill-bundle size and edit size in words, per arm (same rows as Tables 1 and 2).

Words are whitespace-split tokens over the 8 skill files (merge logs and optimizer notes excluded).
Added/removed come from a word-level difflib diff of each file against the Seed, summed over files.
T-opt has 34 private bundles: its row sums the 34 diffs (each counted once), and also gives the
per-champion median and range.
"""
import difflib, json, statistics as st, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "examples/parsec/v6_t2"))
import scaffold_projects as S  # noqa: E402

FILES = ["orchestrator.md", "shared_context.md", "aap2_agent.md", "babylon_agent.md",
         "cost_agent.md", "icinga_agent.md", "ocpv_agent.md", "security_agent.md"]
SEED = ROOT / "results/v6_t4_e1/merge_inputs/seed"
G = Path("/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-ps-worktrees/"
         "parsec-intake_v6/.capevolve/v6_g2_e1/run_g2_e1/candidates/cand_0005")


def measure(d: Path) -> dict:
    out = {"words": 0, "added": 0, "removed": 0, "files_changed": 0, "per_file": {}}
    for f in FILES:
        a, b = (SEED / f).read_text().split(), (d / f).read_text().split()
        add = rem = 0
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
            if op in ("replace", "delete"):
                rem += i2 - i1
            if op in ("replace", "insert"):
                add += j2 - j1
        out["words"] += len(b); out["added"] += add; out["removed"] += rem
        out["files_changed"] += a != b
        out["per_file"][f] = {"words": len(b), "added": add, "removed": rem}
    return out


def champion(task: str) -> Path:
    run = ROOT / ".capevolve" / f"v6_t2_e1_{task}" / f"run_{task}"
    return run / "candidates" / json.loads((run / "state.json").read_text())["best_id"]


seed_words = sum(len((SEED / f).read_text().split()) for f in FILES)
rows = {"Seed": {"words": seed_words, "added": 0, "removed": 0, "files_changed": 0}}
champs = {t: measure(champion(t)) for t in S.TASK_IDS}
rows["T-opt"] = {"added": sum(c["added"] for c in champs.values()),
                 "removed": sum(c["removed"] for c in champs.values()),
                 "files_changed": len({f for c in champs.values() for f, v in c["per_file"].items() if v["added"] or v["removed"]}),
                 "per_champion": {k: {"median": st.median(c[k] for c in champs.values()),
                                      "min": min(c[k] for c in champs.values()),
                                      "max": max(c[k] for c in champs.values())}
                                  for k in ("added", "removed", "files_changed", "words")}}
for name, d in (("T-mrg · merge by order", "m1_order"), ("T-mrg · smart merge", "m3_smart"),
                ("T-mrg · non-conflicting hunks", "m2_nonconflict")):
    rows[name] = measure(ROOT / "results/v6_t4_e1" / d)
rows["Global"] = measure(G)
(ROOT / "results/v6_t4_e1/size_table.json").write_text(json.dumps(
    {"seed_words": seed_words, "rows": rows, "t_opt_champions": champs, "definitions": __doc__}, indent=1))
for k, r in rows.items():
    w = r.get("words")
    print(f"{k:32s} words {w or '-':>6} added {r['added']:6d} removed {r['removed']:4d} files {r['files_changed']}"
          + (f"  growth {w / seed_words - 1:+.0%}" if w else "") + (f"  per-champ {r['per_champion']}" if "per_champion" in r else ""))
