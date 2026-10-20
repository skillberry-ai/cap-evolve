"""The common final window (README: Final window): 168 test_normal tasks x 3 arms x 2 trials.

    python final_window.py freeze     # copy the three frozen artifacts into runs/final/artifacts/, hash them
    python final_window.py run        # run the window (resumable; touch runs/final/PAUSE to pause)

Episodes run in one random order (recorded seed) with AW_ALLOW_SEALED=final-eval-only and
APPWORLD_ROOT=root_full, 48 at a time, trial seeds 5000 + trial. Infrastructure failures are
retried up to 3 times. Only rewards, counters and infrastructure flags are written: no test
trajectory is kept or read.
"""

from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "adapters"))
from awpaths import ALTK_PYTHON, CAPE_RUN, EVAL, FINAL, PROGRESS, ROOT_FULL, RUNS, SECRETS_FILE, read_split, sha256_tree, update_manifest  # noqa: E402

ART = FINAL / "artifacts"
RESULTS = FINAL / "results.jsonl"
ORDER_SEED = 20261013
TRIALS = 2
ARMS = ("seed", "cape-hc", "altk")
SEED_CAP = HERE.parent / "seed_capability"
ALTK = RUNS / "altk"
VALTK = ALTK_PYTHON


def log(detail: str) -> None:
    with open(PROGRESS / "final.log", "a") as f:
        f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} | final | window | {detail}\n")


def freeze() -> int:
    if ART.exists():
        print(f"{ART} exists; artifacts are frozen once", file=sys.stderr)
        return 1
    ART.mkdir(parents=True)
    state = json.loads((CAPE_RUN / "state.json").read_text())
    best = state["best_id"]
    reuse = os.environ.get("AW_REUSE_ARTIFACTS")   # e.g. runs/final/artifacts: keep seed + altk byte-identical
    if reuse:
        for arm in ("seed", "altk"):
            shutil.copytree(Path(reuse) / arm, ART / arm)
        shutil.copytree(CAPE_RUN / "candidates" / best, ART / "cape-hc",
                        ignore=shutil.ignore_patterns(".git", "PROCESS.md", "JOURNAL.md", "DIAGNOSIS.json", "INSTRUCTIONS.md"))
        hashes = {arm: sha256_tree(ART / arm) for arm in ARMS}
        update_manifest(**{f"{FINAL.name}_artifacts": {"cape-hc_best_id": best, "reused_from": reuse,
                                                       "inert_cape_hc": best == "seed", "sha256_tree": hashes}})
        log(f"frozen: cape-hc={best}; seed and altk reused from {reuse}; hashes {hashes}")
        print(json.dumps(hashes, indent=1))
        return 0
    shutil.copytree(SEED_CAP, ART / "seed")
    shutil.copytree(CAPE_RUN / "candidates" / best, ART / "cape-hc",
                    ignore=shutil.ignore_patterns(".git", "PROCESS.md", "JOURNAL.md", "DIAGNOSIS.json", "INSTRUCTIONS.md"))
    sel = json.loads((ALTK / "dose_selection.json").read_text())
    if sel["chosen"] == "altk-full":
        shutil.copytree(ALTK / "cand_full", ART / "altk")
    else:
        # per-task blocks for test_normal, retrieved from the instruction text only
        r = subprocess.run([VALTK, str(HERE.parent / "altk/altk_render.py"), "ret", str(ART / "altk"),
                            str(ROOT_FULL / "data/datasets/test_normal.txt"), "--root", str(ROOT_FULL)],
                           capture_output=True, text=True, env=dict(os.environ, LITELLM_LOG="ERROR"))
        if r.returncode != 0:
            print(r.stdout[-2000:], r.stderr[-2000:], file=sys.stderr)
            return 1
    hashes = {arm: sha256_tree(ART / arm) for arm in ARMS}
    update_manifest(final_artifacts={"cape-hc_best_id": best, "altk_dose": sel["chosen"],
                                     "inert_cape_hc": best == "seed", "sha256_tree": hashes})
    log(f"frozen: cape-hc={best}, altk={sel['chosen']}, hashes {hashes}")
    print(json.dumps(hashes, indent=1))
    return 0


