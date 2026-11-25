"""cap-evolve adapter for fullsend-ai/rfe-creator, scored by its own agent-eval-harness evals.

One adapter for BOTH work-item types the ``rfe-speedrun`` pipeline handles: RFEs
(``eval.yaml``, ``eval/dataset/cases``, 28 cases) and Initiatives (``eval-initiative.yaml``,
``eval/initiative-dataset/cases``, 23 cases). Task ids carry the type: ``rfe-case-021-…``,
``initiative-case-022-…`` (no ``/``: cap-evolve names rollout files after the task id). Both pipelines share the skills under optimization, so a run
over both catches an edit that helps one type and breaks the other.

The editable capability (the seed dir ``run_suite.sh`` / SETUP builds from the clone):

    skills/<name>/...              the six real pipeline skills (rfe-speedrun, rfe-create,
                                   rfe-review, rfe-auto-fix, rfe-split, rfe-submit)
    types/<type>/prompts/*.md      the per-type create/review/revise/split rules

Everything else is read-only and taken from the clone as-is: the ``rfe.*`` compatibility
alias skills, ``scripts/``, the type descriptors, the vendored rubric (``assess-rfe``),
the architecture context and BOTH eval configs (the judges a candidate is scored by).

Per-rollout pipeline (agent-eval-harness's own CLIs), inside a throwaway ``git worktree``
of the rfe-creator clone with the candidate overlaid:
    workspace.py --cases <id> -> execute.py -> collect.py  (each run in its own workspace)
then ``python -m agent_eval.harbor.reward`` scores the case with every judge of the
type's own eval config. The adapter, not the harness's reward formula, composes the
scalar reward — see ``compose_reward`` — because only the adapter knows which checks
APPLY to a case (a check with no annotation for it passes vacuously, and must not count
as a free 1.0).

Feedback is the FULL text of every judge, one labelled section each, never shortened:
the optimizer reads the judges' own words.

Env vars:
    RFE_CREATOR_DIR        clone of fullsend-ai/rfe-creator, bootstrapped once (see SETUP)
    AGENT_EVAL_HARNESS_DIR clone of fullsend-ai/agent-eval-harness
    RFE_HARNESS_PY         python with agent-eval-harness + anthropic + pyyaml installed
                           (default: the interpreter running cap-evolve)
    RFE_EVAL_OVERLAY       optional YAML deep-merged onto BOTH eval configs (e.g. models)
    RFE_RUNNER_MODEL       model under test, for skill and subagents (default: the
                           eval config's models.skill)
    RFE_JUDGE_MODEL        LLM-judge model (default: the eval config's models.judge)
    RFE_EFFORT             runner effort (default: the eval config's runner.effort)
    RFE_SKILL_TIMEOUT_S    per-case pipeline timeout, seconds (default 2700)
    RFE_SKILL_MAX_BUDGET_USD per-case pipeline cost cap (default 10)
    RFE_WORKDIR_ROOT, RFE_RUNS_DIR  scratch dirs (default: under the system tmp root)
    RFE_AGENT_BASE_URL / RFE_AGENT_API_KEY  gateway + key for the RUNNER only (the LLM
                           judges keep ANTHROPIC_*), e.g. a free RITS model behind another
                           gateway, or when the process env carries the optimizer's

SETUP (standalone):
  1. bash ci/benchmarks/rfe-creator/utils/fetch_data.sh <dest>   # clones + bootstraps
  2. export RFE_CREATOR_DIR=<dest>/rfe-creator AGENT_EVAL_HARNESS_DIR=<dest>/agent-eval-harness
  3. python benchmarks/rfe_creator/template/adapter.py --make-seed <capability_dir>
  4. Copy this file to .capevolve/project/adapters/ and run cap-evolve.
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

# --- layout -------------------------------------------------------------------
def _env_path(name: str) -> Path | None:
    v = os.environ.get(name)
    return Path(v).resolve() if v else None


RFE_CREATOR = _env_path("RFE_CREATOR_DIR")
AGENT_EVAL_HARNESS = _env_path("AGENT_EVAL_HARNESS_DIR")
HARNESS_SCRIPTS = AGENT_EVAL_HARNESS / "skills" / "eval-run" / "scripts" if AGENT_EVAL_HARNESS else None
HARNESS_PY = Path(os.environ.get("RFE_HARNESS_PY", sys.executable))
EVAL_OVERLAY = _env_path("RFE_EVAL_OVERLAY")

_tmp_root = Path(tempfile.gettempdir()) / "cap-evolve-rfe-creator"
WORKDIR_ROOT = Path(os.environ.get("RFE_WORKDIR_ROOT", str(_tmp_root / "workdir")))
RUNS_DIR = Path(os.environ.get("RFE_RUNS_DIR", str(_tmp_root / "runs")))

RUNNER_MODEL = os.environ.get("RFE_RUNNER_MODEL", "")
JUDGE_MODEL = os.environ.get("RFE_JUDGE_MODEL", "")
EFFORT = os.environ.get("RFE_EFFORT", "")
SKILL_TIMEOUT_S = int(os.environ.get("RFE_SKILL_TIMEOUT_S", "2700"))
SKILL_MAX_BUDGET_USD = float(os.environ.get("RFE_SKILL_MAX_BUDGET_USD", "10.0"))

# type -> (eval config in the clone, dataset dir, quality judge)
TYPES = {
    "rfe": ("eval.yaml", "eval/dataset/cases", "rfe_quality"),
    "initiative": ("eval-initiative.yaml", "eval/initiative-dataset/cases", "initiative_quality"),
}
SKILL = "rfe-speedrun"
# The capability: the real skills (not the rfe.* aliases) and the per-type prompt rules.
SKILL_NAMES = ("rfe-speedrun", "rfe-create", "rfe-review", "rfe-auto-fix", "rfe-split", "rfe-submit")

# --- reward -------------------------------------------------------------------
# A failed one of these means the pipeline itself broke (nothing usable was produced).
GATE_CHECKS = ("files_exist", "frontmatter_valid", "run_report_exists", "pipeline_flow")
# Behavior checks. Those in CONDITIONAL count only on a case they actually test.
BEHAVIOR_CHECKS = ("recommendation_consistency", "revision_flag_consistency",
                   "architecture_context_used", "classification_signal",
                   "needs_attention_expectation", "revision_coverage",
                   "first_review_expectation", "evidence_fidelity")
# Judges reported as metrics only: never in the reward, never in the optimizer's feedback.
# self_score_calibration (whether the pipeline's own review scores are accurate) is kept
# out on purpose: when the quality judge graded it, optimized candidates lowered their own
# scores, which left review tables inconsistent and triggered needless splits (full-v2).
DIAGNOSTIC_JUDGES = ("self_score_calibration",)
# A 1-5 judge score -> 0-1, convex so the top step (4 -> 5) is worth the most: most cases
# already score 4-5, and a linear 0.75 -> 1.0 step hides that gap in trial noise.
SCORE_MAP = {5: 1.0, 4: 0.6, 3: 0.3, 2: 0.1, 1: 0.0}
QUALITY_WEIGHTS = {"quality": 3.0, "revision_quality": 1.0}   # "quality" = the type's own judge
# Per failed check, the reward is multiplied by the factor: the rare behavior failures the
# cases are built to test cost more than the always-applicable consistency checks.
KEY_CHECKS = ("classification_signal", "needs_attention_expectation", "revision_coverage",
              "first_review_expectation", "evidence_fidelity")
KEY_CHECK_FACTOR, OTHER_CHECK_FACTOR = 0.85, 0.95
GATE_FACTOR = 0.5   # a broken pipeline halves the reward instead of zeroing it, so the case still ranks


def applicable_checks(annotations: dict) -> list[str]:
    """The behavior checks that TEST this case (the rest pass it vacuously)."""
    out = ["recommendation_consistency", "revision_flag_consistency", "architecture_context_used"]
    if annotations.get("expected_classification") is not None:
        out.append("classification_signal")
    if annotations.get("expected_needs_attention") is not None:
        out.append("needs_attention_expectation")
    if "revision-expected" in (annotations.get("tags") or []):
        out.append("revision_coverage")
    # Newer rfe-creator configs: each passes vacuously where it does not apply (a pass never
    # changes the product), so both always count when the config defines them.
    out += ["first_review_expectation", "evidence_fidelity"]
    return out


def judge_ranges(cfg: dict) -> dict:
    """``{judge: (lo, hi)}`` for every judge of the eval config that declares a score_range."""
    return {j["name"]: tuple(float(x) for x in j["score_range"])
            for j in (cfg.get("judges") or []) if j.get("name") and j.get("score_range")}


def _as01(rec: dict | None, rng: tuple | None = None) -> float | None:
    """A check -> 1.0/0.0; a 1-5 judge score -> SCORE_MAP; a judge on any other declared
    range (e.g. rfe-creator's 0-10 per-criterion quality judge) -> linear over that range.
    None when the judge gave no value."""
    v = (rec or {}).get("value")
    if v is None:
        return None
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if rng and tuple(rng) != (1.0, 5.0) and rng[1] > rng[0]:
        return max(0.0, min(1.0, (float(v) - rng[0]) / (rng[1] - rng[0])))
    return SCORE_MAP[max(1, min(5, round(float(v))))]


def compose_reward(per_judge: dict, quality_judge: str, annotations: dict,
                   ranges: dict | None = None) -> tuple[float, dict]:
    """``gate x penalty x quality`` -> (reward, components).

    quality   weighted mean of the type's quality judge (x3) and revision_quality (x1),
              each mapped by ``_as01`` over its declared range (``ranges``); a judge with no
              value is left out.
    penalty   KEY_CHECK_FACTOR per failed applicable KEY_CHECKS check, OTHER_CHECK_FACTOR per
              any other failed check (gate checks included).
    gate      GATE_FACTOR if any GATE_CHECKS judge failed, else 1.
    A case with no quality value is scored on penalty x gate alone; a case with no value
    anywhere scores 0 (it was not measured — the caller marks it errored).
    """
    gate_failed = [g for g in GATE_CHECKS if _as01(per_judge.get(g)) == 0.0]
    ranges = ranges or {}
    q_names = [(quality_judge if k == "quality" else k, w) for k, w in QUALITY_WEIGHTS.items()]
    q_parts = [(w, _as01(per_judge.get(n), ranges.get(n))) for n, w in q_names]
    q_parts = [(w, v) for w, v in q_parts if v is not None]
    quality = sum(w * v for w, v in q_parts) / sum(w for w, _ in q_parts) if q_parts else None
    checks = {c: _as01(per_judge.get(c)) for c in (*GATE_CHECKS, *applicable_checks(annotations))}
    checks = {c: v for c, v in checks.items() if v is not None}
    failed = [c for c, v in checks.items() if v == 0.0]
    penalty = 1.0
    for c in failed:
        penalty *= KEY_CHECK_FACTOR if c in KEY_CHECKS else OTHER_CHECK_FACTOR
    gate = GATE_FACTOR if gate_failed else 1.0
    if quality is None and not checks:
        reward = 0.0
    else:
        reward = gate * penalty * (1.0 if quality is None else quality)
    return reward, {"gate": gate, "gate_failed": gate_failed, "quality": quality,
                    "penalty": penalty if checks else None, "failed_checks": failed}


def format_feedback(per_judge: dict, quality_judge: str, annotations: dict, comp: dict,
                    ranges: dict | None = None) -> str:
    """Every judge's FULL rationale, one labelled section each, worst news first."""
    def label(name: str, rec: dict) -> str:
        v = rec.get("value")
        if rec.get("error"):
            return f"{name} — ERROR (not scored)"
        if v is None:
            return f"{name} — skipped"
        samples = (rec.get("stability") or {}).get("samples")
        many = f" (judge sampled {samples}x)" if samples and samples > 1 else ""
        if isinstance(v, bool):
            return f"{name} — {'PASS' if v else 'FAIL'}{many}"
        top = (ranges or {}).get(name, (1.0, 5.0))[1]
        return f"{name} — {v:g}/{top:g}{many}"

    applicable = set(applicable_checks(annotations))
    order = ([quality_judge, "revision_quality"] + list(GATE_CHECKS)
             + [c for c in BEHAVIOR_CHECKS if c in applicable]
             + [c for c in BEHAVIOR_CHECKS if c not in applicable])
    order += sorted(k for k in per_judge if k not in order)
    order = [k for k in order if k not in DIAGNOSTIC_JUDGES]
    q, pen = comp.get("quality"), comp.get("penalty")
    head = (f"reward parts: gate={'FAILED (' + ', '.join(comp['gate_failed']) + ')' if comp['gate_failed'] else 'ok'}"
            f", quality={'n/a' if q is None else f'{q:.3f}'}, check penalty={'n/a' if pen is None else f'{pen:.3f}'}"
            + (f" (failed: {', '.join(comp['failed_checks'])})" if comp.get("failed_checks") else ""))
    out = [head]
    for name in order:
        rec = per_judge.get(name)
        if rec is None:
            continue
        note = "" if name in applicable or name not in BEHAVIOR_CHECKS else " (not applicable to this case; not in the reward)"
        body = str(rec.get("error") or rec.get("rationale") or "").strip()
        out.append(f"### {label(name, rec)}{note}\n{body}")
    return "\n\n".join(out)


# --- helpers ------------------------------------------------------------------
def _check_layout() -> None:
    missing = [n for n, p in (("RFE_CREATOR_DIR", RFE_CREATOR), ("AGENT_EVAL_HARNESS_DIR", AGENT_EVAL_HARNESS))
               if p is None or not p.exists()]
    if missing:
        raise RuntimeError("rfe_creator adapter: missing/unset " + ", ".join(missing)
                           + " — run ci/benchmarks/rfe-creator/utils/fetch_data.sh (see the docstring).")
    if not (RFE_CREATOR / ".context" / "assess-rfe").is_dir():
        raise RuntimeError(f"{RFE_CREATOR} is not bootstrapped (no .context/assess-rfe) — run "
                           "fetch_data.sh, which runs scripts/bootstrap.sh for both types once.")


def _split_id(task_id: str) -> tuple[str, str]:
    for typ in TYPES:
        if task_id.startswith(typ + "-case-"):
            return typ, task_id[len(typ) + 1:]
    raise ValueError(f"task id {task_id!r} is not <type>-<case>")


def _deep_merge(dst: dict, src: dict) -> dict:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = v
    return dst


def _run(cmd: list, *, cwd: Path, env: dict, timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run([str(c) for c in cmd], cwd=str(cwd), env=env, capture_output=True,
                          text=True, timeout=timeout)


def _harness_env(*, runner: bool = True) -> dict:
    """The full parent env, the bootstrap skipped (the checkout was bootstrapped once; a
    per-rollout clone from GitHub is slow and flaky), and the harness interpreter first on
    PATH (the skills' scripts need pyyaml). With ``runner`` (the pipeline run, not the
    judges) the runner's own RFE_AGENT_* credentials replace ANTHROPIC_*: the model under
    test may sit behind a different gateway than the judge model."""
    env = dict(os.environ)
    if runner and os.environ.get("RFE_AGENT_BASE_URL"):
        env["ANTHROPIC_BASE_URL"] = os.environ["RFE_AGENT_BASE_URL"]
    if runner and os.environ.get("RFE_AGENT_API_KEY"):
        env["ANTHROPIC_AUTH_TOKEN"] = os.environ["RFE_AGENT_API_KEY"]
    env["AGENT_EVAL_RUNS_DIR"] = str(RUNS_DIR)
    env["RFE_SKIP_BOOTSTRAP"] = "1"
    env["PATH"] = f"{HARNESS_PY.parent}:{env.get('PATH', '')}"
    return env


def make_seed(dest: Path) -> None:
    """Copy the editable capability out of the clone into ``dest`` (the seed)."""
    _check_layout()
    dest = Path(dest)
    for name in SKILL_NAMES:
        shutil.copytree(RFE_CREATOR / ".claude" / "skills" / name, dest / "skills" / name, dirs_exist_ok=True)
    for typ in TYPES:
        shutil.copytree(RFE_CREATOR / "types" / typ / "prompts", dest / "types" / typ / "prompts",
                        dirs_exist_ok=True)


class Adapter(CapabilityAdapter):

    # ---- tasks -------------------------------------------------------------

    def tasks(self, split: str) -> list[Task]:
        """Every case of both types; the framework splits via ``split_ids_file``."""
        _check_layout()
        out = []
        for typ, (_, ds, _) in TYPES.items():
            for case_dir in sorted(p for p in (RFE_CREATOR / ds).iterdir() if p.is_dir()):
                inp = yaml.safe_load((case_dir / "input.yaml").read_text(encoding="utf-8")) or {}
                ann_p = case_dir / "annotations.yaml"
                ann = (yaml.safe_load(ann_p.read_text(encoding="utf-8")) or {}) if ann_p.exists() else {}
                out.append(Task(id=f"{typ}-{case_dir.name}", input=inp,
                                metadata={"type": typ, "annotations": ann}))
        return out

    # ---- running -------------------------------------------------------------

    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout:
        """One case through workspace -> execute -> collect, in the live checkout.
        Never raises: an infra failure becomes ``Rollout.error``."""
        ctx = Path(ctx)
        typ, case = _split_id(task.id)
        cfg = ctx / TYPES[typ][0]
        run_id = f"{typ}-{case[:8]}-s{seed}-{uuid.uuid4().hex[:8]}"
        env = _harness_env()

        def infra_error(msg: str) -> Rollout:
            return Rollout(task_id=task.id, output=None, error=msg, metadata={"run_id": run_id})

        try:
            # No preflight.py --clean here: it wipes the SHARED checkout's tmp/, and with
            # several workers rollouts run concurrently in one live() checkout. Each run's
            # pipeline state lives in its own /tmp/agent-eval/<run_id> workspace instead.
            ws = _run([HARNESS_PY, HARNESS_SCRIPTS / "workspace.py", "--config", cfg, "--run-id", run_id,
                       "--cases", case], cwd=ctx, env=env, timeout=120)
            if ws.returncode != 0:
                return infra_error(f"workspace.py failed (rc={ws.returncode}): {ws.stderr[-800:]}")
            workspace = next((ln.split("WORKSPACE:", 1)[1].strip() for ln in ws.stdout.splitlines()
                              if ln.startswith("WORKSPACE:")), None)
            if not workspace:
                return infra_error(f"workspace.py printed no WORKSPACE: line: {ws.stdout[-800:]}")

            run_dir = RUNS_DIR / typ / case / run_id
            cmd = [HARNESS_PY, HARNESS_SCRIPTS / "execute.py", "--workspace", workspace, "--skill", SKILL,
                   "--skill-args", f"--headless --dry-run --input batch.yaml --type {typ}",
                   "--output", run_dir, "--config", cfg, "--run-id", run_id,
                   "--timeout", SKILL_TIMEOUT_S, "--max-budget", SKILL_MAX_BUDGET_USD]
            if RUNNER_MODEL:
                cmd += ["--model", RUNNER_MODEL, "--subagent-model", RUNNER_MODEL]
            if EFFORT:
                cmd += ["--effort", EFFORT]
            ex = _run(cmd, cwd=ctx, env=env, timeout=SKILL_TIMEOUT_S + 300)
            # execute.py's exit code mirrors the SKILL's, not infra health; only a missing
            # run_result.json means the harness itself never ran.
            rr_path = run_dir / "run_result.json"
            if not rr_path.exists():
                return infra_error(f"execute.py produced no run_result.json (rc={ex.returncode}): {ex.stderr[-800:]}")
            run_result = json.loads(rr_path.read_text(encoding="utf-8"))

            co = _run([HARNESS_PY, HARNESS_SCRIPTS / "collect.py", "--config", cfg, "--workspace", workspace,
                       "--output", run_dir], cwd=ctx, env=env, timeout=120)
            if co.returncode != 0:
                return infra_error(f"collect.py failed (rc={co.returncode}): {co.stderr[-800:]}")
            case_dir = run_dir / "cases" / case
            if not case_dir.is_dir():
                return infra_error(f"collect.py produced no cases/{case}/ under {run_dir}")
            # pipeline_flow reads stdout.log from the case dir first.
            if (run_dir / "stdout.log").exists():
                shutil.copy2(run_dir / "stdout.log", case_dir / "stdout.log")
            # The workspace (/tmp/agent-eval/<run_id>) is collected now; drop it so a long
            # run does not fill the disk with one ~MB-sized pipeline tree per rollout.
            shutil.rmtree(workspace, ignore_errors=True)

            return Rollout(
                task_id=task.id, output=str(case_dir),
                trace=str(run_dir / "stdout.log") if (run_dir / "stdout.log").exists() else None,
                cost_usd=float(run_result.get("cost_usd") or 0.0),
                metadata={"config": str(cfg), "run_id": run_id, "run_dir": str(run_dir), "type": typ},
            )
        except subprocess.TimeoutExpired as e:
            return infra_error(f"timed out: {e}")
        except Exception as e:  # noqa: BLE001 — an infra hiccup must not crash the loop
            return infra_error(f"{type(e).__name__}: {e}")

    # ---- scoring ---------------------------------------------------------

    def score(self, task: Task, rollout: Rollout) -> Score:
        if rollout.error:
            return Score(task_id=task.id, reward=0.0, feedback=f"infra error: {rollout.error}", n=0,
                         raw={"errored": True})
        typ, _ = _split_id(task.id)
        quality_judge = TYPES[typ][2]
        annotations = (task.metadata or {}).get("annotations") or {}
        case_dir = Path(rollout.output)
        out_dir = case_dir / "_reward"
        try:
            p = subprocess.run(
                [str(HARNESS_PY), "-m", "agent_eval.harbor.reward", "--config", rollout.metadata["config"],
                 "--case-dir", str(case_dir), "--run-id", rollout.metadata.get("run_id", task.id),
                 "--out-dir", str(out_dir)],
                cwd=str(Path(rollout.metadata["config"]).parent), env=_harness_env(runner=False),
                capture_output=True, text=True, timeout=1800)
            payload = json.loads((out_dir / "judges.json").read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001 — scoring failure: not measured
            tail = locals().get("p")
            return Score(task_id=task.id, reward=0.0,
                         feedback=f"reward computation failed: {type(e).__name__}: {e}"
                                  + (f"\n{tail.stderr[-2000:]}" if tail is not None else ""),
                         n=0, raw={"errored": True})

        per_judge = payload.get("per_judge") or {}
        try:
            cfg = yaml.safe_load(Path(rollout.metadata["config"]).read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            cfg = {}
        ranges = judge_ranges(cfg)
        reward, comp = compose_reward(per_judge, quality_judge, annotations, ranges)
        unmeasured = comp["quality"] is None and comp["penalty"] is None
        metrics = [{"name": "reward", "value": reward, "direction": "higher", "primary": True}]
        for k in ("quality", "penalty", "gate"):
            if comp[k] is not None:
                metrics.append({"name": k, "value": float(comp[k]), "direction": "higher", "primary": False})
        for k in DIAGNOSTIC_JUDGES:
            v = (per_judge.get(k) or {}).get("value")
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                metrics.append({"name": k, "value": float(v), "direction": "higher", "primary": False})
        return Score(task_id=task.id, reward=reward,
                     feedback=format_feedback(per_judge, quality_judge, annotations, comp, ranges),
                     trial_rewards=[reward], metrics=metrics,
                     raw={"per_judge": per_judge, "components": comp, "harness_reward": payload.get("reward"),
                          **({"errored": True} if unmeasured else {})})

    # ---- making the candidate live -----------------------------------------

    @contextmanager
    def live(self, candidate_dir: Path):
        """A throwaway ``git worktree`` of the clone with the candidate overlaid: its skills
        onto ``.claude/skills/<name>``, its prompt rules onto ``types/<type>/prompts``. The
        bootstrap's untracked output (vendored rubric skills, scorer agents, ``.context``,
        the exported rubric) is linked in from the clone, and the eval configs get the
        optional overlay and model overrides."""
        _check_layout()
        candidate_dir = Path(candidate_dir)
        WORKDIR_ROOT.mkdir(parents=True, exist_ok=True)
        _prune_stale_worktrees()
        checkout = WORKDIR_ROOT / f"wt-{uuid.uuid4().hex[:12]}"
        print(f"[adapter.live] worktree: {checkout}", file=sys.stderr)
        wt = subprocess.run(["git", "-C", str(RFE_CREATOR), "worktree", "add", "--detach", str(checkout), "HEAD"],
                            capture_output=True, text=True, timeout=120)
        if wt.returncode != 0:
            raise RuntimeError(f"git worktree add failed: {wt.stderr.strip()}")
        try:
            skills = checkout / ".claude" / "skills"
            for name in SKILL_NAMES:
                src = candidate_dir / "skills" / name
                if src.is_dir():
                    shutil.rmtree(skills / name, ignore_errors=True)
                    shutil.copytree(src, skills / name)
            for typ in TYPES:
                src = candidate_dir / "types" / typ / "prompts"
                if src.is_dir():
                    shutil.rmtree(checkout / "types" / typ / "prompts", ignore_errors=True)
                    shutil.copytree(src, checkout / "types" / typ / "prompts")
            # bootstrap output: untracked in the clone, so a worktree does not carry it.
            for rel in (".context", "artifacts/rfe-rubric.md", ".claude/agents",
                        ".claude/skills/assess-rfe", ".claude/skills/assess-initiative",
                        ".claude/skills/export-rubric"):
                src, dst = RFE_CREATOR / rel, checkout / rel
                if src.exists() and not dst.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    if src.is_dir():
                        dst.symlink_to(src, target_is_directory=True)
                    else:
                        shutil.copy2(src, dst)
            overlay = yaml.safe_load(EVAL_OVERLAY.read_text(encoding="utf-8")) if EVAL_OVERLAY else {}
            for cfg_name, _, _ in TYPES.values():
                cfg = yaml.safe_load((checkout / cfg_name).read_text(encoding="utf-8"))
                _deep_merge(cfg, overlay or {})
                if JUDGE_MODEL:
                    cfg.setdefault("models", {})["judge"] = JUDGE_MODEL
                (checkout / cfg_name).write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
            yield checkout
        finally:
            subprocess.run(["git", "-C", str(RFE_CREATOR), "worktree", "remove", "--force", str(checkout)],
                           capture_output=True, text=True, timeout=120)

    def runner_model(self) -> str:
        return RUNNER_MODEL


def _prune_stale_worktrees() -> None:
    """Remove ``wt-*`` dirs older than 6h that git no longer lists as live worktrees."""
    if not WORKDIR_ROOT.is_dir() or RFE_CREATOR is None:
        return
    subprocess.run(["git", "-C", str(RFE_CREATOR), "worktree", "prune"], capture_output=True, timeout=30)
    listed = subprocess.run(["git", "-C", str(RFE_CREATOR), "worktree", "list", "--porcelain"],
                            capture_output=True, text=True, timeout=30)
    live = {ln.split(" ", 1)[1] for ln in listed.stdout.splitlines() if ln.startswith("worktree ")}
    cutoff = time.time() - 6 * 3600
    for d in WORKDIR_ROOT.glob("wt-*"):
        try:
            if str(d.resolve()) not in live and d.stat().st_mtime < cutoff:
                shutil.rmtree(d, ignore_errors=True)
        except OSError:
            continue


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--make-seed":
        make_seed(Path(sys.argv[2]))
        print(f"seed capability written to {sys.argv[2]}")
    else:
        sys.exit("usage: adapter.py --make-seed <capability_dir>")
