"""Render the two ALTK-Evolve doses into candidate dirs (README: ALTK-Evolve arm). Python 3.12 venv.

    python altk_render.py full OUT_CANDIDATE_DIR
    python altk_render.py ret  OUT_CANDIDATE_DIR TASK_IDS_FILE   [--root APPWORLD_ROOT]

Both copy the seed capability and fill its memory slot with the library's own ``format_selection``
text: ``full`` puts the whole consolidated set (injection_mode=static) in memory/playbook.md;
``ret`` writes memory/retrieval.json, one block per task id: core (support >= 3) + top-k 10
retrieved from the instruction text only (``select_guidelines``, injection_mode=retrieval).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import altk_common  # noqa: E402

SEED = Path(__file__).resolve().parents[1] / "seed_capability"
MEMORY_MAX_CHARS = 30000
NAMESPACE = "aw_train"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dose", choices=["full", "ret"])
    ap.add_argument("out")
    ap.add_argument("task_ids", nargs="?")
    ap.add_argument("--root", default=str(altk_common.EVAL / "root_opt"))
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--core-support", type=int, default=3)
    args = ap.parse_args()
    altk_common.setup(namespace=NAMESPACE)
    from altk_evolve.frontend.client.evolve_client import EvolveClient
    from altk_evolve.llm.guidelines.retrieval import GuidelineSelection, format_selection

    client = EvolveClient()
    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(SEED, out)
    stats: dict = {"dose": args.dose}
    if args.dose == "full":
        ents = client.get_all_entities(NAMESPACE, filters={"type": "guideline"}, limit=10000)
        ents = sorted(ents, key=lambda e: (-int((e.metadata or {}).get("support", 1) or 1), str(e.content)))
        block = format_selection(GuidelineSelection(core=ents, retrieved=[]))
        (out / "memory" / "playbook.md").write_text(block)
        stats.update(guidelines=len(ents), chars=len(block), over_limit=len(block) > MEMORY_MAX_CHARS)
    else:
        ids = Path(args.task_ids).read_text().split()
        blocks, sizes = {}, []
        for tid in ids:
            instr = json.loads((Path(args.root) / "data/tasks" / tid / "specs.json").read_text())["instruction"]
            sel = client.select_guidelines(NAMESPACE, instr, top_k=args.top_k, core_support=args.core_support)
            blocks[tid] = format_selection(sel)
            sizes.append((len(sel.core), len(sel.retrieved), len(blocks[tid])))
        (out / "memory" / "retrieval.json").write_text(json.dumps(blocks, indent=1))
        stats.update(tasks=len(ids), core=sizes[0][0] if sizes else 0,
                     mean_retrieved=sum(s[1] for s in sizes) / max(1, len(sizes)),
                     max_chars=max((s[2] for s in sizes), default=0),
                     over_limit=any(s[2] > MEMORY_MAX_CHARS for s in sizes))
    (out / "memory" / "render_stats.json").write_text(json.dumps(stats, indent=1))
    altk_common.log(f"rendered {args.dose}: {stats}", "render")
    print(json.dumps(stats))
    return 1 if stats.get("over_limit") else 0


if __name__ == "__main__":
    raise SystemExit(main())