def run() -> int:
    os.environ["AW_ALLOW_SEALED"] = "final-eval-only"
    os.environ["AW_APPWORLD_ROOT"] = str(ROOT_FULL)
    os.environ.setdefault("AW_EXPERIMENT", FINAL.name)
    os.environ.setdefault("AW_SECRETS_FILE", SECRETS_FILE)
    os.environ.pop(os.environ.get("AW_KEY_ENV", "RITS_API_KEY"), None)
    from adapter import Adapter, _task  # noqa: E402

    import lints  # noqa: E402

    bad = {arm: v for arm in ARMS if (v := lints.lint_candidate(ART / arm))}
    if bad:
        print(f"frozen artifacts fail the lints: {bad}", file=sys.stderr)
        return 1
    ad = Adapter()
    ids = read_split("test_normal")
    if len(ids) != 168:
        print(f"expected 168 test_normal ids, got {len(ids)}", file=sys.stderr)
        return 1
    tasks = {t: _task(t, ROOT_FULL) for t in ids}
    jobs = [(arm, t, k) for arm in ARMS for t in ids for k in range(TRIALS)]
    random.Random(ORDER_SEED).shuffle(jobs)
    done = set()
    if RESULTS.is_file():
        for line in RESULTS.read_text().splitlines():
            r = json.loads(line)
            if not r.get("infra_error"):
                done.add((r["arm"], r["task_id"], r["trial"]))
    todo = [j for j in jobs if j not in done]
    update_manifest(**{f"{FINAL.name}_window": {"order_seed": ORDER_SEED, "trials": TRIALS, "workers": int(os.environ.get("AW_WORKERS", "48")),
                                  "trial_random_seed": "5000 + trial", "infra_retries": 3}})
    log(f"start: {len(todo)} of {len(jobs)} episodes to run ({len(done)} done)")
    scratch = Path(tempfile.mkdtemp(prefix="final_", dir=EVAL / "scratch"))
    lock = threading.Lock()
    counter = {"done": len(done), "errors": 0, "t0": time.time(), "ran": 0}

    def status(phase: str) -> None:
        ran, el = counter["ran"], time.time() - counter["t0"]
        rem = len(jobs) - counter["done"]
        eta = time.strftime("%H:%M UTC", time.gmtime(time.time() + el / ran * rem)) if ran else ""
        (FINAL / "status.json").write_text(json.dumps({"phase": phase, "done": counter["done"], "total": len(jobs),
                                                      "infra_errors": counter["errors"], "eta": eta}))

    def one(job):
        while (FINAL / "PAUSE").exists():
            time.sleep(30)
        arm, tid, k = job
        r = ad._episode(tasks[tid], ART / arm, seed=k, root=ROOT_FULL, workdir=scratch, random_seed=5000 + k)
        m = r.metadata or {}
        rec = {"arm": arm, "task_id": tid, "trial": k, "infra_error": r.error,
               **{key: m.get(key) for key in ("success", "num_tests", "pass_count", "n_steps", "prompt_tokens",
                                              "completion_tokens", "max_prompt_tokens", "termination",
                                              "collateral_damage", "complete_task_called", "api_errors",
                                              "trimmed_steps", "fs_probe", "episode_seconds", "attempt")}}
        with lock:
            with open(RESULTS, "a") as f:
                f.write(json.dumps(rec) + "\n")
            counter["ran"] += 1
            if r.error:
                counter["errors"] += 1
            else:
                counter["done"] += 1
            if counter["ran"] % 24 == 0:
                log(f"final {counter['done']}/{len(jobs)} episodes ({counter['errors']} infra errors so far)")
                status("running")
        return rec

    os.environ["AW_INFRA_RETRIES"] = "3"
    status("running")
    with ThreadPoolExecutor(max_workers=int(os.environ.get("AW_WORKERS", "48"))) as pool:
        for fut in as_completed([pool.submit(one, j) for j in todo]):
            fut.result()
    status("done")
    log(f"done: {counter['done']}/{len(jobs)} episodes, {counter['errors']} infra-errored attempts")
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    raise SystemExit({"freeze": freeze, "run": run}.get(cmd, lambda: (print(__doc__), 2)[1])())
