#!/usr/bin/env python3
"""Table 4: the AAP2 Rule 4 running example ("don't re-fetch job data") across all arms.

For each arm's aap2_agent.md: the Rule 4 text verbatim, its word diff against the Seed's Rule 4,
the size of the arm's dedicated job-read guidance (sections that say which job action carries
which field), and the arm's train reward on platform-004 (the task whose failure exposed the
rule). Also the upstream fix, rhpds/parsec PR #57 (from v4 T-opt), for reference; its diff is
vendored as results/v6_t4_e1/pr57_aap2_agent.diff (from `gh pr diff 57 --repo rhpds/parsec`).

Rule 4 = from the numbered "**Don't re-fetch job data" item to the next numbered item or heading.
Words = whitespace tokens; added/removed from a word-level difflib diff, as in Table 3.
"""
import difflib, json, re, statistics as st, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
R = ROOT / "results/v6_t4_e1"
GW = Path("/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-ps-worktrees/parsec-intake_v6")
G = GW / ".capevolve/v6_g2_e1/run_g2_e1"
T = ROOT / ".capevolve/v6_t2_e1_platform-004-events-then-config/run_platform-004-events-then-config"
TASK = "platform-004-events-then-config"
JOB_READ = ("### Choosing the job read", "### `get_job_log` vs `get_job_events`",
            "#### What the log carries vs. what the events carry", "#### `get_job` is the FIRST read")


def rule4(text: str) -> str:
    m = re.search(r"^\d+\. \*\*Don't re-fetch job data.*?(?=^\d+[a-z]?\. \*\*|^#{1,4} )", text, re.S | re.M)
    return m.group(0).rstrip() if m else ""


def section(text: str, head: str) -> str:
    i = text.find(head)
    if i < 0:
        return ""
    level = len(head) - len(head.lstrip("#"))
    rest = text[i + len(head):]
    m = re.search(rf"^#{{1,{level}}} ", rest, re.M)
    return head + (rest[: m.start()] if m else rest)


def wdiff(a: str, b: str) -> tuple[int, int]:
    add = rem = 0
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a.split(), b.split(), autojunk=False).get_opcodes():
        rem += (i2 - i1) if op in ("replace", "delete") else 0
        add += (j2 - j1) if op in ("replace", "insert") else 0
    return add, rem


def pr57_rule4() -> str:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else R / "pr57_aap2_agent.diff"
    lines = src.read_text().splitlines()
    plus = [l[1:] for l in lines if l.startswith("+") and not l.startswith("+++")]
    return rule4("\n".join(plus) + "\n## end\n")


def train_reward(arm: str) -> tuple[float, int] | None:
    vals = []
    if arm == "Seed":
        tag = lambda p: p[1] == "seed"  # noqa: E731
        files = (G / "rollouts/feedback").glob(f"{TASK}__seed__t*.json")
    elif arm == "Global":
        files = (G / "rollouts/feedback").glob(f"{TASK}__*__cand_0005__*.json")
    elif arm == "T-opt":
        best = json.loads((T / "state.json").read_text())["best_id"]
        files = (T / "rollouts/val").glob(f"{TASK}__{best}__t*.json")
    else:
        files = [f for s in (arm, arm + "x") for f in (ROOT / ".capevolve").glob(f"v5_v6t4_{s}_{TASK}/run_*/rollouts/val/*.json")]
    for f in files:
        r = json.loads(Path(f).read_text())
        if not (r.get("rollout") or {}).get("error"):
            vals.append(float(r["score"]["reward"]))
    return (st.fmean(vals), len(vals)) if vals else None


seed_text = (R / "merge_inputs/seed/aap2_agent.md").read_text()
best = json.loads((T / "state.json").read_text())["best_id"]
arms = {"Seed": seed_text, "T-opt": (T / "candidates" / best / "aap2_agent.md").read_text(),
        "m1": (R / "m1_order/aap2_agent.md").read_text(), "m3": (R / "m3_smart/aap2_agent.md").read_text(),
        "m2": (R / "m2_nonconflict/aap2_agent.md").read_text(), "Global": (G / "candidates/cand_0005/aap2_agent.md").read_text()}
seed_r4 = rule4(seed_text)
rows = {}
for name, text in arms.items():
    r4 = rule4(text)
    a, d = wdiff(seed_r4, r4)
    jr = {h.strip("#` ").split("—")[0].strip(): len(section(text, h).split()) for h in JOB_READ if section(text, h)}
    fa, fd = wdiff(seed_text, text)
    rw = train_reward(name)
    rows[name] = {"rule4_text": r4, "rule4_words": len(r4.split()), "rule4_added": a, "rule4_removed": d,
                  "rule4_unchanged": r4 == seed_r4, "job_read_sections": jr, "job_read_words": sum(jr.values()),
                  "aap2_file_added": fa, "aap2_file_removed": fd,
                  "platform004_train": rw and round(rw[0], 3), "platform004_trials": rw and rw[1]}
p = pr57_rule4()
a, d = wdiff(seed_r4, p)
rows["PR #57"] = {"rule4_text": p, "rule4_words": len(p.split()), "rule4_added": a, "rule4_removed": d,
                  "rule4_unchanged": False, "job_read_sections": {}, "job_read_words": 0,
                  "aap2_file_added": a, "aap2_file_removed": d, "platform004_train": None, "platform004_trials": None}
(R / "rule4_table.json").write_text(json.dumps({"rows": rows, "definitions": __doc__}, indent=1))
for k, r in rows.items():
    print(f"{k:8s} r4 {r['rule4_words']:4d}w +{r['rule4_added']:<4d}-{r['rule4_removed']:<3d} same={r['rule4_unchanged']!s:5s} "
          f"jobread {r['job_read_words']:4d} {list(r['job_read_sections'])} file +{r['aap2_file_added']} -{r['aap2_file_removed']} "
          f"p004 {r['platform004_train']} (n={r['platform004_trials']})")
