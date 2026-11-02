"""exp895 MIPROv2 arm (issue skillberry-ai/cap-evolve#895 §7.2).

`dspy.MIPROv2` (PyPI dspy==3.4.0, optuna 5.0.0, litellm 1.82.6) runs UNMODIFIED with auto=None. This module
supplies only what a DSPy user supplies:

  * the program (miprov2_program.SpreadsheetAgentProgram): two instruction modules, `agent` = prompt.md
    (+ its demos rendered as "## Worked examples") and `skill` = skills/spreadsheet-helpers/SKILL.md.
    Its forward() never calls a DSPy LM: it renders the program into a v2-seed candidate directory and scores
    the task ONLY through CommonRollout.evaluate(candidate_dir, [task], k=3) (the shared exp895 rollout);
  * the metric: the k=3 mean hard score; during bootstrapping (trace given) 1.0 only if all 3 trials
    were measured and passed, so with metric_threshold=1.0 a demo is admitted only when 3/3 pass;
  * the prompt/instruction LM: GLM-5.3 through the metering gateway; the task LM is a sentinel that raises
    if anything ever calls it.

Guards around upstream (no upstream file is modified; see deviations_miprov2.json):
  * DSPy's Evaluate / BootstrapFewShot / eval_candidate_program / optuna all catch `Exception`. Budget stops,
    persistent infra errors and any bug in this wrapper are therefore raised as BaseException subclasses, which
    none of them catch, so they end the search instead of being scored 0.
  * a per-(candidate, task, split) result cache with in-flight de-duplication (the analogue of DSPy's own LM
    request cache, on by default upstream): re-evaluating identical text on the same task is free, and DSPy's
    straggler re-submission cannot launch duplicate rollouts.
  * the R counter: before each Evaluate the rollouts it needs are checked against R (all-or-nothing);
    bootstrapping may spend at most 20% of R.

Usage (inside the LSF job, see lsf_miprov2_search.sh):
    python miprov2_arm.py --run-dir RUN --seed S --R R --train-ids F --val-ids F [--minibatch-size N] [--max-trials N]
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import re
import shutil
import sys
import threading
import time
import traceback
from pathlib import Path

EXP = Path("/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-spread-worktrees/exp895")
REPO = Path("/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-spread-worktrees/sbv400-main")
SEED_DIR = REPO / "templates/adapters/spreadsheetbench/seed_capability_v2"
CONTRACT = EXP / "arms/common/SURFACE_CONTRACT.md"
ARMDIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXP / "arms/common"))
sys.path.insert(0, str(ARMDIR))

# litellm MUST be imported before dspy: DSPy 3.4.0 puts a lazy-import proxy for litellm into sys.modules, and the
# shared adapter later does `import litellm` inside run_target, which then loads the proxy and fails with a circular
# import (cannot import name BaseModel from openai._models). Importing the real module first removes the proxy.
import litellm  # noqa: E402,F401
import dspy  # noqa: E402
from dspy.utils.callback import BaseCallback  # noqa: E402

import miprov2_program as prog  # noqa: E402
from rollout import BudgetStop, CommonRollout  # noqa: E402

ARM = "miprov2"
K = 3
PROMPT, SKILL = "prompt.md", "skills/spreadsheet-helpers/SKILL.md"
SEED_SHA256 = {  # exp895/BUILD_RECORD.json seed_v2.files_sha256
    "prompt.md": "efa493dd57aee05d5563e4f709d5c9e2fde1fb9fc9f71a3b5a3472a40b723c72",
    "task_template.md": "841967412770441da3ba2785e37194524133aca50a49b489bb57f8e22bb84295",
    "skills/spreadsheet-helpers/SKILL.md": "6679c3f28a9fa25ca376d7d143e32a9d8783bd41e2f6b1829de756b3893dae1f",
}
BOOTSTRAP_FRACTION = 0.20          # §7.2: limit bootstrapping to 20% of R
DEMO_CODE_CAP = 8000               # chars of solution code per rendered demo
INFRA_REEVALS = 2                  # extra immediate re-evaluations of a task whose every trial stayed infra
INFRA_WAITS = (300, 600, 900)
MAX_EVAL_CALLS = 1000              # trial-seed uniqueness bound of arms/common/rollout.py
ZERO_COST_STREAK = 300             # consecutive Evaluates needing 0 new rollouts -> SearchConverged      # then wait-and-retry (s) before declaring an outage
GLM_MODEL = "openai/rits/zai-org/glm-5-3"   # served id (decisions.md); issue spells openai/hosted_vllm/zai-org/GLM-5.3

# Issue §7.2 settings table (num_threads is set from the run's concurrency, §10).
MIPRO_INIT = dict(auto=None, num_candidates=3, max_bootstrapped_demos=2, max_labeled_demos=0, metric_threshold=1.0)
MIPRO_COMPILE = dict(minibatch=True, minibatch_size=8, minibatch_full_eval_steps=4)
UNBOUNDED_TRIALS = 10**6           # §7.2: num_trials effectively unbounded; R stops it


# ---- stops that DSPy cannot swallow ---------------------------------------------------------------------
class ArmStop(BaseException):
    """Base of every stop raised through DSPy/optuna. BaseException: Evaluate's ParallelExecutor,
    eval_candidate_program, BootstrapFewShot and optuna's _run_trial all catch only Exception."""


