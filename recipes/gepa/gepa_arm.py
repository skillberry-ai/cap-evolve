"""exp895 GEPA arm (issue skillberry-ai/cap-evolve#895 §7.1, the text-only GEPA variant).

`gepa.optimize` (PyPI gepa==0.1.4 == gepa-ai/gepa v0.1.4 @ 8b0ce6cd) runs UNMODIFIED. The only thing this
module supplies is what GEPA asks a user to supply:

  * a `GEPAAdapter` whose `evaluate()` materialises the candidate as a v2-seed directory and scores it ONLY
    through `CommonRollout.evaluate(candidate_dir, task_ids, k=3)` (the shared exp895 rollout: same agent,
    scorer, R counter, infra retries, helper gate, rollouts.jsonl);
  * `make_reflective_dataset()`: one record per task = the lowest-scoring trial's transcript (<= 20k chars),
    the k-trial mean, the per-trial scores and the scorer's gold-safe feedback;
  * the reflection LM: `gepa.lm.LM` on GLM-5.3 through the metering gateway, max_tokens 16000, temperature unset;
  * a per-component reflection prompt = GEPA's own default template, byte-identical, followed by the common
    SURFACE_CONTRACT.md (verbatim) and a one-line note naming the file being edited (deviation, recorded).

Optimised components (text only, no scripts): `prompt.md` and `skills/spreadsheet-helpers/SKILL.md`.
`task_template.md` and `skills/*/scripts/` stay byte-identical to the v2 seed.

Usage (inside the LSF job, see lsf_gepa_search.sh):
    python gepa_arm.py --run-dir RUN --seed S --R R --train-ids F --val-ids F [--max-iters N]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import threading
import time
from pathlib import Path

EXP = Path("/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-spread-worktrees/exp895")
REPO = Path("/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-spread-worktrees/sbv400-main")
SEED_DIR = REPO / "templates/adapters/spreadsheetbench/seed_capability_v2"
CONTRACT = EXP / "arms/common/SURFACE_CONTRACT.md"
sys.path.insert(0, str(EXP / "arms/common"))

import gepa  # noqa: E402
from gepa.core.adapter import EvaluationBatch  # noqa: E402
from gepa.core.result import GEPAResult  # noqa: E402
from gepa.core.state import GEPAState  # noqa: E402
from gepa.lm import LM  # noqa: E402
from gepa.strategies.instruction_proposal import InstructionProposalSignature  # noqa: E402
from gepa.utils import MaxCandidateProposalsStopper  # noqa: E402

from rollout import BudgetStop, CommonRollout  # noqa: E402

ARM = "gepa"
K = 3
COMPONENTS = ["prompt.md", "skills/spreadsheet-helpers/SKILL.md"]   # §7.1: GEPA = prompt.md + SKILL.md text
INFRA_WAITS = (300, 600, 900)                                       # wait-and-retry for infra-missing tasks
TRANSCRIPT_CAP = 20_000                                            # §7.1: <= 20k characters
SEED_SHA256 = {  # exp895/BUILD_RECORD.json seed_v2.files_sha256
    "prompt.md": "efa493dd57aee05d5563e4f709d5c9e2fde1fb9fc9f71a3b5a3472a40b723c72",
    "task_template.md": "841967412770441da3ba2785e37194524133aca50a49b489bb57f8e22bb84295",
    "skills/spreadsheet-helpers/SKILL.md": "6679c3f28a9fa25ca376d7d143e32a9d8783bd41e2f6b1829de756b3893dae1f",
}

# Issue §7.1 settings table.
GEPA_SETTINGS = dict(
    reflection_minibatch_size=3,
    candidate_selection_strategy="pareto",
    module_selector="round_robin",
    use_merge=False,
    cache_evaluation=False,
    skip_perfect_score=True,
    perfect_score=1.0,
    max_metric_calls=10**12,   # "a very large number": R binds on the real counter (CommonRollout)
    # 2026-10-25: an iteration whose minibatch hit an all-infra task (IterationSkip) is skipped, not fatal.
    # BudgetStop must still end the search: with raise_on_exception=False GEPA swallows it too, so EventLog.on_error
    # records it and the `budget_hit` stop callback in main() ends the loop before the next iteration.
    raise_on_exception=False,
)


class IterationSkip(RuntimeError):
    """A minibatch task stayed all-infra after every retry: skip this GEPA iteration, keep the search going."""


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def reflection_templates() -> dict[str, str]:
    """GEPA's default reflection template, unchanged, + the common surface contract verbatim + a file note."""
    contract = CONTRACT.read_text(encoding="utf-8").strip()
    base = InstructionProposalSignature.default_prompt_template
    out = {}
    for comp in COMPONENTS:
        note = (f"In this optimizer the instruction above is the full text of `{comp}`, and only the text of "
                f"`prompt.md` and `skills/spreadsheet-helpers/SKILL.md` is editable (one file per step). No "
                f"helper scripts exist in this candidate and none can be added, so never describe or call one. "
                f"When the file is SKILL.md, keep its YAML frontmatter (the name and description lines).")
        out[comp] = f"{base}\n\n{contract}\n\n{note}"
    return out


