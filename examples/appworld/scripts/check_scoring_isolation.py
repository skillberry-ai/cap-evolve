"""Acceptance A3 (REPL isolation, root_opt, split file) and A5 (scoring), no model call.

Usage: APPWORLD_ROOT=/tmp/aw_eval/root_opt python check_scoring_isolation.py SPLIT_IDS_JSON
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import aw_agent  # noqa: E402
from awpaths import ROOT_OPT, read_split  # noqa: E402
from appworld import AppWorld  # noqa: E402
from cap_evolve import Rollout  # noqa: E402

from adapter import Adapter  # noqa: E402


def compiled_solution_code(tid: str) -> str:
    src = (ROOT_OPT / "data/tasks" / tid / "ground_truth/compiled_solution.py").read_text()
    body = "\n".join(l for l in src.splitlines() if not re.match(r"^(from|import) ", l) and not l.startswith("#"))
    return body.replace("apis: ApiCollection, requester: Requester", "apis, requester").replace(") -> None:", "):")


def run_world(tid: str, exp: str, code: str | None):
    with AppWorld(task_id=tid, experiment_name=exp) as world:
        out = ""
        if code:
            out = world.execute(code)
            out += world.execute("solution(apis, requester)")
        return aw_agent.evaluation_fields(world.evaluate().to_dict(stats_only=False)), out


def main(argv: list[str]) -> int:
    ok = True
    train, dev = read_split("train", ROOT_OPT), read_split("dev", ROOT_OPT)
    # A3.1 REPL guards, hardened for every arm
    aw_agent.harden_guard()
    gt = ROOT_OPT / "data/tasks" / train[0] / "ground_truth/answer.json"
    with AppWorld(task_id=dev[0], experiment_name="probes/a3") as world:
        r_os = world.execute("import os\nprint(os.listdir('.'))")
        r_open = world.execute(f"print(open({str(gt)!r}).read())")
        r_path = world.execute(f"import pathlib\nprint(pathlib.Path({str(gt)!r}).read_text())")
    blocked = all(r.startswith("Execution failed") for r in (r_os, r_open, r_path))
    print(f"A3.1 import os / open(answer.json) / pathlib read all fail: {blocked}")
    ok &= blocked
    # A3.2 root_opt has no test data
    test_ids = set(read_split("test_normal")) | set(read_split("test_challenge"))
    present = set(os.listdir(ROOT_OPT / "data/tasks")) & test_ids
    no_test_files = not present and sorted(os.listdir(ROOT_OPT / "data/datasets")) == ["dev.txt", "train.txt"]
    print(f"A3.2 root_opt: no test task dirs, only train/dev split files: {no_test_files}")
    ok &= no_test_files
    # A3.3 split_ids.json == train ∪ dev
    sp = json.loads(Path(argv[1]).read_text())
    split_ok = sp["train"] == sp["val"] == train + dev and sp["test"] == []
    print(f"A3.3 split_ids.json train = val = train.txt ∪ dev.txt ({len(sp['val'])}), test = []: {split_ok}")
    ok &= split_ok

    # A5 scoring
    ad = Adapter()
    tid = train[0]
    task = [t for t in ad.tasks("train") if t.id == tid][0]
    fields_ok, out = run_world(tid, "probes/a5_solution", compiled_solution_code(tid))
    fields_noop, _ = run_world(tid, "probes/a5_noop", None)
    r_ok = Rollout(task_id=tid, trace=[], metadata=dict(fields_ok, n_steps=1, termination="completed"))
    r_no = Rollout(task_id=tid, trace=[], metadata=dict(fields_noop, n_steps=0, termination="max_steps"))
    s1, s2, s0 = ad.score(task, r_ok), ad.score(task, r_ok), ad.score(task, r_no)
    print(f"A5.1 released solution -> reward {s1.reward} (solution output: {out.strip()[:80]!r})")
    print(f"A5.2 no-op -> reward {s0.reward}")
    det = s1.to_dict() == s2.to_dict() and s0.to_dict() == ad.score(task, r_no).to_dict()
    print(f"A5.3 score twice identical: {det}")
    persisted = json.dumps({"rollout": r_no.to_dict(), "score": s0.to_dict()})
    answer = json.loads(gt.read_text()) if gt.is_file() else None
    no_trace = '"trace": "' not in persisted and "Traceback" not in persisted
    no_gold = answer in (None, "") or json.dumps(answer) not in persisted
    print(f"A5.4 persisted metadata has no failure trace: {no_trace}; gold answer absent: {no_gold}")
    ok &= s1.reward == 1.0 and s0.reward == 0.0 and det and no_trace and no_gold
    print("A3+A5", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