class MiproBudgetStop(ArmStop):
    pass


class InfraOutage(ArmStop):
    pass


class ArmFatal(ArmStop):
    pass


class SearchConverged(ArmStop):
    """Every Evaluate for a long run of trials needed 0 new rollouts: optuna only re-samples candidates that
    are already scored, so the search can make no further progress (only reachable when R does not bind)."""


class NoTaskLM(dspy.BaseLM):
    """The DSPy task LM. forward() never calls it (§7.2); if anything ever does, the search stops loudly."""

    def __init__(self):
        super().__init__(model="exp895/no-task-lm", cache=False)

    def forward(self, prompt=None, messages=None, **kwargs):
        raise ArmFatal("the DSPy task LM was called; the miprov2 arm must score tasks only via CommonRollout")

    def __call__(self, *a, **kw):
        raise ArmFatal("the DSPy task LM was called; the miprov2 arm must score tasks only via CommonRollout")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ---- solution code of a solved trial (for demos) ---------------------------------------------------------
_FENCE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.S)


def solution_code_from_trace(trace) -> str:
    """The final solution code of an episode: the last assistant code block that saves a workbook (else the
    last code block). TaskResult carries transcripts, not Rollout.output, so it is recovered from the trace."""
    blocks = []
    for m in trace or []:
        if isinstance(m, dict) and m.get("role") == "assistant":
            blocks += [b.strip("\n") for b in _FENCE.findall(str(m.get("content") or ""))]
    saving = [b for b in blocks if re.search(r"\.save\(|to_excel\(|save_workbook|\.close\(\)", b)]
    return sanitize_paths((saving or blocks or [""])[-1])


_OUT_PATH = re.compile(r"/mnt/data/outputs/[^'\"\s)]+")
_IN_PATH = re.compile(r"/mnt/data/spreadsheet/[^'\"\s)]+")


def sanitize_paths(code: str) -> str:
    """A demo's container paths belong to ITS task (they hold its id and run tag): replace them by the names the
    task message uses, so a worked example never points the agent at another task's files."""
    return _IN_PATH.sub("SPREADSHEET_PATH", _OUT_PATH.sub("OUTPUT_PATH", code))


