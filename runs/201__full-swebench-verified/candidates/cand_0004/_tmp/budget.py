"""Check final_metrics/notes/agent config in trajectories to learn the budget."""
import json
import glob

for f in sorted(glob.glob("trajectories/*.json"))[:6]:
    d = json.load(open(f))
    tr = d["rollout"]["trace"]
    print("==", d["score"]["task_id"], "reward", d["score"]["reward"])
    print("  agent:", json.dumps(tr.get("agent"))[:400])
    print("  notes:", str(tr.get("notes"))[:300])
    print("  final_metrics:", json.dumps(tr.get("final_metrics"))[:400])
