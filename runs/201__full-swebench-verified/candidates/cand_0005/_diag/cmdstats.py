"""Aggregate command stats: which commands appear across PASSING vs FAILING traces."""
import glob
import json
import re
from collections import defaultdict

stats = defaultdict(lambda: {"pass": 0, "fail": 0})
examples = defaultdict(lambda: {"pass": [], "fail": []})

for f in sorted(glob.glob("trajectories/*.json")):
    d = json.load(open(f))
    r = d["rollout"]
    tr = r.get("trace") or {}
    steps = tr.get("steps") or []
    rew = d["score"].get("reward") or 0
    cat = "pass" if rew >= 0.5 else "fail"
    for s in steps:
        if s.get("source") != "agent":
            continue
        for tc in s.get("tool_calls") or []:
            cmd = (tc.get("arguments") or {}).get("command", "")
            # classify command by its head
            head = cmd.strip().split("\n")[0][:80]
            for key in ["git apply", "applypatch", "git add", "git commit", "git stash",
                        "pytest", "python -m pytest", "bin/test", "runtests.py",
                        "verify-fix", "pip install", "git checkout", "git diff",
                        "python - <<", "sed -i", "cat <<", "revert"]:
                if key in cmd:
                    stats[key][cat] += 1
                    if len(examples[key][cat]) < 2:
                        examples[key][cat].append((f.split("/")[-1].split("__seed")[0], head))
                    break

print(f"{'command':<22} {'pass#':>6} {'fail#':>6}")
for k in sorted(stats, key=lambda k: -(stats[k]["pass"] + stats[k]["fail"])):
    v = stats[k]
    print(f"{k:<22} {v['pass']:>6} {v['fail']:>6}")