# ---- candidates -------------------------------------------------------------------------------------------
class CandidateStore:
    """program -> a v2-seed directory: prompt.md = agent instructions (+ worked examples), SKILL.md = skill
    instructions. Everything else is the seed's own bytes. The seed program renders byte-identically."""

    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._index = root / "index.jsonl"
        for rel, h in SEED_SHA256.items():
            got = _sha((SEED_DIR / rel).read_bytes())
            assert got == h, f"seed file {rel} sha256 {got} != BUILD_RECORD {h}"
        self.seed_text = {c: (SEED_DIR / c).read_bytes().decode("utf-8") for c in (PROMPT, SKILL)}

    def _text(self, comp: str, instructions: str) -> str:
        seed = self.seed_text[comp]
        if instructions == inspect.cleandoc(seed):
            return seed                      # unchanged instruction: the seed's exact bytes
        return instructions.rstrip("\n") + "\n"

    @staticmethod
    def render_demos(demos) -> str:
        parts = []
        for i, d in enumerate(demos, 1):
            code = str(d.get("solution_code") or "")
            if len(code) > DEMO_CODE_CAP:
                code = code[:DEMO_CODE_CAP] + "\n# ... (truncated)"
            parts.append(f"### Example {i}\n- instruction_type: {d.get('instruction_type')}\n"
                         f"- answer_position: {d.get('answer_position')}\n- instruction:\n{d.get('instruction')}\n\n"
                         f"Final solution code (SPREADSHEET_PATH and OUTPUT_PATH stand for your own task's "
                         f"spreadsheet_path and output_path):\n```python\n{code}\n```")
        return "\n\n## Worked examples\n\nSolved tasks of the same kind, each with the final code that solved it.\n\n" \
            + "\n\n".join(parts) + "\n"

    def files(self, program) -> dict[str, str]:
        prompt = self._text(PROMPT, program.agent.signature.instructions)
        if program.agent.demos:
            prompt = prompt.rstrip("\n") + "\n" + self.render_demos(program.agent.demos)
        return {PROMPT: prompt, SKILL: self._text(SKILL, program.skill.signature.instructions)}

    def key(self, files: dict[str, str]) -> str:
        h = hashlib.sha256()
        for c in (PROMPT, SKILL):
            h.update(c.encode() + b"\0" + files[c].encode("utf-8") + b"\0")
        return h.hexdigest()[:12]

    def is_seed(self, files) -> bool:
        return all(files[c] == self.seed_text[c] for c in (PROMPT, SKILL))

    def materialize(self, program) -> tuple[str, Path]:
        f = self.files(program)
        k = self.key(f)
        name = "seed" if self.is_seed(f) else f"cand_{k}"
        d = self.root / name
        with self._lock:
            if not d.exists():
                tmp = self.root / f".{name}.tmp"
                if tmp.exists():
                    shutil.rmtree(tmp)
                shutil.copytree(SEED_DIR, tmp)
                for c, text in f.items():
                    (tmp / c).write_bytes(text.encode("utf-8"))
                tmp.rename(d)
                with open(self._index, "a") as fh:
                    fh.write(json.dumps({"name": name, "key": k, "t": time.time(),
                                         "n_demos": len(program.agent.demos or []),
                                         "sha256": {c: _sha(t.encode("utf-8")) for c, t in f.items()}}) + "\n")
        return name, d


