#!/usr/bin/env python3
"""exp895 SkillOpt arm (issue skillberry-ai/cap-evolve#895 §7.3).

microsoft/SkillOpt @ 79124b37 runs UNMODIFIED: scripts/train.py's config loader, ReflACTTrainer (rollout ->
minibatch reflect -> merge -> rank/select with the cosine edit budget -> apply -> selection gate, slow update
and meta skill at epoch ends, sel_cache), its spreadsheetbench analyst prompts, and its openai_compatible
optimizer backend pointed at the GLM gateway.

Replaced, and only this: SpreadsheetBenchAdapter.rollout(). The skill document SkillOpt optimizes is the packed
candidate (skillopt_pack.py). rollout() unpacks it into a candidate directory and calls the common rollout,
CommonRollout.evaluate(candidate_dir, ids, k=3), then turns the result into SkillOpt result rows, one per trial
(`<id>`, `<id>__t1`, `<id>__t2`), each with its own conversation.json under predictions/ so SkillOpt's
reflect stage reads it exactly as it reads its own codegen agent's trajectories. Gold-free: the trace is the
agent's (gold-free mount) and the appended verification is the common scorer's gold-safe feedback; SkillOpt's
gold-guided `use_eval_feedback` retry and its `_auto_verify_output` (which prints expected cell values) are not
used. Every other difference is listed in deviations_skillopt.json.

Usage (inside the launcher, on a compute node): skillopt_exp895.py --run-dir D --seed S --R N --split F
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path

EXP = Path("/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-spread-worktrees/exp895")
UPSTREAM = EXP / "competitors" / "skillopt"
HERE = Path(__file__).resolve().parent
for p in (str(UPSTREAM), str(EXP / "arms" / "common"), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import skillopt_pack as pk  # noqa: E402
from rollout import BudgetStop, CommonRollout  # noqa: E402
from skillopt.envs.spreadsheetbench.adapter import SpreadsheetBenchAdapter  # noqa: E402
from skillopt.utils.scoring import skill_hash  # noqa: E402

ARM = "skillopt"
K = 3
TRACE_CHARS = 20_000           # per-trial transcript cap shown to the analyst (same bound as GEPA §7.1)
MSG_CHARS = 6_000              # per-message cap inside it (head + tail)
OPT_TOKEN_CAP = 20_000_000     # issue §5: non-cache-read optimizer tokens per search (runaway guard)

SURFACE_CONTRACT = (EXP / "arms" / "common" / "SURFACE_CONTRACT.md").read_text(encoding="utf-8")
PACK_NOTE = """
## How the skill document maps onto those surfaces (exp895 packing)

The "Current Skill" document you edit is several files packed into one text. Each file starts with a marker
line of the exact form `=== FILE: <path> ===` and runs until the next marker. The files are
`task_template.md`, every `skills/<name>/SKILL.md` and `skills/<name>/scripts/<script>.py`, and `prompt.md`
(always last). Rules for edits:

- Never change, remove or duplicate a marker line, and never put text before the first marker. A document
  with a damaged marker cannot be unpacked and scores 0.
- To ADD a helper script, use a `replace` edit whose target is the exact line `=== FILE: prompt.md ===` and
  whose content is `=== FILE: skills/spreadsheet-helpers/scripts/<name>.py ===`, then the full Python source,
  then the line `=== FILE: prompt.md ===` again. Then describe the new helper (signature, when to call it,
  example import `from skills.spreadsheet_helpers.<name> import <fn>`) in that skill's SKILL.md.
- `append` edits land at the end of `prompt.md` (the system prompt).
- Inside the `task_template.md` block keep every `{placeholder}` exactly as written; a literal brace must be
  doubled.
