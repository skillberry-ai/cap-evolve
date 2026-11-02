#!/usr/bin/env python3
"""Run ONE upstream Trace2Skill LLM-only analyst CLI with one upstream bug fixed at runtime (no upstream file edited).

Usage: t2s_analyse.py <error|success> <upstream CLI args...>
  error   -> analysis.run_error_analysis_llm.main()
  success -> analysis.run_success_analysis_llm.main()

Deviation D9 (deviations_trace2skill.json): upstream find_logs_repeat() does `sorted(os.scandir(logs_dir))`, which on
Python 3 raises `TypeError: '<' not supported between instances of 'posix.DirEntry'` as soon as logs_dir holds two or
more entries, so `--repeat k` (k > 1) can never run (observed: runs/trace2skill/smoke_s0/analysis_*.log). The fix
replaces that one function with a copy whose only change is the sort key (`key=lambda e: e.name`, i.e. the order
upstream evidently intended). Everything else (prompts, LLM call, report writing, record parsing) is upstream's.
"""
import os
import sys
from pathlib import Path

EXP = Path("/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-spread-worktrees/exp895")
UP = EXP / "competitors" / "trace2skill"
sys.path.insert(0, str(UP))


def _make_fixed(mod, outcome_kw: str, outcome: str):
    def find_logs_repeat(logs_dir, **kw):
        only = kw.get(outcome_kw, True)
        result = {}
        for entry in sorted(os.scandir(logs_dir), key=lambda e: e.name):   # the ONLY change vs upstream
            if not (entry.is_dir() and entry.name.startswith("seed_")):
                continue
            seed_name = entry.name
            for name in sorted(os.listdir(entry.path)):
                parsed = mod.parse_log_filename(name)
                if parsed is None:
                    continue
                instance_id, got = parsed
                if only and got != outcome:
                    continue
                result[f"{instance_id}_{seed_name}"] = os.path.join(entry.path, name)
        return result
    return find_logs_repeat


def main():
    mode, rest = sys.argv[1], sys.argv[2:]
    if mode == "error":
        import analysis.run_error_analysis_llm as m
        m.find_logs_repeat = _make_fixed(m, "failed_only", "FAILED")
    elif mode == "success":
        import analysis.run_success_analysis_llm as m
        m.find_logs_repeat = _make_fixed(m, "succeed_only", "SUCCEED")
    else:
        sys.exit(f"unknown mode {mode!r}")
    sys.argv = [m.__file__] + rest
    m.main()


if __name__ == "__main__":
    main()