# ---- scoring through the common rollout --------------------------------------------------------------------
class Scorer:
    """Every task score of this arm. Cache keyed (candidate, task, split) with in-flight de-duplication."""

    def __init__(self, ro: CommonRollout, run: Path):
        self.ro = ro
        self._cache: dict[tuple, dict] = {}
        self._inflight: dict[tuple, threading.Event] = {}
        self._failed: dict[tuple, BaseException] = {}
        self._lock = threading.Lock()
        self._busy = 0
        self._idle = threading.Condition(self._lock)
        self._log = open(run / "mipro_scores.jsonl", "a", buffering=1)
        self.bootstrap_spent = 0

    def cached(self, cand: str, tid: str, split: str) -> bool:
        with self._lock:
            return (cand, tid, split) in self._cache

    def wait_idle(self, timeout=None):
        with self._idle:
            self._idle.wait_for(lambda: self._busy == 0, timeout=timeout)

    def score(self, cand: str, cdir: Path, ids: list[str], split: str, phase: str) -> dict[str, dict]:
        """{tid: {"mean", "trials", "valid", "infra", "trace0", "cached"}} for every id. Raises InfraOutage if a task
        stays unmeasured after every retry, MiproBudgetStop if R cannot cover it."""
        out, mine, waits = {}, [], []
        with self._lock:
            for t in ids:
                k = (cand, t, split)
                if k in self._cache:
                    out[t] = {**self._cache[k], "cached": True}
                elif k in self._inflight:
                    waits.append((t, self._inflight[k]))
                else:
                    self._inflight[k] = threading.Event()
                    mine.append(t)
            self._busy += 1
        try:
            if mine:
                try:
                    got = self._run(cand, cdir, mine, split, phase)
                except BaseException as e:
                    with self._lock:
                        for t in mine:
                            self._failed[(cand, t, split)] = e
                    raise
                finally:
                    with self._lock:
                        for t in mine:
                            self._inflight.pop((cand, t, split)).set()
                out.update(got)
            for t, ev in waits:
                ev.wait()
                with self._lock:
                    if (cand, t, split) not in self._cache:
                        e = self._failed.pop((cand, t, split), None)
                        if isinstance(e, ArmStop):
                            raise type(e)(f"(shared in-flight evaluation) {e}")
                        raise ArmFatal(f"in-flight evaluation of {cand}/{t} ended without a result: {e!r}")
                    out[t] = {**self._cache[(cand, t, split)], "cached": True}
            return out
        finally:
            with self._idle:
                self._busy -= 1
                self._idle.notify_all()

    def _run(self, cand, cdir, ids, split, phase):
        todo, res = list(ids), {}
        attempt, waits = 0, list(INFRA_WAITS)
        while todo:
            if self.ro._eval_calls >= MAX_EVAL_CALLS:  # noqa: SLF001
                # rollout.py's trial-seed formula (1_000_000*seed + 1000*call + 100*attempt + trial) is unique only
                # for eval_call < 1000; this arm makes one evaluation call per (candidate, task).
                raise ArmFatal(f"eval_call reached {MAX_EVAL_CALLS}: trial seeds would collide")
            try:
                r = self.ro.evaluate(cdir, todo, k=K, candidate_id=cand, split=split)
            except BudgetStop as e:      # an Exception: re-raise as a stop DSPy cannot swallow
                raise MiproBudgetStop(str(e)) from e
            if phase == "bootstrap":
                with self._lock:
                    self.bootstrap_spent += r.counted
            for t in todo:
                tr = r.per_task[t]
                if tr.missing:
                    continue
                j0 = next(j for j, bad in enumerate(tr.infra) if not bad)
                rec = {"mean": tr.mean, "trials": list(tr.trials), "valid": list(tr.valid), "infra": list(tr.infra),
                       "trial_seeds": list(tr.trial_seeds), "errors": [str(x)[:300] if x else None for x in tr.errors],
                       "trace0": tr.traces[j0], "eval_call": r.eval_call}
                with self._lock:
                    self._cache[(cand, t, split)] = rec
                self._log.write(json.dumps({"t": time.time(), "candidate": cand, "task_id": t, "split": split,
                                            "phase": phase, "mean": rec["mean"], "trials": rec["trials"],
                                            "infra": rec["infra"], "eval_call": r.eval_call,
                                            "spent": self.ro.spent}) + "\n")
                res[t] = {**rec, "cached": False}
            todo = [t for t in todo if t not in res]
            if not todo:
                break
            attempt += 1
            if attempt > INFRA_REEVALS:
                if not waits:
                    raise InfraOutage(f"{cand}: tasks {todo} stayed infra-errored on every trial after all retries")
                w = waits.pop(0)
                print(f"[miprov2] {len(todo)} task(s) still infra-missing; waiting {w}s before retrying", flush=True)
                time.sleep(w)
        return res


