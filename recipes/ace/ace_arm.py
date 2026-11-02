"""exp895 ACE arm (issue skillberry-ai/cap-evolve#895 §7.8).

ace-agent/ace @ 82709de050e1db6e6ef2f07bcb0393560b94992a runs from its clone (competitors/ace), files UNMODIFIED.
The official batched flow `ace.ace_batch.ACEBatch.run(mode="offline")` is used: per mini-batch of K=4 train
tasks, parallel Generator + Reflector, ComBEE Curator proposals in floor(sqrt(K)) = 2 groups, an LLM reducer,
then parallel post-curate generation; a val evaluation at each epoch end picks the best playbook.

What this module supplies (each a recorded deviation, deviations_ace.json):
  * the Generator is replaced by `RolloutGenerator`: `generate()` materialises the playbook as a v2-seed
    candidate directory (playbook appended to prompt.md under "## Playbook (ACE)"; [skill]/[script] bullets
    written into skills/ace-playbook/) and scores it ONLY through
    `CommonRollout.evaluate(candidate_dir, [task_id], k=3)`. Its "response" is the gold-safe outcome: the
    k-trial scores, the scorer's feedback, the final code and the lowest-scoring trial's transcript;
  * a `SpreadsheetProcessor` (ACE's data_processor contract): correct = every measured trial passed;
    accuracy = mean over tasks of the k-trial mean hard score; no ground truth anywhere (no-GT mode);
  * the LLM clients: one OpenAI client on the GLM gateway (ACE only knows four hard-coded providers);
  * `is_api_error`, which ace_batch.py calls but the pinned repo never defines;
  * prompt text: the content-filter fix and the surface note (ace_prompts_patch.py, prompt_patch.diff);
  * an R guard: before each training batch, the batch's worst-case rollouts plus one full val evaluation
    must fit in R, else training stops and one final val evaluation of the current playbook is run.

Usage (inside the LSF job, see lsf_ace_search.sh):
    python ace_arm.py --run-dir RUN --seed S --R R --train-ids F --val-ids F [--max-epochs N]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import shutil
import sys
import threading
import time
from pathlib import Path

EXP = Path("/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-spread-worktrees/exp895")
REPO = Path("/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-spread-worktrees/sbv400-main")
ACE_DIR = EXP / "competitors/ace"
SEED_DIR = REPO / "templates/adapters/spreadsheetbench/seed_capability_v2"
ARM_DIR = Path(__file__).resolve().parent
for p in (str(EXP / "arms/common"), str(ACE_DIR), str(ARM_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import openai  # noqa: E402

import ace.ace_batch as ace_batch_mod  # noqa: E402  (upstream, unmodified)
from ace.ace_batch import ACEBatch, INCORRECT_DUE_TO_API_ERROR  # noqa: E402
from playbook_utils import parse_playbook_line  # noqa: E402

import ace_prompts_patch  # noqa: E402
from rollout import BudgetStop, CommonRollout  # noqa: E402

ARM = "ace"
K_TRIALS = 3
TRANSCRIPT_CAP = 20_000          # same cap as the GEPA arms' reflective records
SEED_SHA256 = {  # exp895/BUILD_RECORD.json seed_v2.files_sha256
    "prompt.md": "efa493dd57aee05d5563e4f709d5c9e2fde1fb9fc9f71a3b5a3472a40b723c72",
    "task_template.md": "841967412770441da3ba2785e37194524133aca50a49b489bb57f8e22bb84295",
    "skills/spreadsheet-helpers/SKILL.md": "6679c3f28a9fa25ca376d7d143e32a9d8783bd41e2f6b1829de756b3893dae1f",
}

# Issue §7.8 settings table + the official ace_batch.py flow with K=4 and ComBEE groups = floor(sqrt(K)).
BATCH_K = 4
ACE_SETTINGS = dict(
    batch_size=BATCH_K,
    curator_num_groups=int(BATCH_K ** 0.5),
    playbook_token_budget=80000,
    curator_frequency=1,
    max_num_rounds=1,
    use_bulletpoint_analyzer=False,
    json_mode=False,                 # upstream CLI default
    no_ground_truth=True,            # §7.8: no-GT mode
    augmented_shuffling=True,        # upstream CLI default (factor 2)
    task_name="spreadsheetbench",
)
ACE_MAX_TOKENS = 8000                # Reflector/Curator max_tokens (§7.8); temperature 0.0 is hard-coded upstream

PLAYBOOK_HEADER = "## Playbook (ACE)"
CITE_NOTE = ("The bullets below are a playbook of strategies learned from earlier tasks. Apply the relevant ones. "
             "When a bullet helps you, cite its id in square brackets (for example [code-00003]) in a comment "
             "of the code you write.")
REFLECTION_HEADER = "## Reflection (ACE)"
SKILL_NAME = "ace-playbook"
SKILL_IMPORT = "ace_playbook"
_SCRIPT_RE = re.compile(r"^\[script\]\s*([a-z][a-z0-9_]{0,48})\.py\s*:\s*([^\n]*)\n(.*)$", re.S)
_BULLET_ID_RE = re.compile(r"\[([a-z]{3,}-\d{5})\]")   # = ace.core.generator._extract_bullet_ids_regex
_SCORE_RE = re.compile(r"mean_hard_score=([0-9.]+)")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class InfraMissing(RuntimeError):
    """Every trial of a task stayed infra-errored after the common retries plus 2 re-evaluations."""


class StopTraining(Exception):
    """The next training batch (worst case) plus one final val evaluation would not fit in R."""


# ---- [skill]/[script] bullets ------------------------------------------------------------------------
def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("\r", "").replace("\n", "\\n")


def _unesc(s: str) -> str:
    return re.sub(r"\\(\\|n)", lambda m: "\\" if m.group(1) == "\\" else "\n", s)


def _kind(content: str) -> str:
    c = content.lstrip()
    return "script" if c.startswith("[script]") else "skill" if c.startswith("[skill]") else "text"


def escape_surface_ops(operations):
    """Keep the playbook one-bullet-per-line (ACE's own invariant: parse_playbook_line works per line, and a
    '##' line inside a script would open a section) by storing [skill]/[script] bullet content with escaped
    newlines. Content that has no real newline but literal '\\n' is taken as already escaped."""
    out = []
    for op in operations:
        c = op.get("content", "") if isinstance(op, dict) else ""
        if isinstance(op, dict) and _kind(c) != "text" and ("\n" in c or "\\n" not in c):
            op = {**op, "content": _esc(c)}
        out.append(op)
    return out


def split_playbook(playbook: str):
    """-> (prompt_playbook_text, skill_bullets[(id, text)], scripts{name: (id, desc, source)}, unparsed[ids])."""
    keep, skills, scripts, unparsed = [], [], {}, []
    for line in playbook.split("\n"):
        p = parse_playbook_line(line)
        if p and _kind(p["content"]) != "text":
            content = _unesc(p["content"]).lstrip()
            if _kind(content) == "skill":
                skills.append((p["id"], content[len("[skill]"):].strip()))
            else:
                m = _SCRIPT_RE.match(content)
                if m and m.group(3).strip():
                    scripts[m.group(1)] = (p["id"], m.group(2).strip(), m.group(3).rstrip() + "\n")  # newest wins
                else:
                    unparsed.append(p["id"])
            continue
        keep.append(line)
    return "\n".join(keep), skills, scripts, unparsed


def _has_bullets(text: str) -> bool:
    return any(parse_playbook_line(x) for x in text.split("\n"))


# ---- candidates --------------------------------------------------------------------------------------
class CandidateStore:
    """(playbook, reflection) -> a v2-seed candidate directory. An empty playbook and no reflection is the seed,
    byte-identical. Directory names are content hashes, so a repeat costs nothing to build."""

    def __init__(self, root: Path, skill_bullets: bool):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.skill_bullets = skill_bullets
        self._lock = threading.Lock()
        self._index = root / "index.jsonl"
        for rel, h in SEED_SHA256.items():
            got = _sha((SEED_DIR / rel).read_bytes())
            assert got == h, f"seed file {rel} sha256 {got} != BUILD_RECORD {h}"
        self.seed_prompt = (SEED_DIR / "prompt.md").read_text(encoding="utf-8")

    def files_for(self, playbook: str, reflection: str = "") -> dict[str, bytes]:
        """Relative path -> bytes for the files that differ from / add to the seed."""
        if self.skill_bullets:
            text, skills, scripts, unparsed = split_playbook(playbook)
        else:
            text, skills, scripts, unparsed = playbook, [], {}, []
        files: dict[str, bytes] = {}
        parts = []
        if _has_bullets(text):
            parts.append(f"{PLAYBOOK_HEADER}\n\n{CITE_NOTE}\n\n{text.strip()}")
        if reflection and reflection.strip() and reflection.strip() != "(empty)":
            parts.append(f"{REFLECTION_HEADER}\n\nA diagnosis of an earlier attempt at THIS task:\n\n{reflection.strip()}")
        if parts:
            files["prompt.md"] = (self.seed_prompt.rstrip("\n") + "\n\n" + "\n\n".join(parts) + "\n").encode("utf-8")
        if skills or scripts:
            body = [f"---\nname: {SKILL_NAME}\ndescription: Notes and deterministic helper scripts curated by ACE "
                    f"from earlier tasks. Cite a note's id when it helps.\n---\n", f"# {SKILL_NAME}\n"]
            if scripts:
                body.append("## Scripts\n")
                for name, (bid, desc, _) in sorted(scripts.items()):
                    body.append(f"- [{bid}] `skills.{SKILL_IMPORT}.{name}`: {desc}")
                body.append("")
            if skills:
                body.append("## Notes\n")
                body += [f"- [{bid}] {txt}" for bid, txt in skills]
            files[f"skills/{SKILL_NAME}/SKILL.md"] = ("\n".join(body).rstrip() + "\n").encode("utf-8")
            for name, (_, _, src) in scripts.items():
                files[f"skills/{SKILL_NAME}/scripts/{name}.py"] = src.encode("utf-8")
        return files

    def materialize(self, playbook: str, reflection: str = "") -> Path:
        files = self.files_for(playbook, reflection)
        if not files:
            name = "seed"
        else:
            h = hashlib.sha256()
            for rel in sorted(files):
                h.update(rel.encode() + b"\0" + files[rel] + b"\0")
            name = ("refl_" if reflection and reflection.strip() not in ("", "(empty)") else "pb_") + h.hexdigest()[:12]
        d = self.root / name
        with self._lock:
            if d.exists():
                return d
            tmp = self.root / f".{name}.tmp"
            if tmp.exists():
                shutil.rmtree(tmp)
            shutil.copytree(SEED_DIR, tmp)
            for rel, b in files.items():
                (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
                (tmp / rel).write_bytes(b)
            tmp.rename(d)
            with open(self._index, "a") as f:
                f.write(json.dumps({"name": name, "t": time.time(), "files": {r: _sha(b) for r, b in files.items()},
                                    "has_reflection": name.startswith("refl_")}) + "\n")
        return d


# ---- rendering a scored task as the Generator's "response" -----------------------------------------
def render_transcript(trace) -> str:
    """The agent's turns (system message dropped: it is the candidate itself), capped at TRANSCRIPT_CAP chars:
    head (task + first turns) and tail (where the episode ended)."""
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
    return text[:head] + marker + text[-(TRANSCRIPT_CAP - head - len(marker)):]


def final_code(trace) -> str:
    for m in reversed(trace or []):
        if isinstance(m, dict) and m.get("role") == "assistant":
            blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", str(m.get("content", "")), re.S)
            if blocks:
                return blocks[-1].strip()
    return "(no code block found)"


def cited_ids(traces) -> list[str]:
    seen = []
    for tr in traces:
        for m in tr or []:
            if isinstance(m, dict) and m.get("role") == "assistant":
                for b in _BULLET_ID_RE.findall(str(m.get("content", ""))):
                    if b not in seen:
                        seen.append(b)
    return seen


class RolloutGenerator:
    """Drop-in for ace.core.generator.Generator: generate(question, playbook, context, reflection, ...)
    -> (response_text, bullet_ids, call_info). No LLM call of its own: the agent is the common rollout."""

    def __init__(self, ro: CommonRollout, store: CandidateStore, log_path: Path):
        self.ro, self.store = ro, store
        self.model = os.environ.get("MODEL", "gemma-via-common-rollout")
        self.max_tokens = 0
        self._log = open(log_path, "a", buffering=1)
        self._lock = threading.Lock()

    @staticmethod
    def _task_id(context: str) -> str:
        m = re.search(r"(?m)^task_id:\s*(\S+)\s*$", context or "")
        if not m:
            raise ValueError("sample context carries no task_id line")
        return m.group(1)

    def generate(self, question, playbook, context="", reflection="(empty)", use_json_mode=False,
                 call_id="gen", log_dir=None):
        tid = self._task_id(context)
        split = "val" if str(call_id).startswith("test_") else "train"
        cdir = self.store.materialize(playbook, reflection)
        t0 = time.time()
        res = self.ro.evaluate(cdir, [tid], k=K_TRIALS, candidate_id=cdir.name, split=split)  # BudgetStop first
        tr, counted, reevals = res.per_task[tid], res.counted, 0
        while tr.missing and reevals < 2:     # a task with no measured trial is MISSING, never 0 (§0.3)
            reevals += 1
            again = self.ro.evaluate(cdir, [tid], k=K_TRIALS, candidate_id=cdir.name, split=split)
            tr, counted = again.per_task[tid], counted + again.counted
        if tr.missing:
            self._write({"call_id": call_id, "task_id": tid, "candidate": cdir.name, "split": split,
                         "missing": True, "spent": self.ro.spent})
            raise InfraMissing(f"task {tid}: every trial stayed infra-errored ({call_id})")
        ok = [j for j in range(len(tr.trials)) if not tr.infra[j]]
        trials = [tr.trials[j] for j in ok]
        mean = sum(trials) / len(trials)
        worst = min(trials)
        jw = max(j for j in ok if tr.trials[j] == worst)
        lines = [f"Outcome of the spreadsheet agent on this task ({len(trials)} measured trials).",
                 f"Mean hard score: {mean:.3f}. Per-trial scores: {trials}. The transcript below is trial {jw}, "
                 f"the lowest-scoring one.",
                 f"Scorer feedback on that trial (gold-safe): {tr.feedback[jw]}"]
        if tr.errors[jw]:
            lines.append(f"That trial ended with a candidate-caused error: {str(tr.errors[jw])[:1500]}")
        lines += ["", "Final code of that trial:", "```python", final_code(tr.traces[jw]), "```", "",
                  "Transcript of that trial (system prompt omitted):", render_transcript(tr.traces[jw]), "",
                  f"Finish[mean_hard_score={mean:.4f}; trials={','.join(f'{x:g}' for x in trials)}]"]
        response = "\n".join(lines)
        ids = cited_ids([tr.traces[j] for j in ok])
        info = {"role": "generator", "call_id": call_id, "model": self.model, "candidate": cdir.name,
                "total_time": time.time() - t0, "counted_rollouts": counted}
        self._write({"call_id": call_id, "task_id": tid, "candidate": cdir.name, "split": split, "mean": mean,
                     "trials": trials, "trial_seeds": tr.trial_seeds, "reevals": reevals, "counted": counted,
                     "cited_bullets": ids, "has_reflection": cdir.name.startswith("refl_"),
                     "skill_md_in_system_prompt": _skill_seen(tr.traces[jw]), "spent": self.ro.spent,
                     "wall_s": round(time.time() - t0, 1), "response": response})
        return response, ids, info

    def _write(self, rec):
        with self._lock:
            self._log.write(json.dumps({"t": time.time(), **rec}, default=str) + "\n")


def _skill_seen(trace) -> list[str]:
    sysmsg = next((m.get("content", "") for m in (trace or []) if isinstance(m, dict) and m.get("role") == "system"), "")
    return re.findall(r"## Helper skill `([^`]+)`", str(sysmsg))


# ---- ACE's data_processor contract -----------------------------------------------------------------
class SpreadsheetProcessor:
    """No ground truth (target is ""): the environment signal is the common scorer's k-trial result."""

    @staticmethod
    def score_of(answer: str):
        m = _SCORE_RE.search(str(answer))
        return float(m.group(1)) if m else None

    def answer_is_correct(self, predicted: str, ground_truth: str) -> bool:
        s = self.score_of(predicted)
        return s is not None and s >= 1.0 - 1e-9          # every measured trial passed

    def evaluate_accuracy(self, out, target) -> float:
        vals = [self.score_of(x) for x in out]
        vals = [0.0 if v is None else v for v in vals]       # an API-error placeholder counts 0 (upstream)
        return sum(vals) / len(vals) if vals else 0.0


