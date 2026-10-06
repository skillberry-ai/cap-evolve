"""cap-evolve adapter bridging the RFE-creator skill pipeline to agent-eval-harness.

Optimizes 7 Claude Code skills (rfe.speedrun, rfe.create, rfe.auto-fix, rfe.review,
rfe-feasibility-review, rfe.split, rfe.submit) against agent-eval-harness's RFE-creation
eval. Both projects are public but unlicensed
(github.com/opendatahub-io/rfe-creator, github.com/opendatahub-io/agent-eval-harness), so
neither their code nor their 25 eval cases are vendored here — ``ci/benchmarks/rfe-creator/
utils/fetch_data.sh`` clones both at run time (same convention as ``spreadsheetbench/
fetch_data.sh`` and the parsec local-shadow pattern).

Contract verified against source (not guessed):
  - 3 abstract methods + defaulted hooks: cap-evolve/core/cap_evolve/adapter.py:74-183
  - Task/Rollout/Score field names: cap-evolve/core/cap_evolve/types.py
  - ``score()`` runs INSIDE the ``live()`` context (harness.py:403,338) — the checkout
    (``ctx``) must still exist when ``score()`` is called.
  - The framework re-splits from ``tasks("all")`` itself (harness.py:130) — a split
    computed inside ``tasks()`` would be discarded; ``run_suite.sh`` pins the split via
    ``split_ids_file`` (no-holdout FIT, matching this bench's original config), so
    ``tasks()`` just returns everything.

Per-rollout pipeline (agent-eval-harness's REAL CLIs, no console script exists):
    preflight.py -> workspace.py --cases <id> -> execute.py -> collect.py
run inside a throwaway ``git worktree`` of the rfe-creator clone with the candidate's 7
skills overlaid onto ``.claude/skills/``. Scoring shells out to the harness's own
``python3 -m agent_eval.harbor.reward`` CLI (same interpreter, no sys.path surgery).

Env vars (all optional; ``ci_setup.sh``/``fetch_data.sh`` set sane CI defaults under
``$CAPEVOLVE_CI_CACHE``, so this adapter needs nothing set for a local run following
this template's own SETUP steps below):
    RFE_CREATOR_DIR       clone of opendatahub-io/rfe-creator
    AGENT_EVAL_HARNESS_DIR clone of opendatahub-io/agent-eval-harness (its scripts dir is
                          <this>/skills/eval-run/scripts)
    RFE_HARNESS_PY        python interpreter with agent_eval_harness + pyyaml installed
                          (default: the interpreter running cap-evolve itself)
    RFE_EVAL_CONFIG       merged eval config (upstream eval.yaml + this repo's small
                          reward_overlay.yaml — see fetch_data.sh); required
    RFE_WORKDIR_ROOT      scratch dir for the per-rollout git worktrees (default: a temp
                          dir under the system tmp root)
    RFE_RUNS_DIR          AGENT_EVAL_RUNS_DIR for the harness's own run records (default:
                          a temp dir under the system tmp root)
    RFE_CTX_CACHE         optional shared architecture-context cache dir; if unset,
                          rfe.review re-fetches architecture-context from GitHub on first
                          use (public, just slower)
    RFE_RUNNER_MODEL      the agent model under test (default: aws/claude-haiku-4-5)

KNOWN GAP: the Claude Code CLI has no ``--seed`` flag, so ``run_target``'s ``seed`` cannot
force an independent draw. ``num_trials`` still gets genuinely separate Claude Code
invocations (ordinary sampling variance) — see the module docstring in
cap-evolve/core/cap_evolve/adapter.py:74-183 ("Deterministic adapters can ignore it").

SETUP (standalone, outside CI):
  1. bash ci/benchmarks/rfe-creator/utils/fetch_data.sh <dest-dir>   # clones + merges config
  2. export RFE_CREATOR_DIR=<dest-dir>/rfe-creator
     export AGENT_EVAL_HARNESS_DIR=<dest-dir>/agent-eval-harness
     export RFE_EVAL_CONFIG=<dest-dir>/eval.merged.yaml
     export ANTHROPIC_BASE_URL=... ANTHROPIC_AUTH_TOKEN=...   # or ANTHROPIC_API_KEY
     # Running alongside a DIFFERENT optimizer model? Use the dedicated agent-only pair
     # instead (takes priority over the two vars above — see _harness_env()):
     #   export RFE_AGENT_BASE_URL=...  RFE_AGENT_API_KEY=...
  3. pip install -e <dest-dir>/agent-eval-harness pyyaml
  4. Copy this directory to .capevolve/project/adapters/
  5. Run: cap-evolve check && cap-evolve run
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

import yaml

from cap_evolve import CapabilityAdapter, Rollout, Score, Task

# --- layout (env-overridable; see module docstring) --------------------------
RFE_CREATOR = Path(os.environ.get("RFE_CREATOR_DIR", "")).resolve() if os.environ.get("RFE_CREATOR_DIR") else None
AGENT_EVAL_HARNESS = Path(os.environ.get("AGENT_EVAL_HARNESS_DIR", "")).resolve() if os.environ.get("AGENT_EVAL_HARNESS_DIR") else None
HARNESS_SCRIPTS = (AGENT_EVAL_HARNESS / "skills" / "eval-run" / "scripts") if AGENT_EVAL_HARNESS else None
CASES_DIR = (RFE_CREATOR / "eval" / "dataset" / "cases") if RFE_CREATOR else None
EVAL_CONFIG = Path(os.environ["RFE_EVAL_CONFIG"]).resolve() if os.environ.get("RFE_EVAL_CONFIG") else None
HARNESS_PY = Path(os.environ.get("RFE_HARNESS_PY", sys.executable)).resolve()

_tmp_root = Path(tempfile.gettempdir()) / "cap-evolve-rfe-creator"
WORKDIR_ROOT = Path(os.environ.get("RFE_WORKDIR_ROOT", str(_tmp_root / "workdir")))
RUNS_DIR = Path(os.environ.get("RFE_RUNS_DIR", str(_tmp_root / "runs")))
CTX_CACHE = Path(os.environ["RFE_CTX_CACHE"]).resolve() if os.environ.get("RFE_CTX_CACHE") else None

RUNNER_MODEL = os.environ.get("RFE_RUNNER_MODEL", "aws/claude-haiku-4-5")
SKILL_TIMEOUT_S = int(os.environ.get("RFE_SKILL_TIMEOUT_S", "900"))
SKILL_MAX_BUDGET_USD = float(os.environ.get("RFE_SKILL_MAX_BUDGET_USD", "8.0"))

# The 7 in-scope skill dirs (must match capevolve.yaml::capability_path contents).
SKILL_NAMES = (
    "rfe.speedrun", "rfe.create", "rfe.auto-fix", "rfe.review",
    "rfe-feasibility-review", "rfe.split", "rfe.submit",
)


def _check_layout() -> None:
    missing = [name for name, val in (
        ("RFE_CREATOR_DIR", RFE_CREATOR), ("AGENT_EVAL_HARNESS_DIR", AGENT_EVAL_HARNESS),
        ("RFE_EVAL_CONFIG", EVAL_CONFIG),
    ) if val is None or not val.exists()]
    if missing:
        raise RuntimeError(
            "rfe_creator adapter: missing/unset " + ", ".join(missing) +
            " — run ci/benchmarks/rfe-creator/utils/fetch_data.sh first (see adapter.py docstring)."
        )


def _run(cmd: list, *, cwd: Path, env: dict, timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True,
                          text=True, timeout=timeout)


def _harness_env() -> dict:
    """Env for the harness subprocess tree (preflight/workspace/execute/collect, which in
    turn shells out to the `claude` CLI). Starts from the full parent env, then lets
    RFE_AGENT_BASE_URL/RFE_AGENT_API_KEY override ANTHROPIC_BASE_URL/ANTHROPIC_AUTH_TOKEN
    when set — a caller that also runs an optimizer model (e.g. cap-evolve's own
    run_suite.sh, invoking `claude` for OPTIMIZER_MODEL) may already have those two vars
    exported process-wide for THAT model, and a plain dict(os.environ) copy would silently
    hand the sandboxed agent the optimizer's credentials instead of its own."""
    env = dict(os.environ)
    if os.environ.get("RFE_AGENT_BASE_URL"):
        env["ANTHROPIC_BASE_URL"] = os.environ["RFE_AGENT_BASE_URL"]
    if os.environ.get("RFE_AGENT_API_KEY"):
        env["ANTHROPIC_AUTH_TOKEN"] = os.environ["RFE_AGENT_API_KEY"]
    env["AGENT_EVAL_RUNS_DIR"] = str(RUNS_DIR)
    # rfe-creator's own scripts (invoked BY the Claude Code agent as e.g.
    # `python3 scripts/frontmatter.py ...`) need pyyaml, which the system default python3
    # may lack. Prepend the harness interpreter's bin dir so any `python3` resolved by a
    # subprocess launched further down this env's tree (execute.py -> claude --print -> the
    # skill's own script calls) finds it.
    env["PATH"] = f"{HARNESS_PY.parent}:{env.get('PATH', '')}"
    return env


