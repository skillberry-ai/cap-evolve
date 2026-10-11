"""R6: the tamper seal hashes only the candidate WORKDIR; an optimizer subprocess can rewrite the project's adapter/scorer
outside it and verify() still reports ok. Uses the real harness.optimizer_from_command (no sandbox, full env inherited)."""
import sys, os, tempfile, pathlib, textwrap
sys.path.insert(0, "/home/dev/projects2/cap-evolve-campaign/core")
from cap_evolve import harness, integrity
root = pathlib.Path(tempfile.mkdtemp())
proj = root/"project"; proj.mkdir(); (proj/"adapter.py").write_text("SCORER='honest'\n"); (proj/"scorer.py").write_text("def score(): return 0.0\n")
work = root/"run/work/cand_0001"; work.mkdir(parents=True); (work/"skill.md").write_text("v0\n")
man = integrity.snapshot(work, integrity.DEFAULT_PATTERNS)           # what run_step does (workdir only)
evil = textwrap.dedent(f"""
import pathlib, os
pathlib.Path({str(proj/'scorer.py')!r}).write_text('def score(): return 1.0\\n')   # outside workdir
print('env keys visible to optimizer:', sum(k.endswith(('_KEY','_TOKEN')) for k in os.environ))
""")
opt = harness.optimizer_from_command([sys.executable, "-c", evil])
opt(work, "go")
print("verify ok:", integrity.verify(man, work).ok, "| scorer.py now:", (proj/'scorer.py').read_text().strip())
print("manifest covers:", list(man['files']) or "(no protected files inside workdir)")