# ---- the ACE system --------------------------------------------------------------------------------
class ExpACEBatch(ACEBatch):
    """ACEBatch, unchanged, plus ONE override: the R guard in front of each training batch."""

    def __init__(self, *a, ro: CommonRollout, val_n: int, rounds: int, **kw):
        super().__init__(*a, **kw)
        self._ro, self._val_n, self._rounds = ro, val_n, rounds
        self.batches_run = 0

    def worst_case(self, n_samples: int) -> int:
        # Phase 1 generation + one regeneration per reflection round + Phase 3 post-curate generation
        return n_samples * K_TRIALS * (2 + self._rounds)

    def _train_batch(self, batch, *a, **kw):
        need = self.worst_case(len(batch)) + self._val_n * K_TRIALS
        if self._ro.spent + need > self._ro.R:
            raise StopTraining(f"next batch (<= {self.worst_case(len(batch))}) + final val ({self._val_n * K_TRIALS}) "
                               f"would exceed R ({self._ro.spent}/{self._ro.R})")
        out = super()._train_batch(batch, *a, **kw)
        self.batches_run += 1
        return out


def make_clients_factory(glm_base: str, tag: str):
    def initialize_clients(api_provider):
        c = openai.OpenAI(api_key="tag-not-a-secret", base_url=f"{glm_base}/t/{tag}/v1", timeout=3600)
        print(f"Using the exp895 GLM gateway for reflector/curator ({api_provider})")
        return c, c, c
    return initialize_clients