# ---------------------------------------------------------------------------------------------------------
class CandidateStore:
    """candidate dict -> a v2-seed directory. Everything except the GEPA components is the seed's own bytes."""

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._index = root / "index.jsonl"

    def seed_candidate(self) -> dict[str, str]:
        for rel, h in SEED_SHA256.items():
            got = _sha((SEED_DIR / rel).read_bytes())
            assert got == h, f"seed file {rel} sha256 {got} != BUILD_RECORD {h}"
        return {c: (SEED_DIR / c).read_bytes().decode("utf-8") for c in COMPONENTS}

    def key(self, cand: dict[str, str]) -> str:
        h = hashlib.sha256()
        for c in COMPONENTS:
            h.update(c.encode() + b"\0" + cand[c].encode("utf-8") + b"\0")
        return h.hexdigest()[:12]

    def materialize(self, cand: dict[str, str]) -> Path:
        k = self.key(cand)
        is_seed = all(cand[c].encode("utf-8") == (SEED_DIR / c).read_bytes() for c in COMPONENTS)
        name = "seed" if is_seed else f"cand_{k}"
        d = self.root / name
        with self._lock:
            if d.exists():
                return d
            tmp = self.root / f".{name}.tmp"
            if tmp.exists():
                shutil.rmtree(tmp)
            shutil.copytree(SEED_DIR, tmp)
            for c in COMPONENTS:
                (tmp / c).write_bytes(cand[c].encode("utf-8"))
            tmp.rename(d)
            with open(self._index, "a") as f:
                f.write(json.dumps({"name": name, "key": k, "t": time.time(),
                                    "sha256": {c: _sha(cand[c].encode("utf-8")) for c in COMPONENTS}}) + "\n")
        return d


def render_transcript(trace) -> str:
    """The agent's turns (system message dropped: it is the candidate itself), capped at TRANSCRIPT_CAP chars.
    Over the cap, keep the head (task + first turns) and the tail (where the episode ended)."""
    if not trace:
        return "(no transcript: the rollout produced none)"
    parts = []
    for m in trace:
        role = m.get("role", "?") if isinstance(m, dict) else "?"
        if role == "system":
            continue
        content = m.get("content", "") if isinstance(m, dict) else str(m)
        if isinstance(content, list):
            content = "\n".join(str(x.get("text", x)) if isinstance(x, dict) else str(x) for x in content)
        parts.append(f"[{role}]\n{content}")
    text = "\n\n".join(parts)
    if len(text) <= TRANSCRIPT_CAP:
        return text
    marker = "\n\n[... middle of the transcript elided to fit 20k characters ...]\n\n"
    head = 6_000
    tail = TRANSCRIPT_CAP - head - len(marker)
    return text[:head] + marker + text[-tail:]


def _infra_trial(tr, j) -> bool:
    """A trial still infra after every retry: CommonRollout scores it 0.0, refunds it, and leaves error None
    (a candidate-caused error is kept in tr.errors). The scorer's infra feedback starts 'Rollout failed:'."""
    return tr.errors[j] is None and str(tr.feedback[j] or "").startswith("Rollout failed:")