# ---- the arm state shared by the program hook, the metric and the callback ---------------------------------
class Arm:
    def __init__(self, ro, store, scorer, train, val, R, run):
        self.ro, self.store, self.scorer, self.R = ro, store, scorer, R
        self.train, self.val = set(train), list(val)
        self.val_set = set(val)
        self.blocked = None          # set by the callback when the current Evaluate cannot fit in R
        self.in_eval = False
        self.full_val = []           # [{"candidate", "score", "t", "source"}] in evaluation order
        self._full_seen = set()
        self._evlog = open(run / "mipro_evals.jsonl", "a", buffering=1)
        self._fwd = open(run / "mipro_forward.jsonl", "a", buffering=1)
        self._cur = None
        self.n_evaluates = 0
        self.stopped = None          # once set, every forward raises: DSPy's abandoned threads cannot score more
        self.zero_streak = 0
        self.converged = None

    # program.forward -> here
    def run_program(self, program, task_id, inputs):
        if self.stopped:
            raise MiproBudgetStop(f"search already stopped: {self.stopped}")
        try:
            return self._run_program(program, str(task_id), inputs)
        except ArmStop as e:
            self.stopped = self.stopped or f"{type(e).__name__}: {str(e)[:200]}"
            raise
        except Exception as e:  # noqa: BLE001 — a wrapper bug must never be swallowed as a 0 score
            self.stopped = self.stopped or f"ArmFatal: {e!r}"[:200]
            raise ArmFatal(f"miprov2 forward failed: {type(e).__name__}: {e}\n{traceback.format_exc()}") from e

    def _run_program(self, program, tid, inputs):
        if self.in_eval and self.converged:
            raise SearchConverged(self.converged)
        if self.in_eval and self.blocked:
            raise MiproBudgetStop(self.blocked)
        cand, cdir = self.store.materialize(program)
        split = "val" if (self.in_eval or tid not in self.train) else "train"
        phase = "evaluate" if self.in_eval else "bootstrap"
        if phase == "bootstrap" and not self.scorer.cached(cand, tid, split):
            if not self.ro.would_fit(1, K):
                raise MiproBudgetStop(f"bootstrapping: R exhausted ({self.ro.spent}/{self.R})")
            cap = int(BOOTSTRAP_FRACTION * self.R)
            if self.scorer.bootstrap_spent + K > cap:
                self._fwd.write(json.dumps({"t": time.time(), "phase": phase, "candidate": cand, "task_id": tid,
                                            "skipped": f"bootstrap cap {cap} reached"}) + "\n")
                return dspy.Prediction(solution_code="", score=0.0, all_pass=False, skipped=True)
        r = self.scorer.score(cand, cdir, [tid], split, phase)[tid]
        code = solution_code_from_trace(r["trace0"])
        all_pass = len(r["valid"]) == K and all(x >= 1.0 for x in r["valid"])
        self._fwd.write(json.dumps({"t": time.time(), "phase": phase, "candidate": cand, "task_id": tid,
                                    "split": split, "mean": r["mean"], "trials": r["trials"], "infra": r["infra"],
                                    "cached": r["cached"], "all_pass": all_pass, "spent": self.ro.spent}) + "\n")
        if phase == "bootstrap":
            st = dspy.settings.trace
            if st is not None and dspy.settings.max_trace_size > 0:
                st.append((program.agent, dict(inputs), dspy.Prediction(solution_code=code)))
        return dspy.Prediction(solution_code=code, score=r["mean"], all_pass=all_pass, skipped=False)

    # the metric
    def metric(self, example, pred, trace=None):
        if trace is not None:          # bootstrapping: admit a demo only if all 3 trials passed
            return 1.0 if pred.get("all_pass") else 0.0
        return float(pred.get("score", 0.0))

    # Evaluate start/end (via the callback)
    def evaluate_start(self, program, devset, metric_key=None):
        ids = [str(e.task_id) for e in devset]
        cand, _ = self.store.materialize(program)
        need = sum(1 for t in dict.fromkeys(ids) if not self.scorer.cached(cand, t, "val"))
        self.in_eval = True
        self.zero_streak = self.zero_streak + 1 if need == 0 else 0
        if self.zero_streak > ZERO_COST_STREAK:
            self.converged = f"{self.zero_streak} consecutive evaluations needed no new rollout"
        self.blocked = None if self.ro.would_fit(need, K) else (
            f"Evaluate of {cand} on {len(ids)} tasks needs {need}x{K}={need * K} new rollouts; "
            f"R has {self.ro.remaining()} left ({self.ro.spent}/{self.R})")
        self._cur = {"candidate": cand, "ids": ids, "need_rollouts": need * K, "t0": time.time(),
                     "spent0": self.ro.spent, "blocked": self.blocked, "metric_key": metric_key}

    def evaluate_end(self, outputs, exception):
        cur, self._cur = self._cur or {}, None
        self.in_eval, self.blocked = False, None
        self.n_evaluates += 1
        cand, ids = cur.get("candidate"), cur.get("ids", [])
        rec = {**cur, "t1": time.time(), "spent1": self.ro.spent,
               "dspy_score": getattr(outputs, "score", None) if outputs is not None else None,
               "exception": repr(exception)[:300] if exception is not None else None,
               "full_val": set(ids) == self.val_set}
        # MIPRO's own full evaluations (eval_candidate_program tags them metric_key="eval_full")
        if exception is None and cand and set(ids) == self.val_set and cur.get("metric_key") == "eval_full":
            self.record_full_val(cand, source="mipro_evaluate")
        self._evlog.write(json.dumps(rec, default=str) + "\n")

    def record_full_val(self, cand, source):
        means = []
        for t in self.val:
            k = (cand, t, "val")
            with self.scorer._lock:  # noqa: SLF001
                if k not in self.scorer._cache:  # noqa: SLF001
                    return
                means.append(self.scorer._cache[k]["mean"])  # noqa: SLF001
        if cand in self._full_seen:
            return
        self._full_seen.add(cand)
        self.full_val.append({"candidate": cand, "score": sum(means) / len(means), "t": time.time(),
                              "source": source})

    def champion(self):
        """Best full-val candidate; the seed (first record) wins ties, as MIPRO's strict `>` does."""
        best = None
        for r in self.full_val:
            if best is None or r["score"] > best["score"]:
                best = r
        return best


