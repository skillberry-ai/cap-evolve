#!/usr/bin/env python3
"""Launch the held-out test window for each search the moment its optimization ends (Boaz, 2026-10-22).

Light, login-node-safe: it only reads small JSON files and calls bsub/bjobs. One pass per invocation (run it from a
loop / Monitor). For every (arm, seed) it decides FINISHED + CHAMPION from the arm's own end-of-search record:
  capevolve:   run_meta.txt has CAPEVOLVE_RC=0 and run_main/champion.json exists  -> candidate_dir
  competitors: run_summary.json exists with no error, and <run>/champion/ exists   -> that frozen dir
A search that ended in error (rc!=0, error set, stop_reason engine_error) is NOT tested: it is reported for a relaunch.
Each launch goes through the exclusive-host wrapper; a test dir that exists (or a queued job of the same name) is skipped.
"""
import json
import subprocess
import zlib
from pathlib import Path

KEY_SLOTS = [1, 2, 3, 5, 6]   # working RITS keys in ~/secrets/rits_keys.env (slot 4 returns 403)

EXP = Path("/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-spread-worktrees/exp895")
ARMS = ["capevolve", "gepa", "gepa_full", "miprov2", "skillopt", "evoskill", "trace2skill", "meta_harness", "wikiskill", "ace",
        "capevolve_v2"]   # capevolve_v2 = main 75b3bcdd0 (PR #914, k_se 0.2), added 2026-10-25
RESERVED = r"^cccxc(6[0-3][0-9]|70[1247]|71[01]|535|575)$"
BAD_STOPS = ("engine_error", "error", "fatal", "infraoutage")


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout


def finished(arm, seed):
    """(status, champion_dir_or_reason)."""
    run = EXP / "runs" / arm / f"search_s{seed}"
    if not run.is_dir():
        return "absent", ""
    if arm in ("capevolve", "capevolve_v2"):
        meta = (run / "run_meta.txt").read_text() if (run / "run_meta.txt").exists() else ""
        if "CAPEVOLVE_RC=" not in meta:
            return "running", ""
        if "CAPEVOLVE_RC=0" not in meta:
            return "failed", "CAPEVOLVE_RC != 0"
        champ = run / "work/.capevolve/run_main/champion.json"
        return ("done", json.loads(champ.read_text())["candidate_dir"]) if champ.exists() else ("failed", "no champion.json")
    summ = run / "run_summary.json"
    if not summ.exists():
        return "running", ""
    s = json.loads(summ.read_text())
    stop = str(s.get("stop_reason", "")).lower()
    if s.get("error") not in (None, "None", "", "null") or any(b in stop for b in BAD_STOPS):
        return "failed", f"stop_reason={s.get('stop_reason')} error={s.get('error')}"
    champ = run / "champion"
    return ("done", str(champ)) if champ.is_dir() else ("failed", "no champion/ dir")


def main():
    queued = set(sh("bjobs -noheader -w -u $USER 2>/dev/null | awk '{print $7}'").split())
    busy = sh("bjobs -noheader -w -u $USER 2>/dev/null | awk '$7 ~ /^exp895_/ {split($6,a,\":\"); print a[1]}'").split()
    hosts = [h for h in sh("bhosts -w 2>/dev/null | awk 'NR>1 && ($2==\"ok\" || $2==\"closed_Full\") && $1 ~ /^cccxc/ {print $1}'").split()
             if h not in busy and not subprocess.run(["grep", "-qE", RESERVED], input=h, text=True).returncode == 0]
    for arm in ARMS:
        for seed in (0, 1, 2):
            st, info = finished(arm, seed)
            name = f"exp895_test_{arm}_s{seed}"
            if st == "failed":
                print(f"FAILED_SEARCH {arm} s{seed}: {info} (not tested; needs a relaunch)")
                continue
            if st != "done" or (EXP / "runs/test" / f"{arm}_s{seed}").exists() or name in queued:
                continue
            if not hosts:
                print(f"NO_HOST for {name}")
                continue
            # 2026-10-26: spread new test windows over the dedicated RITS keys (slot 4 is dead), deterministic per (arm, seed).
            slot = KEY_SLOTS[zlib.crc32(f"{arm}{seed}".encode()) % len(KEY_SLOTS)]
            env = f"all,ARM={arm},SEED={seed},CHAMP={info},CONC=16,KEY_SLOT={slot}"
            out = sh(f"bsub -q normal -n 1 -R 'span[hosts=1]' -M 64G -m '{' '.join(hosts)}' -Q 99 -J {name} -env '{env}' "
                     f"-oo {EXP}/logs/test_{arm}_s{seed}.%J.out -eo {EXP}/logs/test_{arm}_s{seed}.%J.err "
                     f"bash {EXP}/tools/lsf_exclusive_wrapper.sh {EXP}/tools/lsf_test_window_v3.sh 2>&1")
            print(f"LAUNCHED_TEST {arm} s{seed} key={slot} champion={info} ::{out.strip().splitlines()[-1] if out.strip() else out}")


if __name__ == "__main__":
    main()