class SpreadsheetGEPAAdapter:
    """GEPAAdapter: evaluate() = CommonRollout.evaluate(k=3); make_reflective_dataset() per §7.1."""

    propose_new_texts = None   # GEPA's own reflective proposer (default), with the reflection LM below

    def __init__(self, ro: CommonRollout, store: CandidateStore, log_dir: Path):
        self.ro, self.store = ro, store
        self._evals = open(log_dir / "gepa_evals.jsonl", "a", buffering=1)

    def evaluate(self, batch, candidate, capture_traces=False):
        cdir = self.store.materialize(candidate)
        ids = [str(x["id"]) for x in batch]
        uniq = list(dict.fromkeys(ids))          # GEPA pads a minibatch with repeats; k stays inside one call
        res = self.ro.evaluate(cdir, uniq, k=K, candidate_id=cdir.name)   # raises BudgetStop before overshooting
        per_task, counted = dict(res.per_task), res.counted
        # A task whose every trial stayed infra is MISSING, not 0, and GEPA needs one score per batch item. So:
        # two immediate re-evaluations, then wait-and-retry (300/600/900 s, as in the MIPROv2 arm) so an upstream
        # outage is waited out instead of killing the search (GEPA s0/s1 died here on 2026-10-23/24, decisions.md).
        for attempt in range(2 + len(INFRA_WAITS) + 1):
            missing = [t for t in uniq if all(_infra_trial(per_task[t], j) for j in range(len(per_task[t].trials)))]
            if not missing:
                break
            if attempt >= 2:
                if attempt - 2 >= len(INFRA_WAITS):
                    break
                w = INFRA_WAITS[attempt - 2]
                print(f"[gepa] {len(missing)} task(s) still infra-missing; waiting {w}s before retrying", flush=True)
                time.sleep(w)
            again = self.ro.evaluate(cdir, missing, k=K, candidate_id=cdir.name)
            per_task.update(again.per_task)
            counted += again.counted
        outputs, scores, trajs, skill_seen = [], [], [], []
        for t in ids:
            tr = per_task[t]
            ok = [j for j in range(len(tr.trials)) if not _infra_trial(tr, j)]
            if not ok:
                # 2026-10-25: still infra after the immediate re-evaluations AND the 300/600/900 s waits (chronic tasks
                # 6239 / 22-47 on RITS). Raise IterationSkip: an Exception, so GEPA's main loop logs it and moves on to
                # the next iteration (raise_on_exception=False below) instead of ending the search. Nothing is scored 0:
                # the minibatch is dropped, and its counted rollouts stay debited (they were run).
                raise IterationSkip(f"gepa arm: task {t} stayed infra-errored on every trial after retries")
            trials = [tr.trials[j] for j in ok]
            mean = sum(trials) / len(trials)
            outputs.append({"task_id": t, "mean": mean, "trials": trials, "candidate": cdir.name})
            scores.append(mean)
            if capture_traces:
                # Same choice as rollout.py's worst_trace: the LAST trial whose score is <= every earlier one.
                jw = max(j for j in range(len(tr.trials)) if tr.trials[j] <= min(tr.trials[: j + 1]))
                sysmsg = next((m.get("content", "") for m in (tr.worst_trace or [])
                               if isinstance(m, dict) and m.get("role") == "system"), "")
                skill_seen.append("Helper skill `spreadsheet-helpers`" in str(sysmsg))
                trajs.append({"task_id": t, "mean": mean, "trials": trials, "worst_trial": jw,
                              "worst_feedback": tr.feedback[jw], "worst_error": tr.errors[jw],
                              "worst_transcript": render_transcript(tr.worst_trace)})
        self._evals.write(json.dumps({"t": time.time(), "eval_call": res.eval_call, "candidate": cdir.name,
                                      "ids": ids, "scores": scores, "counted": counted,
                                      "capture_traces": capture_traces, "spent": self.ro.spent,
                                      "skill_md_in_system_prompt": skill_seen or None}) + "\n")
        return EvaluationBatch(outputs=outputs, scores=scores, trajectories=trajs if capture_traces else None,
                               num_metric_calls=counted)

    def make_reflective_dataset(self, candidate, eval_batch, components_to_update):
        tasks = self.ro._tasks  # noqa: SLF001 — the shared rollout's own task table (gold-free inputs)
        records, seen = [], set()
        for tj in eval_batch.trajectories or []:
            if tj["task_id"] in seen:      # one row per task (a padded minibatch repeats ids)
                continue
            seen.add(tj["task_id"])
            inp = tasks[tj["task_id"]].input
            fb = [f"Mean hard score over {len(tj['trials'])} trials: {tj['mean']:.3f}. "
                  f"Per-trial scores: {tj['trials']}. The transcript shown is trial {tj['worst_trial']}, the "
                  f"lowest-scoring one.",
                  f"Scorer feedback on that trial: {tj['worst_feedback']}"]
            if tj["worst_error"]:
                fb.append(f"That trial ended with a candidate-caused error: {str(tj['worst_error'])[:1000]}")
            records.append({
                "Inputs": {"instruction": inp["instruction"], "instruction_type": inp["instruction_type"],
                           "answer_position": inp["answer_position"]},
                "Generated Outputs": tj["worst_transcript"],
                "Feedback": "\n".join(fb),
            })
        return {c: records for c in components_to_update}