class Adapter(CapabilityAdapter):

    # ---- tasks -------------------------------------------------------------

    def tasks(self, split: str) -> list[Task]:
        """All eval cases, for every split — the framework itself splits from this via
        ``split_ids_file`` (see module docstring). Stable: sorted directory scan."""
        _check_layout()
        out = []
        for case_dir in sorted(p for p in CASES_DIR.iterdir() if p.is_dir()):
            input_yaml = yaml.safe_load((case_dir / "input.yaml").read_text(encoding="utf-8")) or {}
            ann_path = case_dir / "annotations.yaml"
            annotations = yaml.safe_load(ann_path.read_text(encoding="utf-8")) or {} if ann_path.exists() else {}
            out.append(Task(id=case_dir.name, input=input_yaml, metadata=annotations))
        return out

    # ---- running -------------------------------------------------------------

    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout:
        """Run ONE case through the real preflight -> workspace -> execute -> collect
        pipeline, inside the live checkout ``ctx``. Never raises: any infra failure
        (timeout, missing files, non-zero exit) becomes ``Rollout.error`` so cap-evolve
        classifies it as uncontrollable noise, not a capability defect."""
        ctx = Path(ctx)
        run_id = f"rfe-{task.id}-s{seed}-{uuid.uuid4().hex[:8]}"
        cfg_path = ctx / "eval.yaml"
        env = _harness_env()

        def infra_error(msg: str) -> Rollout:
            return Rollout(task_id=task.id, error=msg, metadata={"run_id": run_id})

        try:
            pre = _run([str(HARNESS_PY), str(HARNESS_SCRIPTS / "preflight.py"),
                       "--config", str(cfg_path), "--run-id", run_id,
                       "--clean", "--force"],
                      cwd=ctx, env=env, timeout=60)
            if pre.returncode not in (0, 1):  # 1 == "was dirty, now cleaned" is fine
                return infra_error(f"preflight failed (rc={pre.returncode}): {pre.stderr[-800:]}")

            ws = _run([str(HARNESS_PY), str(HARNESS_SCRIPTS / "workspace.py"),
                      "--config", str(cfg_path), "--run-id", run_id,
                      "--cases", task.id],
                     cwd=ctx, env=env, timeout=120)
            if ws.returncode != 0:
                return infra_error(f"workspace.py failed (rc={ws.returncode}): {ws.stderr[-800:]}")
            workspace = next((line.split("WORKSPACE:", 1)[1].strip()
                              for line in ws.stdout.splitlines() if line.startswith("WORKSPACE:")), None)
            if not workspace:
                return infra_error(f"workspace.py printed no WORKSPACE: line: {ws.stdout[-800:]}")

            run_dir = RUNS_DIR / f"rfe-{task.id}" / run_id
            ex = _run([str(HARNESS_PY), str(HARNESS_SCRIPTS / "execute.py"),
                      "--workspace", workspace, "--skill", "rfe.speedrun",
                      "--skill-args", "--headless --dry-run --input batch.yaml",
                      "--model", RUNNER_MODEL, "--subagent-model", RUNNER_MODEL,
                      "--output", str(run_dir), "--config", str(cfg_path),
                      "--run-id", run_id, "--timeout", str(SKILL_TIMEOUT_S),
                      "--max-budget", str(SKILL_MAX_BUDGET_USD)],
                     cwd=ctx, env=env, timeout=SKILL_TIMEOUT_S + 120)
            # execute.py's own exit code mirrors the SKILL's exit code, not infra health —
            # a skill that legitimately fails a case is a rollout to SCORE, not an infra
            # error. Only a missing run_result.json means the harness itself never ran.
            run_result_path = run_dir / "run_result.json"
            if not run_result_path.exists():
                return infra_error(f"execute.py produced no run_result.json (rc={ex.returncode}): "
                                   f"{ex.stderr[-800:]}")
            run_result = json.loads(run_result_path.read_text(encoding="utf-8"))

            co = _run([str(HARNESS_PY), str(HARNESS_SCRIPTS / "collect.py"),
                      "--config", str(cfg_path), "--workspace", workspace,
                      "--output", str(run_dir)],
                     cwd=ctx, env=env, timeout=60)
            if co.returncode != 0:
                return infra_error(f"collect.py failed (rc={co.returncode}): {co.stderr[-800:]}")

            case_dir = run_dir / "cases" / task.id
            if not case_dir.is_dir():
                return infra_error(f"collect.py produced no cases/{task.id}/ under {run_dir}")

            # pipeline_flow judge reads stdout.log from the case dir first — stash a copy.
            stdout_log = run_dir / "stdout.log"
            if stdout_log.exists():
                shutil.copy2(stdout_log, case_dir / "stdout.log")

            return Rollout(
                task_id=task.id,
                output=str(case_dir),
                trace=(run_result.get("per_case", {}) or {}).get(task.id)
                      or (ex.stdout[-4000:] if ex.stdout else None),
                cost_usd=float(run_result.get("cost_usd") or 0.0),
                metadata={"config": str(cfg_path), "run_id": run_id, "run_dir": str(run_dir)},
            )
        except subprocess.TimeoutExpired as e:
            return infra_error(f"timed out: {e}")
        except Exception as e:  # noqa: BLE001 — never let an infra hiccup crash the loop
            return infra_error(f"{type(e).__name__}: {e}")

    # ---- scoring ---------------------------------------------------------

    def score(self, task: Task, rollout: Rollout) -> Score:
        if rollout.error:
            return Score(task_id=task.id, reward=0.0,
                        feedback=f"infra error: {rollout.error}", n=0,
                        raw={"errored": True})

        case_dir = Path(rollout.output)
        cfg_path = rollout.metadata.get("config")
        out_dir = case_dir / "_reward"
        try:
            subprocess.run(
                [str(HARNESS_PY), "-m", "agent_eval.harbor.reward",
                 "--config", str(cfg_path), "--case-dir", str(case_dir),
                 "--run-id", rollout.metadata.get("run_id", task.id),
                 "--out-dir", str(out_dir)],
                cwd=str(RFE_CREATOR), capture_output=True, text=True, timeout=300,
            )
            payload = json.loads((out_dir / "judges.json").read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001 — scoring failure, not an infra Rollout.error
            return Score(task_id=task.id, reward=0.0,
                        feedback=f"reward computation failed: {type(e).__name__}: {e}",
                        n=0, raw={"errored": True})

        reward = float(payload.get("reward") or 0.0)
        per_judge = payload.get("per_judge") or {}
        feedback = "; ".join(
            f"{name}: {info['rationale']}" for name, info in sorted(per_judge.items())
            if info.get("rationale")
        )
        return Score(task_id=task.id, reward=reward, feedback=feedback,
                    trial_rewards=[reward], raw={"per_judge": per_judge})

    # ---- making the candidate live -----------------------------------------

    @contextmanager
    def live(self, candidate_dir: Path):
        """A throwaway ``git worktree`` of the rfe-creator clone with the candidate's 7
        skills overlaid onto ``.claude/skills/``, plus the merged eval config (so the
        harness's cwd/config-dir-relative paths resolve inside the checkout) and the
        optional shared architecture-context cache (symlinked in if present).

        ``git worktree`` (not ``shutil.copytree``) because rfe-creator is a git repo — a
        worktree checkout is fast and tracked-files-only. Removed on exit;
        ``RFE_WORKDIR_ROOT`` is pruned of stale worktrees on entry so repeated runs cannot
        grow it unboundedly.
        """
        _check_layout()
        candidate_dir = Path(candidate_dir)
        WORKDIR_ROOT.mkdir(parents=True, exist_ok=True)
        _prune_stale_worktrees()

        checkout = WORKDIR_ROOT / f"wt-{uuid.uuid4().hex[:12]}"
        print(f"[adapter.live] worktree: {checkout}", file=sys.stderr)
        used_worktree = True
        wt = subprocess.run(["git", "-C", str(RFE_CREATOR), "worktree", "add",
                            "--detach", str(checkout), "HEAD"],
                           capture_output=True, text=True, timeout=60)
        if wt.returncode != 0:
            used_worktree = False
            print(f"[adapter.live] worktree add failed ({wt.stderr.strip()}); "
                 f"falling back to copytree", file=sys.stderr)
            shutil.copytree(RFE_CREATOR, checkout,
                            ignore=shutil.ignore_patterns(".git"))

        try:
            for name in SKILL_NAMES:
                src = candidate_dir / name
                if not src.is_dir():
                    continue
                dst = checkout / ".claude" / "skills" / name
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)

            shutil.copy2(EVAL_CONFIG, checkout / "eval.yaml")

            if CTX_CACHE and CTX_CACHE.is_dir():
                dst_ctx = checkout / ".context"
                if not dst_ctx.exists():
                    dst_ctx.symlink_to(CTX_CACHE)
            else:
                print("[adapter.live] no shared architecture-context cache set "
                     "(RFE_CTX_CACHE) — rfe.review will re-fetch it from GitHub on "
                     "first use", file=sys.stderr)

            yield checkout
        finally:
            if used_worktree:
                subprocess.run(["git", "-C", str(RFE_CREATOR), "worktree", "remove",
                               "--force", str(checkout)],
                              capture_output=True, text=True, timeout=60)
            else:
                shutil.rmtree(checkout, ignore_errors=True)

    def runner_model(self) -> str:
        return RUNNER_MODEL


def _prune_stale_worktrees() -> None:
    """Best-effort GC so ``RFE_WORKDIR_ROOT`` cannot grow unboundedly across many runs.

    Removes ``wt-*`` dirs older than 6h that ``git worktree`` no longer lists as live (a
    prior crash left the checkout but not the worktree registration) — a live one is left
    alone even if old (a slow rollout is still running).
    """
    if not WORKDIR_ROOT.is_dir() or RFE_CREATOR is None:
        return
    listed = subprocess.run(["git", "-C", str(RFE_CREATOR), "worktree", "list", "--porcelain"],
                            capture_output=True, text=True, timeout=30)
    live_paths = {line.split(" ", 1)[1] for line in listed.stdout.splitlines()
                  if line.startswith("worktree ")}
    cutoff = time.time() - 6 * 3600
    for d in WORKDIR_ROOT.glob("wt-*"):
        if str(d.resolve()) in live_paths:
            continue
        try:
            if d.stat().st_mtime < cutoff:
                shutil.rmtree(d, ignore_errors=True)
        except OSError:
            continue