class ArmCallback(BaseCallback):
    """Evaluate start/end -> the arm (R pre-check, full-val bookkeeping); every prompt-model call -> the log
    the §4.1 isolation scan reads (it is everything the optimizer ever sees and says)."""

    def __init__(self, arm: Arm, run: Path):
        self.arm = arm
        self.lm_log = open(run / "prompt_lm_log.jsonl", "a", buffering=1)
        self._lock = threading.Lock()
        self._calls = {}
        self.lm_errors = 0

    def on_evaluate_start(self, call_id, instance, inputs):
        try:
            self.arm.evaluate_start(inputs["program"], inputs.get("devset") or instance.devset,
                                    (inputs.get("callback_metadata") or {}).get("metric_key"))
        except Exception as e:  # noqa: BLE001 — callback exceptions are swallowed by DSPy: block the eval instead
            self.arm.in_eval, self.arm.blocked = True, f"evaluate_start failed: {e!r}"

    def on_evaluate_end(self, call_id, outputs, exception=None):
        self.arm.evaluate_end(outputs, exception)

    def on_lm_start(self, call_id, instance, inputs):
        with self._lock:
            self._calls[call_id] = {"t0": time.time(), "model": getattr(instance, "model", None),
                                    "messages": inputs.get("messages"), "prompt": inputs.get("prompt"),
                                    "kwargs": {k: v for k, v in (inputs.get("kwargs") or {}).items()
                                               if not str(k).startswith("api_")}}

    def on_lm_end(self, call_id, outputs, exception=None):
        with self._lock:
            rec = self._calls.pop(call_id, {})
            if exception is not None:
                self.lm_errors += 1
        rec.update({"t1": time.time(), "outputs": outputs, "exception": repr(exception) if exception else None})
        self.lm_log.write(json.dumps(rec, default=str) + "\n")


