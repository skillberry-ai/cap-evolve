"""Compare cand_0003's actual capability files with the seed's."""
import subprocess
import sys

BASE = "/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_swebench-harnessfix-s2/work/cand_0004"

pairs = [
    ("candidates/seed/SKILL.md", "candidates/cand_0003/SKILL.md"),
    ("candidates/seed/prompt.md", "candidates/cand_0003/prompt.md"),
    ("candidates/seed/task-config.yaml", "candidates/cand_0003/task-config.yaml"),
    ("candidates/seed/SYSTEM.md", "candidates/cand_0003/SYSTEM.md"),
]

def show(rev, path):
    r = subprocess.run(["git", "-C", BASE, "show", f"{rev}:{path}"],
                       capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else f"<ERROR {r.returncode}: {r.stderr[:100]}>"

for seed_path, cand_path in pairs:
    a = show("69992b9", seed_path)
    b = show("e173dda", cand_path)
    same = "IDENTICAL" if a == b else "DIFFERENT"
    print(f"{seed_path} vs {cand_path}: {same} (seed {len(a)} chars, cand {len(b)} chars)")

# Also compare tools.py of cand_0003 (it was 105 lines = seed copy?) vs the 380-line .tmp file
a = show("69992b9", "candidates/seed/tools/tools.py")
b = show("e173dda", "candidates/cand_0003/tools/tools.py")
print(f"tools.py: {'IDENTICAL' if a == b else 'DIFFERENT'} (seed {len(a)}, cand3 {len(b)})")
tmp = show("e173dda", "candidates/cand_0003/.tmp_cand1_tools.py")
print(f"cand_0003 .tmp_cand1_tools.py: {len(tmp)} chars")
c1 = show("05787c6", "candidates/cand_0001/tools/tools.py")
print(f"cand_0001 tools.py: {len(c1)} chars")
