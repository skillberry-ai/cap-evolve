"""Dose selection on the 57 official dev tasks (README: ALTK-Evolve arm). Runs in venv-aw (it uses the adapter).

    python select_dose.py FULL_CANDIDATE_DIR RET_CANDIDATE_DIR OUT_JSON

Scores both doses on dev, 1 trial each, with the same harness as every arm. Rule fixed in
advance: the higher TGC wins; on a tie, the dose with fewer memory tokens. Rollouts are kept
(gold-free) under ``runs/altk/dev_<dose>/`` for the record.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "adapters"))
from adapter import Adapter, _split_ids  # noqa: E402

EVAL = Path(os.environ.get("AW_EVAL", "/tmp/aw_eval"))


def memory_tokens(cdir: Path, ids: list[str]) -> float:
    import tiktoken
    enc = tiktoken.get_encoding("o200k_base")
    pb = cdir / "memory" / "playbook.md"
    if pb.is_file():
        return float(len(enc.encode(pb.read_text())))
    blocks = json.loads((cdir / "memory" / "retrieval.json").read_text())
    return sum(len(enc.encode(blocks.get(t, ""))) for t in ids) / max(1, len(ids))


def main(argv: list[str]) -> int:
    full, ret, out = Path(argv[1]).resolve(), Path(argv[2]).resolve(), Path(argv[3])
    ad = Adapter()
    dev = _split_ids("dev")
    if len(dev) != 57:
        print(f"expected 57 dev ids, got {len(dev)}", file=sys.stderr)
        return 1
    tasks = [t for t in ad.tasks("val") if t.id in set(dev)]
    import lints  # noqa: E402

    res: dict = {}
    for name, cdir in (("altk-full", full), ("altk-ret", ret)):
        bad = lints.lint_candidate(cdir)
        if bad:
            # Same rule as every candidate (README: Lints): a lint-violating dose is rejected without a rollout.
            res[name] = {"infeasible": bad[:5], "n_violations": len(bad),
                         "memory_tokens_per_task": memory_tokens(cdir, dev), "candidate_dir": str(cdir)}
            with open(EVAL / "progress" / "altk.log", "a") as f:
                import time
                f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} | altk | dose | "
                        f"dose {name} infeasible (lint): {bad[0][:200]}\n")
            continue
        os.environ["AW_PHASE"] = f"dose {name}"
        rollouts = ad.run_trials(tasks, cdir, n_trials=1, base_seed=0)
        rdir = EVAL / "runs" / "altk" / f"dev_{name}"
        rdir.mkdir(parents=True, exist_ok=True)
        rewards, errored = {}, []
        for t in tasks:
            r = rollouts[t.id][0]
            s = ad.score(t, r)
            (rdir / f"{t.id}__{name}__t0.json").write_text(json.dumps(
                {"input": t.input, "rollout": r.to_dict(), "score": s.to_dict()}, default=str))
            if r.error:
                errored.append(t.id)
            else:
                rewards[t.id] = s.reward
        # an infra-errored episode is missing data, scored 0 here (primary) and listed
        tgc = sum(rewards.get(t.id, 0.0) for t in tasks) / len(tasks)
        res[name] = {"dev_tgc": tgc, "n": len(tasks), "infra_errored": errored,
                     "memory_tokens_per_task": memory_tokens(cdir, dev), "candidate_dir": str(cdir)}
        with open(EVAL / "progress" / "altk.log", "a") as f:
            import time
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} | altk | dose | "
                    f"dose {name} dev={tgc:.4f} ({len(errored)} infra errors)\n")
    a, b = res["altk-full"], res["altk-ret"]
    feasible = [n for n in ("altk-full", "altk-ret") if "dev_tgc" in res[n]]
    if not feasible:
        print("no feasible dose", file=sys.stderr)
        out.write_text(json.dumps(res, indent=1))
        return 1
    if len(feasible) == 1:
        chosen = feasible[0]
    elif a["dev_tgc"] != b["dev_tgc"]:
        chosen = "altk-full" if a["dev_tgc"] > b["dev_tgc"] else "altk-ret"
    else:
        chosen = "altk-full" if a["memory_tokens_per_task"] <= b["memory_tokens_per_task"] else "altk-ret"
    res["chosen"] = chosen
    res["rule"] = "higher dev TGC; tie -> fewer memory tokens per task; a lint-violating dose is infeasible"
    out.write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
