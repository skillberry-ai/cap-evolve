"""Behavioral contract for agent-optimize.

agent-optimize has no deterministic loop, so **SKILL.md's prose IS the
implementation** — which means the only honest contract test is to *execute* the
commands SKILL.md documents against a real throwaway run dir and fail if they don't
work. (The previous version only grepped SKILL.md for substrings, which is why a gate
invocation using an argparse choice that doesn't exist, a shell heredoc that never
expanded ``$R``, and a ``cp`` into a directory nobody creates all shipped.)

Offline and deterministic: a synthetic adapter + hand-written rollouts, zero model calls.

Asserts, end to end on a temp run dir:
  * the deterministic-invocation guard emits a JSON error naming the fix;
  * ``mkdir -p $R/work`` + copy-the-best is a real path (RunDir does NOT create ``work/``);
  * the documented **diagnose** command runs and yields ``kept_good``;
  * ``gate_check.py`` reaches the **paired** gate off real rollouts (``paired_n > 0``) and
    accepts a genuine improvement;
  * no-regression vetoes a mean gain that breaks a passing task;
  * ``commit.py`` moves ``best_id`` + ``iterations`` + the stall counter;
  * ``spend.py`` surfaces budget_exhausted + the free-text stop_condition;
  * every script SKILL.md names exists and is named in SKILL.md (no drift);
  * SKILL.md carries none of the known-broken patterns;
  * the test seal is never consumed.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve.skillcheck import (
    Checker, SyntheticAdapter, import_run, quiet, seed_capability_dir, temp_run_dir,
    write_val_rollout,
)

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parents[2]
SKILL_MD = HERE.parent / "SKILL.md"
DIAGNOSE = SKILLS / "phases" / "diagnose" / "scripts" / "run.py"


def _run(c: Checker, label: str, argv: list[str]) -> dict | None:
    """Execute a documented command; return its parsed JSON (None on failure)."""
    env = dict(os.environ, CAPEVOLVE_CORE=str(SKILLS.parent / "core"))
    p = subprocess.run([sys.executable, *argv], capture_output=True, text=True, env=env)
    if p.returncode != 0:
        c.fail(f"documented command failed ({label}, rc={p.returncode}): "
               f"{(p.stderr or p.stdout).strip()[:400]}")
        return None
    try:
        return json.loads(p.stdout)
    except Exception:  # noqa: BLE001
        c.fail(f"documented command did not emit JSON ({label}): {p.stdout[:200]}")
        return None


def _guard(c: Checker) -> None:
    run = import_run()
    c.require_main(run)
    with quiet() as buf:
        rc = run.main(["--run-dir", "R", "--project", "P", "--optimizer", "x"])
    try:
        payload = json.loads(buf.getvalue())
    except Exception:  # noqa: BLE001
        payload = {}
    c.check(rc != 0 and "orchestration_mode" in str(payload.get("fix", "")),
            "run.main must refuse a deterministic invocation with a JSON fix naming "
            f"orchestration_mode (rc={rc}, payload={payload})",
            note="deterministic invocation is rejected with an actionable fix message")


def _prose(c: Checker, skill: str) -> None:
    for section in ("## Agent-mode loop", "Phase 0", "Honesty invariants",
                    "## Parallel round"):
        c.check(section in skill, f"SKILL.md missing section: {section!r}")
    for needle in ("FULL val", "stop_condition", "finalize", "budget_exhausted",
                   "no-regression", "unique per sibling"):
        c.check(needle in skill, f"SKILL.md missing honesty/loop marker: {needle!r}")

    # Known-broken patterns that previously shipped.
    # `--mode paired` used to be an invalid choice (argparse exit 2). The phase CLI now
    # reaches it, but ONLY in rollout mode: two scalar means carry no per-task deltas.
    # Join backslash continuations so a multi-line invocation is judged as one command.
    _joined = skill.replace("\\\n", " ")
    c.check(all("--run-dir" in ln for ln in _joined.splitlines() if "--mode paired" in ln),
            "SKILL.md pairs `--mode paired` with scalar means — that combination is "
            "refused; a paired test needs --run-dir/--current-tag/--candidate-tag",
            note="any --mode paired invocation supplies a run dir")
    c.check("<<'PY'" not in skill and '<<"PY"' not in skill,
            "SKILL.md uses a heredoc for run-dir Python (a quoted one never expands $R)",
            note="no heredoc-Python: the commit step is a real script with real flags")
    c.check('mkdir -p "$R/work"' in skill,
            "SKILL.md copies into $R/work without creating it (RunDir.create does not)",
            note="$R/work is explicitly created before it is used")
    c.check("Example only" in skill,
            "SKILL.md must mark the capability file layout as example-only")

    # Every helper the loop names must exist, and every helper must be named.
    helpers = ["gate_check.py", "commit.py", "spend.py"]
    for h in helpers:
        c.check((HERE / h).is_file(), f"missing documented helper script: scripts/{h}")
        c.check(h in skill, f"scripts/{h} exists but SKILL.md never uses it")
    c.check("Task" in (skill.split("---")[1] if skill.count("---") >= 2 else ""),
            "frontmatter allowed-tools must include Task for the parallel round",
            note="allowed-tools declares Task (parallel fan-out is actionable)")


def _live_round(c: Checker, tmp: Path) -> None:
    """Walk the SKILL.md round against a real run dir, executing each command."""
    from cap_evolve import Budget, RunDir, harness

    # n=20 → ~5 val tasks, and a seed that already solves a few, so the paired delta
    # vector is MIXED (some tasks flip, some don't) and the paired SE is genuinely
    # non-zero — i.e. the check proves the real significance test, not its SE=0 fallback.
    adapter = SyntheticAdapter(n=20)
    seed = seed_capability_dir(tmp, level=3)
    run_dir = RunDir.create(tmp / ".capevolve", ts="chk", budget=Budget(max_iterations=5))
    harness.ensure_splits(adapter, run_dir, seed=0)
    harness.baseline(adapter, seed, run_dir=run_dir)
    R = str(run_dir.root)

    # A minimal project so spend.py can echo the free-text stop_condition.
    project = tmp / "project"
    project.mkdir(parents=True, exist_ok=True)
    (project / "capevolve.yaml").write_text(
        'stop_condition: "val mean >= 0.9 or $5 spent"\n', encoding="utf-8")

    # step 0 — the affordability readout
    sp = _run(c, "spend.py (pre-round)", [str(HERE / "spend.py"), "--run-dir", R,
                                          "--project", str(project)])
    if sp:
        c.check(sp.get("best_id") == "seed" and sp.get("stop") is False,
                f"spend.py did not report a fresh run: {sp}")
        c.check("val mean >= 0.9" in sp.get("stop_condition", ""),
                "spend.py did not echo the project's free-text stop_condition")
        c.check(sp.get("test_sealed") is True, "spend.py reported an unsealed test split",
                note="spend.py: best_val + spent + budget_exhausted + stop_condition in one call")

    # step 1 — the documented diagnose command
    dg = _run(c, "diagnose phase", [str(DIAGNOSE), "--run-dir", R, "--tag", "seed"])
    if dg is not None:
        c.check("kept_good" in dg, f"diagnose emitted no kept_good: {list(dg)}",
                note="diagnose gives clusters to fix + kept_good to protect")

    # step 2 — mkdir work + copy the best (the path RunDir does not create)
    work = Path(R) / "work"
    work.mkdir(parents=True, exist_ok=True)
    tag = "cand_1"
    shutil.copytree(run_dir.candidate_dir("seed"), work / tag)
    c.check((work / tag / "level.txt").is_file(),
            "copying $R/candidates/$BEST into $R/work/<tag> did not produce a working copy",
            note="$R/work/<tag> working-copy flow is real")
    (work / tag / "level.txt").write_text("12", encoding="utf-8")  # a genuine improvement

    # step 4 — full-val eval under the candidate's own tag, then the real gate
    harness.evaluate_candidate(adapter, work / tag, run_dir=run_dir, split="val",
                              n_trials=1, tag=tag)
    g = _run(c, "gate_check.py (accept)", [str(HERE / "gate_check.py"), "--run-dir", R,
                                           "--candidate", tag, "--k-se", "1.0"])
    if g:
        c.check(g.get("paired_n", 0) > 0,
                f"gate_check did not reach the PAIRED gate (paired_n={g.get('paired_n')})",
                note=f"paired gate reachable from the CLI: {g['gate']['reason']}")
        c.check(g.get("verdict") == "accept" and not g.get("regressions"),
                f"gate_check rejected a genuine improvement: {g}")

    # step 5 — commit moves best_id, iterations and the stall counter
    cm = _run(c, "commit.py (accept)", [str(HERE / "commit.py"), "--run-dir", R,
                                       "--candidate-id", tag, "--from-dir", str(work / tag),
                                       "--decision", "accept", "--val", "1.0",
                                       "--note", "raise coverage generally",
                                       "--optimizer-usd", "0.25"])
    if cm:
        c.check(cm.get("best_id") == tag, f"commit.py did not set best: {cm}")
        c.check(cm["spent"]["iterations"] == 1 and cm["spent"]["stall"] == 0
                and cm["spent"]["optimizer_usd"] == 0.25,
                f"commit.py under-recorded spend: {cm['spent']}",
                note="commit.py records iterations + stall + the proposer's own cost")
        c.check(run_dir.candidate_dir(tag).is_dir(), "commit.py did not snapshot the candidate")

    # a reject must advance the stall counter (what budget_exhausted's stall rule reads)
    rj = _run(c, "commit.py (reject)", [str(HERE / "commit.py"), "--run-dir", R,
                                        "--candidate-id", "cand_2", "--from-dir", str(work / tag),
                                        "--decision", "reject", "--note", "no gain"])
    if rj:
        c.check(rj["best_id"] == tag and rj["spent"]["stall"] == 1,
                f"reject changed best or did not advance stall: {rj}")

    c.check(not run_dir.read_splits().test_used,
            "the agent-optimize round consumed the sealed test split",
            note="test split sealed throughout the round")


def _no_regression(c: Checker, tmp: Path) -> None:
    """A mean gain that breaks a passing task must be vetoed."""
    run_dir, _ = temp_run_dir(tmp / "regr", ids=("a", "b", "c", "d"))
    # current: a passes, b/c/d fail  → mean 0.25
    for tid, r in (("a", 1.0), ("b", 0.0), ("c", 0.0), ("d", 0.0)):
        write_val_rollout(run_dir, tid, tag="cur", reward=r, feedback="fb")
    # candidate: a BREAKS, b/c pass  → mean 0.50 (a real mean gain, a real regression)
    for tid, r in (("a", 0.0), ("b", 1.0), ("c", 1.0), ("d", 0.0)):
        write_val_rollout(run_dir, tid, tag="regr", reward=r, feedback="fb")
    run_dir.set_best("cur")

    g = _run(c, "gate_check.py (no-regression)",
             [str(HERE / "gate_check.py"), "--run-dir", str(run_dir.root),
              "--candidate", "regr", "--mode", "strict"])
    if g:
        c.check(g.get("regressions") == ["a"] and g.get("verdict") == "reject",
                f"no-regression did not veto a mean gain that broke task 'a': {g}",
                note="no-regression veto is enforced by a real command, not prose")
        c.check(g["gate"]["accept"] is True,
                f"expected the raw gate to accept the mean gain: {g['gate']}")


def main() -> int:
    c = Checker("agent-optimize")
    _guard(c)
    _prose(c, SKILL_MD.read_text(encoding="utf-8"))
    tmp = Path(tempfile.mkdtemp(prefix="agent_optimize_chk_"))
    try:
        _live_round(c, tmp)
        _no_regression(c, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    c.note("agent-mode-only algorithm: every command SKILL.md documents is executed here")
    return c.emit()


if __name__ == "__main__":
    sys.exit(main())