"""
ANALYST_SUFFIX = "\n\n" + SURFACE_CONTRACT.strip() + "\n" + PACK_NOTE


def _clip(s: str, n: int) -> str:
    s = "" if s is None else str(s)
    if len(s) <= n:
        return s
    h = n // 2
    return s[:h] + f"\n...[{len(s) - n} chars truncated]...\n" + s[-h:]


def _bounded_conversation(msgs: list[dict]) -> list[dict]:
    """The agent turns after the first user message, each message head+tail capped, the whole kept under
    TRACE_CHARS by dropping middle turns (the first turns and the final ones are the informative ones)."""
    conv = [{"role": m.get("role", "agent"), "content": _clip(m.get("content", ""), MSG_CHARS)} for m in msgs]
    total = sum(len(m["content"]) for m in conv)
    if total <= TRACE_CHARS:
        return conv
    head, tail, used = [], [], 0
    for m in conv:                         # up to 40% of the budget from the start
        if used + len(m["content"]) > 0.4 * TRACE_CHARS:
            break
        head.append(m)
        used += len(m["content"])
    for m in reversed(conv[len(head):]):   # the rest from the end
        if used + len(m["content"]) > TRACE_CHARS:
            break
        tail.insert(0, m)
        used += len(m["content"])
    dropped = len(conv) - len(head) - len(tail)
    return head + [{"role": "user", "content": f"...[{dropped} middle messages omitted (exp895 transcript cap)]..."}] + tail


def _phase(out_dir: str) -> str:
    p = Path(out_dir).as_posix()
    if p.endswith("selection_eval_baseline"):
        return "sel_baseline"
    if "/steps/" in p and p.endswith("/rollout"):
        return "train"
    if "/steps/" in p and p.endswith("/selection_eval"):
        return "sel"
    if "/slow_update/" in p and p.endswith("/selection_eval"):
        return "slow_sel"        # gated slow update (only if slow_update_gate_with_selection; off in the yaml)
    if "/slow_update/" in p:
        return "slow_update"
    if "/meta_skill/" in p:
        return "meta_skill"
    return "other"


class Exp895SkillOptAdapter(SpreadsheetBenchAdapter):
    """SkillOpt's SpreadsheetBench adapter with rollout() replaced by the exp895 common rollout."""

    def __init__(self, *, common: CommonRollout, run_dir: Path, ledger_glm: Path, opt_tag: str,
                 allowed_ids: set, **kwargs):
        super().__init__(**kwargs)
        self.common = common
        self.allowed_ids = set(allowed_ids)   # train ∪ val of THIS search's split; nothing else is ever rolled out
        self.run_dir = Path(run_dir)
        self.ledger_glm = Path(ledger_glm)
        self.opt_tag = opt_tag
        self.n_rollout_calls = 0
        self.n_damaged = 0
        self.n_infra_missing = 0

    # SkillOpt's analyst prompts are looked up by the adapter's module path; ours lives outside skillopt/envs,
    # so name the env explicitly to keep the spreadsheetbench prompts (issue §7.3 "force _env_name").
    @property
    def _env_name(self) -> str:
        return "spreadsheetbench"

    def get_error_minibatch_prompt(self):
        return super().get_error_minibatch_prompt() + ANALYST_SUFFIX

    def get_success_minibatch_prompt(self):
        return super().get_success_minibatch_prompt() + ANALYST_SUFFIX

    # ---- guards ---------------------------------------------------------------------------------
    def _optimizer_tokens(self) -> int:
        n = 0
        if self.ledger_glm.exists():
            for ln in self.ledger_glm.read_text().splitlines():
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                if r.get("tag") == self.opt_tag and r.get("status") == 200:
                    n += (r.get("prompt_total") or 0) - (r.get("cached_tokens") or 0) + (r.get("completion_tokens") or 0)
        return n

    def _guards(self, phase: str, n_items: int) -> None:
        used = self._optimizer_tokens()
        if used > OPT_TOKEN_CAP:
            raise BudgetStop(f"optimizer token cap: {used} non-cache-read GLM tokens > {OPT_TOKEN_CAP}")
        if phase in ("slow_update", "meta_skill") and self._out_dir.endswith("rollout_prev"):
            # The longitudinal pair is two rollouts (prev skill, curr skill); start it only if both fit.
            if not self.common.would_fit(2 * n_items, K):
                raise BudgetStop(f"{phase} guard: prev+curr {2 * n_items}x{K} does not fit "
                                 f"({self.common.spent}/{self.common.R})")
        if phase == "train":
            # A step is started only if its train rollout AND its selection eval both fit in R; otherwise a
            # train rollout would be spent on a step whose candidate can never be scored.
            n_val = len(self.dataloader.val_items)
            if not self.common.would_fit(n_items + n_val, K):
                raise BudgetStop(f"step guard: train {n_items}x{K} + selection {n_val}x{K} does not fit "
                                 f"({self.common.spent}/{self.common.R})")

    # ---- the one replaced method --------------------------------------------------------------------
    def rollout(self, env_manager, skill_content: str, out_dir: str, **kwargs) -> list[dict]:
        items = list(env_manager)
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        results_path = out / "results.jsonl"
        if results_path.exists():                       # upstream resume semantics, kept
            rows = [json.loads(ln) for ln in results_path.read_text().splitlines() if ln.strip()]
            if rows:
                return rows
        phase = _phase(out_dir)
        ids = [str(it["id"]) for it in items]
        stray = sorted(set(ids) - self.allowed_ids)
        if stray:
            raise RuntimeError(f"refusing to roll out ids outside this search's train/val split: {stray[:3]}")
        self._out_dir = Path(out_dir).as_posix()
        self._guards(phase, len(items))
        cand = out / "candidate"
        damaged = pk.unpack_to_dir(skill_content, cand)
        if damaged:
            self.n_damaged += 1
            (out / "pack_damaged.txt").write_text(damaged + "\n")
        sh = skill_hash(skill_content)
        t0 = time.time()
        # Every SkillOpt "selection_eval*" directory (step gate, baseline, slow-update gate, final selection) runs on
        # the val split; everything else (train rollout, longitudinal pairs) on train.
        split = "val" if (phase in ("sel", "sel_baseline", "slow_sel") or "selection_eval" in Path(out_dir).name) \
            else "train"
        res = self.common.evaluate(cand, ids, k=K, candidate_id=f"{phase}:{sh}", split=split)
        self.n_rollout_calls += 1
        rows = []
        for it in items:
            tid = str(it["id"])
            tr = res.per_task[tid]
            task = self.common._tasks[tid]
            for j, seed in enumerate(tr.trial_seeds):
                if tr.infra[j]:
                    self.n_infra_missing += 1
                    continue                            # still infra after the common retries: missing, not 0
                err = tr.errors[j]                      # candidate-caused error (scores 0), or None
                rid = tid if j == 0 else f"{tid}__t{j}"
                reward = float(tr.trials[j])
                msgs = list(tr.traces[j] or [])
                sys_prompt = msgs[0]["content"] if msgs and msgs[0].get("role") == "system" else ""
                rest = msgs[1:] if sys_prompt else msgs
                user_prompt = rest[0]["content"] if rest and rest[0].get("role") == "user" else ""
                conv = _bounded_conversation(rest[1:] if user_prompt else rest)
                fb = tr.feedback[j] or ""
                if err:
                    fb = f"{fb}\nError: {err}".strip()
                conv.append({"role": "system", "content": f"[POST-EXECUTION VERIFICATION]\n\n{fb}"})
                pdir = out / "predictions" / rid
                pdir.mkdir(parents=True, exist_ok=True)
                (pdir / "conversation.json").write_text(json.dumps(conv, ensure_ascii=False, indent=2))
                (pdir / "target_system_prompt.txt").write_text(sys_prompt)
                (pdir / "target_user_prompt.txt").write_text(user_prompt)
                itype = task.input.get("instruction_type", "")
                low = itype.lower()
                rows.append({
                    "id": rid, "task_id": tid, "trial": j, "trial_seed": seed,
                    "ok": reward >= 1.0, "hard": reward, "soft": reward,
                    "instruction_type": itype,
                    "task_type": "cell_level" if "cell" in low else ("sheet_level" if "sheet" in low else "other"),
                    "task_description": task.input.get("instruction", ""),
                    "fail_reason": "" if reward >= 1.0 else (fb.splitlines()[0][:300] if fb else "failed"),
                    "n_turns": sum(1 for m in rest if m.get("role") == "assistant"),
                    "n_cases": 1, "n_pass": int(reward >= 1.0), "error": err or "",
                    "candidate_hash": sh, "phase": phase, "eval_call": res.eval_call,
                })
        with open(results_path, "w") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        with open(self.run_dir / "skillopt_evals.jsonl", "a") as f:
            f.write(json.dumps({"t": t0, "wall_s": round(time.time() - t0, 1), "phase": phase, "out_dir": str(out),
                                "candidate_hash": sh, "pack_damaged": damaged, "n_tasks": len(ids), "k": K,
                                "counted": res.counted, "infra_retries": res.infra_retries, "mean": res.mean,
                                "rows": len(rows), "spent": self.common.spent, "R": self.common.R}) + "\n")
        return rows


