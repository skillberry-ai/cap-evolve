"""Acceptance A7: one trajectory -> save_trajectory -> >= 1 guideline; lossless consolidation conserves
support; both renderers give a block under the size limit. Uses a throwaway store (AW_ALTK_DIR).

    AW_ALTK_DIR=/tmp/aw_eval/runs/altk_probe python check_altk.py ROLLOUT_JSON [ROLLOUT_JSON ...]
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import altk_common  # noqa: E402

NS = "aw_train"


def main(argv: list[str]) -> int:
    altk_common.setup(namespace=NS)
    from altk_evolve.frontend.client.evolve_client import EvolveClient
    from altk_evolve.frontend.mcp import mcp_server
    from to_messages import load

    ok = True
    n_first = None
    for i, p in enumerate(argv[1:]):
        tid = Path(p).name.split("__")[0]
        mcp_server.save_trajectory(json.dumps(load(Path(p))), task_id=tid, namespace_id=NS)
        # save_trajectory returns the trajectory entities only; count this task's guidelines in the store
        n = len(EvolveClient().get_all_entities(NS, filters={"type": "guideline", "metadata.source_task_id": tid},
                                                limit=10000))
        n_first = n if n_first is None else n_first
        print(f"save_trajectory({Path(p).name}) -> {n} guidelines")
    ok &= bool(n_first)
    c = EvolveClient()
    before = c.get_all_entities(NS, filters={"type": "guideline"}, limit=10000)
    sb = sum(int((e.metadata or {}).get("support", 1) or 1) for e in before)
    res = c.consolidate_guidelines(NS, mode="lossless")
    after = c.get_all_entities(NS, filters={"type": "guideline"}, limit=10000)
    sa = sum(int((e.metadata or {}).get("support", 1) or 1) for e in after)
    print(f"consolidation: {len(before)} -> {len(after)} guidelines, support {sb} -> {sa}; {res}")
    ok &= sb == sa
    tmp = Path(tempfile.mkdtemp())
    ids = tmp / "ids.txt"
    ids.write_text("\n".join(Path(p).name.split("__")[0] for p in argv[1:]))
    py = sys.executable
    here = Path(__file__).resolve().parent
    for dose, extra in (("full", []), ("ret", [str(ids)])):
        r = subprocess.run([py, str(here / "altk_render.py"), dose, str(tmp / dose), *extra], capture_output=True, text=True)
        print(f"render {dose}: rc={r.returncode} {r.stdout.strip()[-300:]}")
        ok &= r.returncode == 0
    print("A7 usage:", altk_common.usage_totals())
    print("A7", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