def is_api_error(e) -> bool:
    """ace_batch.py calls is_api_error() but the pinned repo defines it nowhere (NameError on any exception).
    An API/infra failure: an OpenAI-client error that survived llm.py's own retries, or a task whose every
    trial stayed infra-errored. BudgetStop and everything else re-raise, as upstream's default does."""
    return isinstance(e, (InfraMissing, openai.APIError))


# ---------------------------------------------------------------------------------------------------
def _ids(path) -> list[str]:
    return [ln.strip() for ln in Path(path).read_text().splitlines() if ln.strip()]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--R", type=int, required=True)
    ap.add_argument("--train-ids", required=True)
    ap.add_argument("--val-ids", required=True)
    ap.add_argument("--max-epochs", type=int, default=1000, help="smoke: 1. Default: R binds")
    ap.add_argument("--test-workers", type=int, default=BATCH_K)
    ap.add_argument("--no-skill-bullets", action="store_true", help="ablation: no [skill]/[script] surface")
    ap.add_argument("--glm-base", default="http://127.0.0.1:4115")
    a = ap.parse_args(argv)
    run = Path(a.run_dir)
    t0 = time.time()
    skill_bullets = not a.no_skill_bullets
    random.seed(a.seed)                           # ACE's augmented shuffling uses the global RNG

    # prompts (in memory; upstream files untouched)
    patch_report = ace_prompts_patch.apply(skill_bullets=skill_bullets)
    ace_prompts_patch.write_diff(run / "prompt_patch.diff", skill_bullets=skill_bullets)

    ro = CommonRollout(run, arm=ARM, search_seed=a.seed, R=a.R)
    store = CandidateStore(run / "candidates", skill_bullets)
    tasks = ro._tasks  # noqa: SLF001 — the shared rollout's task table (gold-free inputs)
    train_ids, val_ids = _ids(a.train_ids), _ids(a.val_ids)
    random.Random(1000 + a.seed).shuffle(train_ids)   # per-seed train order (upstream: file order)

    def sample(t):
        inp = tasks[t].input
        return {"question": inp["instruction"],
                "context": (f"task_id: {t}\ninstruction_type: {inp['instruction_type']}\n"
                            f"answer_position: {inp['answer_position']}\ninstruction: {inp['instruction']}"),
                "target": "", "task_id": t}

    train, val = [sample(t) for t in train_ids], [sample(t) for t in val_ids]

    tag = f"exp895-{ARM}-s{a.seed}:optimizer"
    ace_batch_mod.initialize_clients = make_clients_factory(a.glm_base, tag)
    ace_batch_mod.is_api_error = is_api_error
    ace_batch_mod.apply_curator_operations = (lambda pb, ops, nid, _f=ace_batch_mod.apply_curator_operations:
                                              _f(pb, escape_surface_ops(ops), nid)) if skill_bullets \
        else ace_batch_mod.apply_curator_operations
    val_log = open(run / "val_evals.jsonl", "a", buffering=1)
    val_records = []
    _orig_evaluate_test_set = ace_batch_mod.evaluate_test_set

    def recording_evaluate_test_set(data_processor, generator, playbook, samples, *args, **kw):
        res, err = _orig_evaluate_test_set(data_processor, generator, playbook, samples, *args, **kw)
        cand = store.materialize(playbook)
        rec = {"t": time.time(), "candidate": cand.name, "accuracy": res.get("accuracy"), "n_scored": res.get("total"),
               "n_samples": len(samples), "spent": ro.spent, "playbook_sha256": _sha(playbook.encode())}
        val_records.append({**rec, "playbook": playbook})
        val_log.write(json.dumps(rec) + "\n")
        return res, err

    ace_batch_mod.evaluate_test_set = recording_evaluate_test_set

    ace_sys = ExpACEBatch(api_provider="exp895-gateway", generator_model="common-rollout",
                          reflector_model="rits/zai-org/glm-5-3", curator_model="rits/zai-org/glm-5-3",
                          max_tokens=ACE_MAX_TOKENS, initial_playbook=None, use_bulletpoint_analyzer=False,
                          ro=ro, val_n=len(val), rounds=ACE_SETTINGS["max_num_rounds"])
    ace_sys.generator = RolloutGenerator(ro, store, run / "generator_calls.jsonl")
    seed_playbook = ace_sys.playbook
    config = {**ACE_SETTINGS, "num_epochs": a.max_epochs, "eval_steps": len(train), "save_steps": BATCH_K,
              "save_dir": str(run / "ace"), "test_workers": a.test_workers, "api_provider": "exp895-gateway",
              "online_eval_frequency": 15, "curator_batch_size": None, "bulletpoint_analyzer_threshold": 0.90,
              "initial_playbook_path": None, "mode": "offline"}

    stop_reason = ""
    try:
        ace_sys.run(mode="offline", train_samples=train, val_samples=val, test_samples=None,
                    data_processor=SpreadsheetProcessor(), config=config)
        stop_reason = f"max_epochs={a.max_epochs}"
    except StopTraining as e:
        stop_reason = f"StopTraining: {e}"
    except BudgetStop as e:          # should not happen (the guard reserves the worst case); recorded if it does
        stop_reason = f"BudgetStop: {e}"
    print("ACE_STOP", stop_reason, flush=True)

    # One final val evaluation of the current playbook, unless it is the one evaluated last (§7.8).
    if stop_reason.startswith("StopTraining") and ace_sys.playbook != (val_records[-1]["playbook"] if val_records else None) \
            and ace_sys.batches_run > 0:
        recording_evaluate_test_set(SpreadsheetProcessor(), ace_sys.generator, ace_sys.playbook, val,
                                    ace_sys.max_tokens, None, max_workers=a.test_workers, use_json_mode=False)

    # Champion: upstream's rule (best_accuracy starts at 0.0 with the initial playbook; strict > wins).
    best_acc, best_pb = 0.0, seed_playbook
    for r in val_records:
        if r["accuracy"] is not None and r["accuracy"] > best_acc:
            best_acc, best_pb = r["accuracy"], r["playbook"]
    champ = store.materialize(best_pb)
    if (run / "champion").exists():
        shutil.rmtree(run / "champion")
    shutil.copytree(champ, run / "champion")
    (run / "best_playbook.txt").write_text(best_pb)
    (run / "final_playbook.txt").write_text(ace_sys.playbook)

    gens = [json.loads(x) for x in (run / "generator_calls.jsonl").read_text().splitlines()] \
        if (run / "generator_calls.jsonl").exists() else []
    _, sk, sc, unp = split_playbook(ace_sys.playbook) if skill_bullets else ("", [], {}, [])
    summary = {
        "arm": ARM, "seed": a.seed, "R": a.R, "rollouts_used": ro.spent, "stop_reason": stop_reason,
        "binding_on_R": stop_reason.startswith(("StopTraining", "BudgetStop")),
        "champion": champ.name, "champion_val_score": best_acc if val_records else None,
        "val_evaluations": [{k: v for k, v in r.items() if k != "playbook"} for r in val_records],
        "n_candidates_evaluated": len({g["candidate"] for g in gens if "candidate" in g}),
        "n_playbook_candidates_evaluated": len({g["candidate"] for g in gens if g.get("candidate", "").startswith(("pb_", "seed"))}),
        "batches_run": ace_sys.batches_run, "generate_calls": len(gens),
        "final_playbook": {"bullets": sum(1 for x in ace_sys.playbook.split("\n") if parse_playbook_line(x)),
                           "skill_bullets": len(sk), "scripts": sorted(sc), "unparsed_script_bullets": unp},
        "train_ids_n": len(train), "val_ids_n": len(val), "wall_s": round(time.time() - t0, 1),
        "settings": {**ACE_SETTINGS, "k": K_TRIALS, "max_tokens": ACE_MAX_TOKENS, "max_epochs": a.max_epochs,
                     "eval_steps": len(train), "test_workers": a.test_workers, "skill_bullets": skill_bullets},
        "prompt_patch": patch_report,
        "upstream": "ace-agent/ace@82709de050e1db6e6ef2f07bcb0393560b94992a (ace.ace_batch.ACEBatch, offline)",
    }
    (run / "run_summary.json").write_text(json.dumps(summary, indent=1))
    print("ACE_ARM_DONE", json.dumps({k: summary[k] for k in ("rollouts_used", "R", "stop_reason", "champion",
                                                               "n_candidates_evaluated", "batches_run")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