# Optimizer infra failures (what the openai client reports for timeouts, dropped connections and the gateway's
# 502 after its own 8 attempts, or a 429/5xx). Upstream's reflect catches ANY exception and returns None, so a GLM
# outage would turn into "skip_no_patches" steps whose train rollouts were already charged to R. We wait such
# failures out instead (issue §0.3: infra errors are retried, never scored); any other error is upstream behaviour.
import re  # noqa: E402
_OPT_INFRA = re.compile(r"Error code: (429|5\d\d)\b|Request timed out|Connection error|timed out|ReadTimeout")
OPT_INFRA_WAIT_S = 120                 # pause between re-tries of a whole upstream call during an outage
OPT_INFRA_MAX_WAIT_S = 12 * 3600       # after this much waiting on one call, give up (upstream behaviour resumes)


def _install_optimizer_transcript(path: Path) -> None:
    """Log every optimizer call (messages + reply) for the post-search isolation scan, and wait out optimizer
    infra outages (deviation D12). Successful calls are unchanged."""
    from skillopt.model import openai_compatible_backend as oc
    orig = oc._chat_messages_impl
    lock = threading.Lock()

    def _log(t0, stage, kw, messages, text, usage, err, infra_wait_s=0):
        with lock, open(path, "a") as f:
            f.write(json.dumps({"t": t0, "wall_s": round(time.time() - t0, 1), "stage": stage,
                                "role": kw.get("role"), "messages": messages,
                                "reply": text if isinstance(text, str) else str(text),
                                "usage": usage, "error": err, "infra_wait_s": infra_wait_s},
                               ensure_ascii=False) + "\n")

    def logged(messages, max_completion_tokens, retries, stage, **kw):
        t0 = time.time()
        waited = 0
        while True:
            try:
                out = orig(messages, max_completion_tokens, retries, stage, **kw)
            except Exception as e:  # noqa: BLE001
                err = repr(e)[:500]
                infra = bool(_OPT_INFRA.search(str(e)))
                _log(t0, stage, kw, messages, None, {}, err, waited)
                if not infra or waited >= OPT_INFRA_MAX_WAIT_S:
                    raise
                print(f"[exp895] optimizer infra failure in stage={stage} ({err[:160]}); waiting "
                      f"{OPT_INFRA_WAIT_S}s and re-trying (waited {waited}s so far)", file=sys.stderr, flush=True)
                time.sleep(OPT_INFRA_WAIT_S)
                waited += OPT_INFRA_WAIT_S
                continue
            text, usage = out if isinstance(out, tuple) else (out, {})
            _log(t0, stage, kw, messages, text, usage, None, waited)
            return out
    oc._chat_messages_impl = logged


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--R", type=int, required=True)
    ap.add_argument("--split", required=True, help="split_dir with train/val/test items.json (test = 1 stub)")
    ap.add_argument("--opt-model", default="rits/zai-org/glm-5-3")
    a = ap.parse_args()
    run = Path(a.run_dir)
    out_root = run / "skillopt_out"
    seed_doc = run / "seed_packed.md"
    opt_tag = f"exp895-{ARM}-s{a.seed}:optimizer"

    # SkillOpt's own CLI/config path, unmodified (scripts/train.py parse_args + load_config).
    sys.path.insert(0, str(UPSTREAM / "scripts"))
    import train as so_train  # scripts/train.py
    n_train = len(json.loads((Path(a.split) / "train" / "items.json").read_text()))
    sys.argv = ["train.py", "--config", str(UPSTREAM / "configs/spreadsheetbench/default.yaml"),
                "--cfg-options", "model.backend=openai_compatible", "evaluation.gate_metric=hard",
                "--optimizer_backend", "openai_compatible", "--target_backend", "openai_compatible",
                "--optimizer_model", a.opt_model,
                "--target_model", "google/gemma-4-31B-it",
                "--num_epochs", "100", "--batch_size", "6", "--eval_test", "false",
                "--train_size", str(n_train), "--seed", str(a.seed),
                "--split_mode", "split_dir", "--split_dir", str(a.split), "--data_root", "",
                "--skill_init", str(seed_doc), "--out_root", str(out_root),
                "--sel_env_num", "0", "--test_env_num", "0"]
    cfg = so_train.load_config(so_train.parse_args())
    (run / "skillopt_config.json").write_text(json.dumps(cfg, indent=2, default=str))

    _install_optimizer_transcript(run / "optimizer_transcript.jsonl")
    common = CommonRollout(run, arm=ARM, search_seed=a.seed, R=a.R)
    import inspect
    accepted = set(inspect.signature(SpreadsheetBenchAdapter.__init__).parameters) - {"self"}
    split = {n: [str(i["id"]) for i in json.loads((Path(a.split) / n / "items.json").read_text())]
             for n in ("train", "val")}
    adapter = Exp895SkillOptAdapter(common=common, run_dir=run, ledger_glm=run / "calls_glm.jsonl", opt_tag=opt_tag,
                                    allowed_ids=set(split["train"]) | set(split["val"]),
                                    **{k: cfg[k] for k in accepted if k in cfg})
    from skillopt.engine.trainer import ReflACTTrainer
    t0 = time.time()
    stop_reason, err = "completed", None
    try:
        ReflACTTrainer(cfg, adapter).train()
    except BudgetStop as e:
        stop_reason = f"BudgetStop: {e}"
    except Exception as e:  # noqa: BLE001
        import traceback
        stop_reason, err = "error", traceback.format_exc()
    wall = time.time() - t0

    best = out_root / "best_skill.md"
    best_doc = best.read_text() if best.exists() else seed_doc.read_text()
    champ_err = pk.unpack_to_dir(best_doc, run / "champion")
    hist = json.loads((out_root / "history.json").read_text()) if (out_root / "history.json").exists() else []
    evals = [json.loads(ln) for ln in (run / "skillopt_evals.jsonl").read_text().splitlines()] \
        if (run / "skillopt_evals.jsonl").exists() else []
    seed_files = pk.tree_digest(Path(os.environ["EXP895_SEED_DIR"]))
    summary = {
        "arm": ARM, "seed": a.seed, "R": a.R, "rollouts_used": common.spent,
        "binding_on_R": stop_reason.startswith("BudgetStop") and "token cap" not in stop_reason,
        "stop_reason": stop_reason, "error": err,
        "champion": {"dir": str(run / "champion"), "skill_hash": skill_hash(best_doc), "unpack_error": champ_err,
                     "identical_to_seed": pk.tree_digest(run / "champion") == seed_files,
                     "files": pk.tree_digest(run / "champion")},
        "n_candidates_evaluated": sum(1 for e in evals if e["phase"] in ("sel", "slow_sel")),
        "n_eval_calls": len(evals), "iterations": len(hist),
        "accepted": sum(1 for h in hist if "accept" in str(h.get("action", ""))),
        "rejected": sum(1 for h in hist if h.get("action") == "reject"),
        "skipped": sum(1 for h in hist if str(h.get("action", "")).startswith("skip")),
        "pack_damaged_candidates": adapter.n_damaged,
        "optimizer_tokens_non_cache_read": adapter._optimizer_tokens(),
        "wall_s": round(wall, 1),
    }
    (run / "run_summary.json").write_text(json.dumps(summary, indent=2))
    print("SKILLOPT_SUMMARY", json.dumps({k: summary[k] for k in ("rollouts_used", "R", "stop_reason", "iterations",
                                                                  "accepted", "rejected", "n_candidates_evaluated")}))
    if err:
        print(err, file=sys.stderr)
    return 0 if stop_reason != "error" else 1


if __name__ == "__main__":
    sys.exit(main())