class EventLog:
    """GEPA callbacks -> reflection_log.jsonl (every reflection prompt + raw GLM output, for the §4.1 scan)
    and gepa_events.jsonl. Callback exceptions are swallowed by GEPA's notify_callbacks."""

    def __init__(self, log_dir: Path):
        self.refl = open(log_dir / "reflection_log.jsonl", "a", buffering=1)
        self.ev = open(log_dir / "gepa_events.jsonl", "a", buffering=1)
        self.budget_stop: str | None = None   # set by on_error when GEPA swallowed a BudgetStop
        self.skipped = 0                      # iterations skipped by IterationSkip

    def _e(self, kind, **kw):
        self.ev.write(json.dumps({"t": time.time(), "event": kind, **kw}, default=str) + "\n")

    def on_proposal_end(self, e):
        self.refl.write(json.dumps({"t": time.time(), "iteration": e["iteration"], "prompts": e["prompts"],
                                    "raw_lm_outputs": e["raw_lm_outputs"],
                                    "new_instructions": e["new_instructions"]}, default=str) + "\n")

    def on_candidate_selected(self, e):
        self._e("candidate_selected", iteration=e["iteration"], candidate_idx=e["candidate_idx"], score=e["score"])

    def on_minibatch_sampled(self, e):
        self._e("minibatch", iteration=e["iteration"], ids=list(e["minibatch_ids"]))

    def on_evaluation_skipped(self, e):
        self._e("evaluation_skipped", iteration=e["iteration"], reason=e["reason"])

    def on_candidate_accepted(self, e):
        self._e("accepted", iteration=e["iteration"], idx=e["new_candidate_idx"], score=e["new_score"])

    def on_candidate_rejected(self, e):
        self._e("rejected", iteration=e["iteration"], old=e["old_score"], new=e["new_score"], reason=e["reason"])

    def on_valset_evaluated(self, e):
        self._e("valset", iteration=e["iteration"], idx=e["candidate_idx"], avg=e["average_score"],
                scores=e["scores_by_val_id"], best=e["is_best_program"])

    def on_error(self, e):
        self._e("error", iteration=e["iteration"], exception=repr(e["exception"]))
        if isinstance(e["exception"], BudgetStop):
            self.budget_stop = str(e["exception"])
        elif isinstance(e["exception"], IterationSkip):
            self.skipped += 1


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
    ap.add_argument("--max-iters", type=int, default=0, help="smoke only: cap GEPA proposals (0 = R binds)")
    ap.add_argument("--glm-base", default="http://127.0.0.1:4115")
    a = ap.parse_args(argv)
    run = Path(a.run_dir)
    t0 = time.time()

    train, val = _ids(a.train_ids), _ids(a.val_ids)
    ro = CommonRollout(run, arm=ARM, search_seed=a.seed, R=a.R)
    store = CandidateStore(run / "candidates")
    adapter = SpreadsheetGEPAAdapter(ro, store, run)
    tasks = ro._tasks  # noqa: SLF001
    to_inst = lambda ids: [{"id": t, **{k: tasks[t].input[k] for k in ("instruction", "instruction_type",
                                                                      "answer_position")}} for t in ids]
    tag = f"exp895-{ARM}-s{a.seed}:optimizer"
    reflection_lm = LM("openai/rits/zai-org/glm-5-3", api_base=f"{a.glm_base}/t/{tag}/v1",
                       api_key="tag-not-a-secret", max_tokens=16000,
                       timeout=3600)   # the gateway retries GLM up to 8x; litellm's 600 s default would cut it   # temperature unset (§7.1)
    evlog = EventLog(run)
    stops = [lambda s: ro.remaining() < K,   # nothing more can be scored; BudgetStop is the hard guard
             lambda s: evlog.budget_stop is not None]   # a BudgetStop GEPA swallowed (raise_on_exception=False)
    if a.max_iters:
        stops.append(MaxCandidateProposalsStopper(a.max_iters))
    gdir = run / "gepa"

    stop_reason, result = "", None
    try:
        result = gepa.optimize(
            seed_candidate=store.seed_candidate(), trainset=to_inst(train), valset=to_inst(val),
            adapter=adapter, reflection_lm=reflection_lm, reflection_prompt_template=reflection_templates(),
            stop_callbacks=stops, run_dir=str(gdir), callbacks=[evlog], seed=a.seed,
            display_progress_bar=False, **GEPA_SETTINGS)
        stop_reason = (f"BudgetStop: {evlog.budget_stop}" if evlog.budget_stop else
                       "budget_remaining<k" if ro.remaining() < K else ("max_iters" if a.max_iters else "gepa_stop"))
    except BudgetStop as e:
        # Raised by CommonRollout BEFORE an evaluation that would overshoot R. GEPA re-raises it
        # (raise_on_exception=True, the upstream default); its state was saved at the start of the iteration.
        stop_reason = f"BudgetStop: {e}"
        if not (gdir / "gepa_state.bin").exists():
            raise RuntimeError("R is too small to score the seed on the valset") from e
        result = GEPAResult.from_state(GEPAState.load(str(gdir)), run_dir=str(gdir), seed=a.seed)

    best = result.best_idx
    champ = store.materialize(result.candidates[best])
    if (run / "champion").exists():
        shutil.rmtree(run / "champion")
    shutil.copytree(champ, run / "champion")
    state = GEPAState.load(str(gdir))
    events = [json.loads(x) for x in (run / "gepa_events.jsonl").read_text().splitlines()] \
        if (run / "gepa_events.jsonl").exists() else []
    summary = {
        "arm": ARM, "seed": a.seed, "R": a.R, "rollouts_used": ro.spent, "binding_on_R": ro.remaining() < K
        or stop_reason.startswith("BudgetStop"), "stop_reason": stop_reason,
        "champion": champ.name, "champion_idx": best, "champion_val_score": result.val_aggregate_scores[best],
        "candidates": [{"idx": i, "dir": store.materialize(c).name, "val": result.val_aggregate_scores[i],
                        "parents": result.parents[i]} for i, c in enumerate(result.candidates)],
        "n_candidates_in_pool": len(result.candidates),
        "n_candidates_evaluated": len({json.loads(x)["candidate"] for x in
                                       (run / "gepa_evals.jsonl").read_text().splitlines()}),
        "iterations": state.i + 1,
        "accepted": sum(e["event"] == "accepted" for e in events),
        "rejected": sum(e["event"] == "rejected" for e in events),
        "train_ids_n": len(train), "val_ids_n": len(val), "wall_s": round(time.time() - t0, 1),
        "settings": {**{k: v for k, v in GEPA_SETTINGS.items()}, "k": K, "components": COMPONENTS,
                     "reflection_lm": "gepa.lm.LM(openai/rits/zai-org/glm-5-3, max_tokens=16000)"},
        "gepa_version": getattr(gepa, "__version__", "0.1.4"),
        "iterations_skipped_infra": evlog.skipped,   # minibatches dropped by IterationSkip (2026-10-25)
    }
    (run / "run_summary.json").write_text(json.dumps(summary, indent=1))
    print("GEPA_ARM_DONE", json.dumps({k: summary[k] for k in ("rollouts_used", "R", "stop_reason", "champion",
                                                                "n_candidates_evaluated", "iterations")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