# ---------------------------------------------------------------------------------------------------------
def _ids(path) -> list[str]:
    return [ln.strip() for ln in Path(path).read_text().splitlines() if ln.strip()]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--R", type=int, required=True)
    ap.add_argument("--train-ids", required=True)
    ap.add_argument("--val-ids", required=True)
    ap.add_argument("--conc", type=int, default=10)
    ap.add_argument("--minibatch-size", type=int, default=MIPRO_COMPILE["minibatch_size"],
                    help="smoke only: must not exceed the valset size")
    ap.add_argument("--max-trials", type=int, default=0, help="smoke only: cap Bayesian trials (0 = R binds)")
    ap.add_argument("--glm-base", default="http://127.0.0.1:4115")
    a = ap.parse_args(argv)
    run = Path(a.run_dir)
    t0 = time.time()

    # The surface contract goes to the proposer verbatim, as part of the program source MIPRO's
    # program-aware proposer reads. Fail if the two ever drift apart.
    contract = CONTRACT.read_text(encoding="utf-8").strip()
    assert contract in (prog.SpreadsheetAgentProgram.__doc__ or ""), "program docstring != SURFACE_CONTRACT.md"

    train, val = _ids(a.train_ids), _ids(a.val_ids)
    ro = CommonRollout(run, arm=ARM, search_seed=a.seed, R=a.R)
    store = CandidateStore(run / "candidates")
    scorer = Scorer(ro, run)
    arm = Arm(ro, store, scorer, train, val, a.R, run)
    prog.ARM_HOOK["run"] = arm.run_program
    cb = ArmCallback(arm, run)

    tag = f"exp895-{ARM}-s{a.seed}:optimizer"
    prompt_lm = dspy.LM(GLM_MODEL, api_base=f"{a.glm_base}/t/{tag}/v1", api_key="tag-not-a-secret",
                        max_tokens=16000, timeout=3600)
    dspy.configure(lm=NoTaskLM(), callbacks=[cb])

    # Seed program: the v2 seed's prompt.md and SKILL.md as the two modules' instructions.
    program = prog.SpreadsheetAgentProgram()
    program.agent.signature = program.agent.signature.with_instructions(store.seed_text[PROMPT])
    program.skill.signature = program.skill.signature.with_instructions(store.seed_text[SKILL])
    assert store.is_seed(store.files(program)), "the seed program does not render to the v2 seed bytes"
    to_ex = lambda ids: [dspy.Example(task_id=t, **{k: ro._tasks[t].input[k] for k in  # noqa: SLF001
                                                    ("instruction", "instruction_type", "answer_position")}
                                      ).with_inputs("task_id", "instruction", "instruction_type", "answer_position")
                         for t in ids]
    trainset, valset = to_ex(train), to_ex(val)

    # Fail fast if the prompt model is unreachable (DSPy's proposer silently drops its dataset summary and
    # program description when their LM calls fail).
    pre = prompt_lm("Reply with the single word READY.")
    print("[miprov2] prompt-model preflight:", str(pre)[:200], flush=True)

    stop_reason, best_program, trace_txt = "", None, None
    try:
        # §7.2: score the seed first (full val); MIPRO's default-program evaluation reuses it via the cache.
        seed_name, seed_dir = store.materialize(program)
        print(f"[miprov2] scoring the seed on val ({len(val)} tasks x {K})", flush=True)
        scorer.score(seed_name, seed_dir, val, "val", "seed")
        arm.record_full_val(seed_name, source="seed_prescore")
        print(f"[miprov2] seed val mean = {arm.full_val[0]['score']:.4f}  spent {ro.spent}/{a.R}", flush=True)

        tp = dspy.MIPROv2(metric=arm.metric, prompt_model=prompt_lm, task_model=NoTaskLM(),
                          num_threads=max(1, a.conc // K), seed=a.seed, log_dir=str(run / "mipro"),
                          verbose=False, **MIPRO_INIT)
        best_program = tp.compile(program, trainset=trainset, valset=valset,
                                  num_trials=a.max_trials or UNBOUNDED_TRIALS,
                                  **{**MIPRO_COMPILE, "minibatch_size": a.minibatch_size})
        stop_reason = "max_trials" if a.max_trials else "mipro_returned"
    except MiproBudgetStop as e:
        stop_reason = f"BudgetStop: {e}"
    except InfraOutage as e:
        stop_reason = f"InfraOutage: {e}"
    except SearchConverged as e:
        stop_reason = f"SearchConverged: {e}"
    except ArmFatal as e:
        stop_reason, trace_txt = f"ArmFatal: {str(e)[:500]}", traceback.format_exc()
    except ValueError as e:
        if "No valid program found" not in str(e):
            stop_reason, trace_txt = f"error: {type(e).__name__}: {str(e)[:500]}", traceback.format_exc()
        else:
            stop_reason = "search_space_exhausted"
    except Exception as e:  # noqa: BLE001 — e.g. the prompt model failing past its retries: report, keep the champion
        stop_reason, trace_txt = f"error: {type(e).__name__}: {str(e)[:500]}", traceback.format_exc()
    arm.stopped = arm.stopped or stop_reason
    for _ in range(3):                   # rollouts still running in DSPy's abandoned worker threads
        scorer.wait_idle(timeout=6 * 3600)
        time.sleep(2)

    best = arm.champion()
    if best is None:
        raise RuntimeError(f"no full-val candidate exists (stop: {stop_reason})")
    champ = store.root / best["candidate"]
    if (run / "champion").exists():
        shutil.rmtree(run / "champion")
    shutil.copytree(champ, run / "champion")
    evals = [json.loads(x) for x in (run / "mipro_evals.jsonl").read_text().splitlines()] \
        if (run / "mipro_evals.jsonl").exists() else []
    lm_calls = (run / "prompt_lm_log.jsonl").read_text().count("\n") if (run / "prompt_lm_log.jsonl").exists() else 0
    cands = [json.loads(x)["name"] for x in (store.root / "index.jsonl").read_text().splitlines()]
    summary = {
        "arm": ARM, "seed": a.seed, "R": a.R, "rollouts_used": ro.spent,
        "binding_on_R": stop_reason.startswith("BudgetStop"), "stop_reason": stop_reason,
        "champion": best["candidate"], "champion_val_score": best["score"],
        "full_val_candidates": arm.full_val,
        "n_candidates_rendered": len(cands),
        "n_candidates_evaluated": len({json.loads(x)["candidate"] for x in
                                       (run / "mipro_scores.jsonl").read_text().splitlines()}),
        "n_dspy_evaluates": len(evals), "bootstrap_rollouts": scorer.bootstrap_spent,
        "bootstrap_cap": int(BOOTSTRAP_FRACTION * a.R), "prompt_lm_calls": lm_calls,
        "prompt_lm_errors": cb.lm_errors,
        "mipro_best_program_returned": best_program is not None,
        "train_ids_n": len(train), "val_ids_n": len(val), "wall_s": round(time.time() - t0, 1),
        "settings": {**MIPRO_INIT, **MIPRO_COMPILE, "minibatch_size": a.minibatch_size,
                     "num_trials": a.max_trials or UNBOUNDED_TRIALS, "num_threads": max(1, a.conc // K), "k": K,
                     "prompt_model": f"dspy.LM({GLM_MODEL}, max_tokens=16000)", "task_model": "NoTaskLM (never called)"},
        "dspy_version": dspy.__version__,
    }
    if trace_txt:
        summary["fatal_traceback"] = trace_txt[-4000:]
    (run / "run_summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print("MIPROV2_ARM_DONE", json.dumps({k: summary[k] for k in ("rollouts_used", "R", "stop_reason", "champion",
                                                                   "champion_val_score", "n_candidates_evaluated")}))
    return 1 if stop_reason.startswith(("ArmFatal", "error")) else 0


if __name__ == "__main__":
    sys.exit(main())
