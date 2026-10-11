"""R1: footprint masking can turn a net-negative candidate into an ACCEPT (hill-climb default path)."""
import sys, json, tempfile, pathlib
sys.path.insert(0, "/home/dev/projects2/cap-evolve-campaign/core")
from cap_evolve import footprint, gate
from cap_evolve.harness import _paired_deltas
from cap_evolve.loop import SplitResult

T = 30
tid = [f"t{i:02d}" for i in range(T)]
# parent: passes everything except 5 tasks
par = {t: (0.0 if i < 5 else 1.0) for i, t in enumerate(tid)}
# candidate: fixes the 4 tasks that call tool `refund_order` (inside footprint), but a prose
# rule added to prompt.md breaks 6 OTHER tasks (outside footprint, no named surface in diff).
cand = dict(par)
for t in tid[1:5]: cand[t] = 1.0      # +4 fixed, in-footprint
for t in tid[20:26]: cand[t] = 0.0    # -6 broken, out-of-footprint
def sr(d): return SplitResult("val", sum(d.values())/T, 0.0,
    per_task=[{"task_id": t, "reward": r, "stderr": 0.0, "raw": {"valid_trials": 1, "n_trials": 1}} for t, r in d.items()],
    n_tasks=T, n_scored=T)
P, C = sr(par), sr(cand)

root = pathlib.Path(tempfile.mkdtemp())
(root/"parent").mkdir(); (root/"cand").mkdir(); (root/"rollouts/val").mkdir(parents=True)
(root/"parent/tools.py").write_text("def refund_order(o):\n    return o\n")
(root/"parent/prompt.md").write_text("Be helpful.\n")
(root/"cand/tools.py").write_text("def refund_order(o):\n    return validate(o)\n")
(root/"cand/prompt.md").write_text("Be helpful.\nNever transfer to a human agent under any circumstances.\n")
for i, t in enumerate(tid):
    for tag in ("parent", "cand"):
        text = json.dumps({"trace": ["call refund_order(1)"] if i in (1,2,3,4) else ["call lookup(2)"]})
        (root/f"rollouts/val/{t}__{tag}__t0.json").write_text(text)
class RD: rollouts = root/"rollouts"
fp = footprint.footprint(RD, parent_dir=root/"parent", cand_dir=root/"cand", tags=("parent","cand"), split="val", all_task_ids=tid)
print("footprint:", sorted(fp) if fp else fp)
for label, f in (("full vector", None), ("footprint (default)", fp)):
    d = _paired_deltas(P, C, footprint=f)
    dec = gate.decide(P.reward, C.reward, mode="paired", paired_deltas=d, k_se=1.0)
    print(f"{label:22s} mean_delta={sum(d)/len(d):+.4f} accept={dec.accept} :: {dec.reason}")
print("true full-split delta (cand-par) =", round(C.reward-P.reward,4), "; n_broke(full split) =", sum(1 for t in tid if par[t]==1 and cand[t]==0))
