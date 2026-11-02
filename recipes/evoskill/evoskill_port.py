"""exp895 EvoSkill arm (issue skillberry-ai/cap-evolve#895 §7.4).

EvoSkill (sentient-agi/EvoSkill @ 36f6f04952293d7054145550c2b9f0b0411bff1c, competitors/evoskill) runs from its own
source tree, UNMODIFIED on disk: `src.loop.SelfImprovingLoop`, `src.registry.ProgramManager` (git branches per
program, frontier tags), `src.cache.RunCache`, the skill proposer + skill generator profiles and prompts, and the
Claude executor (`claude_agent_sdk`). What this module supplies or replaces (each item is in deviations_evoskill.json):

  * `CapEvolveBaseAgent` replaces the base agent. `run(question)` materialises the CURRENT program (the checked-out
    git branch) as a v2-seed candidate directory and runs `CommonRollout.evaluate(candidate_dir, [task_id], k=3)`.
    It returns `final_answer="pass"` when the k-trial mean (measured trials only) is >= 2/3, else `"fail"`.
    k stays INSIDE run(), so EvoSkill's run cache (keyed by question + program tree) cannot collapse trials.
  * The proposer and generator are EvoSkill's own Claude-Code agents with EvoSkill's own options. Each factory call
    adds only `cli_path` (the exp895 bwrap sandbox shim), `max_turns=30`, a `can_use_tool` approver and a stderr log.
    The approver allows exactly the tools EvoSkill's profile lists. Writes are allowed only inside the project dir and
    never into `.git`. Claude Code 2.1.304 protects `.claude/skills/` from writes even under acceptEdits, which is where
    EvoSkill writes its skills. Its non-interactive mode has no one to approve them, so they need this approver.
  * The SURFACE_CONTRACT goes in verbatim, plus an arm-specific note mapping the three surfaces onto EvoSkill's
    layout. It is EvoSkill's native `task_constraints` for the proposer and is appended to the generator's query.
  * The 17-minute asyncio limit in `src.evaluation.evaluate` is lifted at run time (no file edit). The module's
    `asyncio` name points to a proxy whose `timeout()` has no deadline.
  * `_evaluate` is overridden to drop infra-missing tasks (no measured trial after retries) from the val mean
    (issue §0.3). Everything else is upstream's code: pass = 1, fail = 0, mean over tasks.
  * An iteration guard (`_select_parent`) raises `BudgetExhausted` before an iteration whose worst case (training
    sample + one full val evaluation) would not fit in R.

Layout inside the EvoSkill project (a git repo the optimizer can see, under runs/evoskill/<NAME>/project):
    .claude/skills/<name>/SKILL.md, scripts/*.py  -> candidate skills/<name>/       (EvoSkill's native skill dir)
    .claude/skills/prompt.md                      -> candidate prompt.md            (hashed by RunCache, committed)
    task_template.md                              -> the v2 seed bytes, never edited (skill mode)
    .claude/skills/{brainstorming,skill-creator}  -> EvoSkill's own optimizer meta-skills; never given to the agent
"""
from __future__ import annotations

import asyncio
import contextvars
import dataclasses
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

EXP = Path("/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-spread-worktrees/exp895")
REPO = Path("/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-spread-worktrees/sbv400-main")
UPSTREAM = EXP / "competitors/evoskill"
SEED_DIR = REPO / "templates/adapters/spreadsheetbench/seed_capability_v2"
CONTRACT = EXP / "arms/common/SURFACE_CONTRACT.md"
SHIM = EXP / "tools/sandbox/claude"
sys.path.insert(0, str(EXP / "arms/common"))
sys.path.insert(0, str(UPSTREAM))

ARM = "evoskill"
K = 3
PASS_THRESHOLD = 2.0 / 3.0          # §7.4: pass when the k=3 mean >= 2/3
OPT_MAX_TURNS = 30                  # §7.4
TRANSCRIPT_CAP = 20_000             # same cap the GEPA reflective dataset uses
META_SKILLS = ("brainstorming", "skill-creator")   # EvoSkill's own optimizer skills (upstream .claude/skills)
PROMPT_REL = ".claude/skills/prompt.md"
SEED_SHA256 = {  # exp895/BUILD_RECORD.json seed_v2.files_sha256
    "prompt.md": "efa493dd57aee05d5563e4f709d5c9e2fde1fb9fc9f71a3b5a3472a40b723c72",
    "task_template.md": "841967412770441da3ba2785e37194524133aca50a49b489bb57f8e22bb84295",
    "skills/spreadsheet-helpers/SKILL.md": "6679c3f28a9fa25ca376d7d143e32a9d8783bd41e2f6b1829de756b3893dae1f",
}
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}

ARM_NOTE = """### Where the three surfaces live in this EvoSkill project
- `skills/<name>/SKILL.md` and `skills/<name>/scripts/*.py` are `.claude/skills/<name>/SKILL.md` and `.claude/skills/<name>/scripts/*.py` here. Every skill directory you create or edit there (except `brainstorming` and `skill-creator`, which are your own design tools and are never given to the agent) is given to the agent.
- `prompt.md` is the file `.claude/skills/prompt.md`. You may edit it.
- `task_template.md` is not editable in this optimizer.
- A helper must be importable as plain Python: put it at `.claude/skills/<name>/scripts/<script>.py` and document in that skill's SKILL.md when to call it and how (`from skills.<name_with_underscores>.<script> import ...`)."""

_split_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("exp895_split", default="train")


class BudgetExhausted(BaseException):
    """R would be exceeded. A BaseException so EvoSkill's `except Exception` (which scores an error 0) cannot
    swallow it."""


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def contract_block() -> str:
    return CONTRACT.read_text(encoding="utf-8").strip() + "\n\n" + ARM_NOTE


# ---------------------------------------------------------------------------------------------------------
# Lift the 17-minute asyncio eval timeout (issue §7.4) without editing upstream: evaluate.py does
# `async with asyncio.timeout(1020)` on its module-global `asyncio`; point that name at a proxy.
class _AsyncioNoEvalDeadline:
    def __getattr__(self, name):
        return getattr(asyncio, name)

    @staticmethod
    def timeout(_seconds):
        return asyncio.timeout(None)


def lift_eval_timeout() -> None:
    import src.evaluation.evaluate as ev
    ev.asyncio = _AsyncioNoEvalDeadline()


# ---------------------------------------------------------------------------------------------------------
def render_transcript(trace) -> str:
    """The agent's turns (system message dropped: it is the candidate itself), capped at TRANSCRIPT_CAP chars."""
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


# ---------------------------------------------------------------------------------------------------------
class CandidateMaterializer:
    """Current EvoSkill program tree -> a v2-seed candidate dir (prompt.md, task_template.md, skills/)."""

    def __init__(self, project: Path, root: Path):
        self.project, self.root = project, root
        root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._index = root / "index.jsonl"
        self._seed_key = None

    def _files(self) -> dict[str, bytes]:
        files: dict[str, bytes] = {}
        p = self.project / PROMPT_REL
        files["prompt.md"] = p.read_bytes() if p.is_file() else (SEED_DIR / "prompt.md").read_bytes()
        files["task_template.md"] = (SEED_DIR / "task_template.md").read_bytes()
        sk = self.project / ".claude/skills"
        for d in sorted(x for x in sk.iterdir() if x.is_dir()) if sk.is_dir() else []:
            if d.name in META_SKILLS or not (d / "SKILL.md").is_file():
                continue
            for f in sorted(d.rglob("*")):
                if f.is_file() and "__pycache__" not in f.parts:
                    files[f"skills/{d.name}/{f.relative_to(d)}"] = f.read_bytes()
        return files

    @staticmethod
    def _key(files: dict[str, bytes]) -> str:
        h = hashlib.sha256()
        for k in sorted(files):
            h.update(k.encode() + b"\0" + files[k] + b"\0")
        return h.hexdigest()[:12]

    def seed_key(self) -> str:
        if self._seed_key is None:
            files = {str(f.relative_to(SEED_DIR)): f.read_bytes() for f in SEED_DIR.rglob("*") if f.is_file()}
            self._seed_key = self._key(files)
        return self._seed_key

    def current(self, program: str) -> Path:
        with self._lock:
            files = self._files()
            key = self._key(files)
            name = "seed" if key == self.seed_key() else f"{program}_{key}"
            d = self.root / name
            if d.exists():
                return d
            tmp = self.root / f".{name}.tmp"
            if tmp.exists():
                shutil.rmtree(tmp)
            for rel, b in files.items():
                (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
                (tmp / rel).write_bytes(b)
            (tmp / "skills").mkdir(exist_ok=True)
            tmp.rename(d)
            with open(self._index, "a") as f:
                f.write(json.dumps({"name": name, "key": key, "program": program, "t": time.time(),
                                    "sha256": {k: _sha(v) for k, v in files.items()}}) + "\n")
            return d


# ---------------------------------------------------------------------------------------------------------
class CapEvolveBaseAgent:
    """EvoSkill's base agent, replaced: run() = CommonRollout.evaluate(current candidate, [task], k=3)."""

    def __init__(self, ro, mat: CandidateMaterializer, manager, tasks: dict, *, max_parallel: int,
                 log_path: Path):
        from src.schemas import AgentResponse
        self.ro, self.mat, self.manager, self.tasks = ro, mat, manager, tasks
        self.response_model = AgentResponse
        self._sem = asyncio.Semaphore(max(1, max_parallel))
        self._log = open(log_path, "a", buffering=1)

    def _get_options(self) -> dict:
        # Read by EvoSkill for ProgramConfig (options_to_config) and as the model part of its run-cache key.
        return {"system": "exp895 CommonRollout (Gemma-4-31B-it via the CapEvolve SpreadsheetBench adapter); "
                          "candidate = .claude/skills/* + .claude/skills/prompt.md + seed task_template.md",
                "tools": {}, "model": os.environ.get("MODEL", "")}

    async def run(self, question: str):
        from src.harness import AgentTrace
        tid = question.split("\n", 1)[0].removeprefix("TASK::").strip()
        if tid not in self.tasks:   # only this search's train/val ids (CommonRollout itself knows all 400)
            raise BudgetExhausted(f"refusing a task outside this search's train/val ids")
        split = _split_ctx.get()
        async with self._sem:
            program = self.manager.get_current_name()
            cand = self.mat.current(program)
            t0 = time.time()
            try:
                res = await asyncio.to_thread(self.ro.evaluate, cand, [tid], k=K, candidate_id=cand.name, split=split)
            except Exception as e:  # BudgetStop: let it escape EvoSkill's except-Exception
                from rollout import BudgetStop
                if isinstance(e, BudgetStop):
                    raise BudgetExhausted(str(e)) from e
                raise
        tr = res.per_task[tid]
        if tr.missing:
            verdict, mean = "missing", None
        else:
            mean = tr.mean
            verdict = "pass" if mean >= PASS_THRESHOLD - 1e-9 else "fail"
        trials = [None if bad else r for r, bad in zip(tr.trials, tr.infra)]
        fb = "\n".join(f"- trial {j}: reward {'infra-missing' if trials[j] is None else trials[j]}; scorer feedback: "
                       f"{str(tr.feedback[j] or '')[:600]}" for j in range(len(trials)))
        reasoning = (f"k={K} trials of task {tid}; per-trial rewards {trials}; mean over measured trials "
                     f"{'n/a' if mean is None else round(mean, 4)}; pass threshold mean >= 2/3 -> {verdict}.\n{fb}")
        result = ("Transcript of the lowest-scoring trial (the agent is a Python-only CodeAct agent; "
                  "the system prompt = the candidate is omitted):\n\n" + render_transcript(tr.worst_trace))
        self._log.write(json.dumps({"t": t0, "wall_s": round(time.time() - t0, 1), "task_id": tid, "split": split,
                                    "program": program, "candidate": cand.name, "trials": trials,
                                    "verdict": verdict, "eval_call": res.eval_call}) + "\n")
        return AgentTrace(duration_ms=int((time.time() - t0) * 1000), total_cost_usd=0.0, num_turns=len(trials),
                          usage={}, result=result, is_error=False, model=os.environ.get("MODEL", ""),
                          output=self.response_model(final_answer=verdict, reasoning=reasoning), messages=[])


def scorer(question: str, predicted: str, ground_truth: str) -> float:
    """pass -> 1, fail -> 0. 'missing' (no measured trial) -> 1 so it is never handed to the proposer as a failure;
    on val it never reaches this scorer (EvoSkillLoop._evaluate drops it)."""
    p = (predicted or "").strip().lower()
    return 1.0 if p in ("pass", "missing") else 0.0


# ---------------------------------------------------------------------------------------------------------
def _ser(m) -> dict:
    d = dataclasses.asdict(m) if dataclasses.is_dataclass(m) else {"repr": repr(m)}
    d["_type"] = type(m).__name__
    return d


def make_optimizer_agent(options_fn, response_model, project: Path, transcript: Path, perm_log: Path, *,
                         role: str, model: str = None, query_suffix: str = ""):
    """EvoSkill's own Agent + EvoSkill's own profile options; adds only the sandbox cli_path, max_turns 30,
    the scoped approver and logging."""
    from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny
    from src.harness import Agent

    model = model or os.environ.get("EXP895_OPT_MODEL", "rits/zai-org/glm-5-3")
    project = project.resolve()
    tlog = open(transcript, "a", buffering=1)
    plog = open(perm_log, "a", buffering=1)
    slog = open(transcript.parent / "optimizer_stderr.log", "a", buffering=1)
    # EvoSkill's own tool list for this role, plus the CLI's StructuredOutput tool (how --json-schema output is
    # returned; upstream relies on it for every agent's structured output).
    allowed = set(options_fn(model=model, project_root=str(project)).allowed_tools) | {"StructuredOutput"}

    async def approver(tool_name, tool_input, _ctx):
        ok, why = tool_name in allowed, "tool in EvoSkill's allowed list"
        if not ok:
            why = "tool not in EvoSkill's allowed list for this role"
        elif tool_name in WRITE_TOOLS:
            raw = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
            p = Path(raw if os.path.isabs(raw) else project / raw).resolve()
            inside = p == project or project in p.parents
            ok = inside and ".git" not in p.relative_to(project).parts if inside else False
            why = "write inside the project" if ok else "write outside the project or into .git"
        plog.write(json.dumps({"t": time.time(), "role": role, "tool": tool_name, "allow": ok, "why": why,
                               "path": tool_input.get("file_path") or tool_input.get("command", "")[:300]}) + "\n")
        return PermissionResultAllow() if ok else PermissionResultDeny(message=f"exp895 approver: {why}")

    def factory():
        o = options_fn(model=model, project_root=str(project))
        return dataclasses.replace(o, cli_path=str(SHIM), max_turns=OPT_MAX_TURNS, can_use_tool=approver,
                                   stderr=lambda line: slog.write(f"[{role}] {line}\n"))

    class LoggedAgent(Agent):
        async def _execute_query(self, query):
            t0 = time.time()
            try:
                msgs = await super()._execute_query(query)
            except BaseException as e:
                tlog.write(json.dumps({"t": t0, "role": role, "query": query, "error": repr(e)[:2000]}) + "\n")
                raise
            tlog.write(json.dumps({"t": t0, "wall_s": round(time.time() - t0, 1), "role": role, "query": query,
                                   "messages": [_ser(m) for m in msgs]}, default=str) + "\n")
            return msgs

        async def run(self, query):
            return await super().run(query + query_suffix if query_suffix else query)

    return LoggedAgent(factory, response_model)


# ---------------------------------------------------------------------------------------------------------
def make_loop_class():
    from src.loop import SelfImprovingLoop

    class EvoSkillLoop(SelfImprovingLoop):
        """Upstream loop; two hooks only: the R iteration guard and the infra-missing-aware val mean."""
        ro = None
        per_iter_worst = 0

        def _select_parent(self, iteration: int = 0) -> str:
            if iteration > 0 and not self.ro.would_fit(self.per_iter_worst, 1):
                raise BudgetExhausted(f"iteration guard: iteration {iteration} needs up to {self.per_iter_worst} "
                                      f"rollouts, {self.ro.remaining()} of R={self.ro.R} left")
            return super()._select_parent(iteration)

        async def _evaluate(self, data):
            from src.evaluation import evaluate_agent_parallel
            tok = _split_ctx.set("val")
            try:
                qa = [(q, a) for q, a, _ in data]
                results = await evaluate_agent_parallel(self.agents.base, qa, max_concurrent=self.config.concurrency,
                                                        cache=self.cache)
            finally:
                _split_ctx.reset(tok)
            score, n = 0.0, 0
            for r in results:
                if r.trace is not None:
                    self._iter_cost += r.trace.total_cost_usd
                if r.trace is not None and r.trace.output is not None and r.trace.output.final_answer == "missing":
                    continue   # §0.3: no measured trial -> missing data, not a 0
                n += 1
                if r.trace is None or r.trace.output is None:
                    continue
                score += self.scorer(r.question, r.trace.output.final_answer, r.ground_truth)
            return score / n if n else 0.0

    return EvoSkillLoop


# ---------------------------------------------------------------------------------------------------------
def _git(project: Path, *args):
    return subprocess.run(["git", *args], cwd=project, check=True, capture_output=True, text=True)


def init_project(project: Path) -> None:
    """A fresh EvoSkill project: git repo on `main` with the v2 seed skill + prompt and EvoSkill's meta-skills."""
    for rel, h in SEED_SHA256.items():
        got = _sha((SEED_DIR / rel).read_bytes())
        assert got == h, f"seed file {rel} sha256 {got} != BUILD_RECORD {h}"
    project.mkdir(parents=True)
    shutil.copytree(SEED_DIR / "skills/spreadsheet-helpers", project / ".claude/skills/spreadsheet-helpers")
    shutil.copyfile(SEED_DIR / "prompt.md", project / PROMPT_REL)
    for m in META_SKILLS:
        shutil.copytree(UPSTREAM / ".claude/skills" / m, project / ".claude/skills" / m)
    (project / ".evoskill").mkdir()
    (project / ".evoskill/state.json").write_text(json.dumps({"original_branch": "main"}) + "\n")
    # Upstream .gitignore's relevant lines (EvoSkill relies on them: its checkout auto-stashes untracked files).
    (project / ".gitignore").write_text(".claude/*\n!.claude/program.yaml\n!.claude/skills/\n.evoskill/\n.cache/\n"
                                        "__pycache__/\n*.py[oc]\n")
    _git(project, "init", "-q", "-b", "main")
    _git(project, "config", "user.name", "exp895-evoskill")
    _git(project, "config", "user.email", "exp895-evoskill@localhost")
    _git(project, "config", "commit.gpgsign", "false")
    _git(project, "add", "-A")
    _git(project, "commit", "-q", "-m", "exp895 evoskill project: v2 seed + EvoSkill meta-skills")


def build_pools(train_ids, tasks, seed: int):
    """§7.4: train pooled by instruction_type. Within a pool, a seeded shuffle (upstream shuffles with a fixed
    random_state=42; we use the search seed so the 3 searches differ)."""
    pools: dict[str, list[tuple[str, str]]] = {}
    for t in sorted(train_ids):
        pools.setdefault(tasks[t].input["instruction_type"], []).append(t)
    rng = random.Random(seed)
    out = {}
    for cat in sorted(pools):
        ids = pools[cat]
        rng.shuffle(ids)
        out[cat] = [(question(t, tasks), "pass") for t in ids]
    return out


def question(tid: str, tasks) -> str:
    """§7.4: TASK::<id> + instruction + range."""
    i = tasks[tid].input
    return f"TASK::{tid}\nInstruction: {i['instruction']}\nRange: {i['answer_position']}"


def _ids(path) -> list[str]:
    return [l.strip() for l in open(path) if l.strip()]


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--R", type=int, required=True)
    ap.add_argument("--train-ids", required=True)
    ap.add_argument("--val-ids", required=True)
    ap.add_argument("--max-iters", type=int, default=12)        # §7.4
    ap.add_argument("--conc", type=int, default=int(os.environ.get("SPREADSHEETBENCH_CONCURRENCY", "10")))
    a = ap.parse_args(argv)
    run = Path(a.run_dir).resolve()
    project = run / "project"

    from rollout import CommonRollout
    from src.agent_profiles.skill_generator import get_skill_generator_options
    from src.agent_profiles.skill_proposer import get_skill_proposer_options
    from src.agent_profiles.prompt_generator import get_prompt_generator_options
    from src.agent_profiles.prompt_proposer import get_prompt_proposer_options
    from src.harness import set_sdk
    from src.loop import LoopAgents, LoopConfig
    from src.registry import ProgramManager
    from src.schemas import (PromptGeneratorResponse, PromptProposerResponse, SkillProposerResponse,
                             ToolGeneratorResponse)

    set_sdk("claude")
    lift_eval_timeout()
    init_project(project)
    os.chdir(project)   # upstream resolves some defaults from cwd; the optimizer's cwd is this dir too

    ro = CommonRollout(run, arm=ARM, search_seed=a.seed, R=a.R)
    train, val = _ids(a.train_ids), _ids(a.val_ids)
    tasks = {t: ro._tasks[t] for t in set(train) | set(val)}
    train_pools = build_pools(train, tasks, a.seed)
    val_data = [(question(t, tasks), "pass", tasks[t].input["instruction_type"]) for t in sorted(val)]

    manager = ProgramManager(cwd=project)
    mat = CandidateMaterializer(project, run / "candidates")
    seed_dir = mat.current("main")
    assert seed_dir.name == "seed", f"initial program is not byte-identical to the v2 seed: {seed_dir}"
    contract = contract_block()
    tr_path, perm_path = run / "optimizer_transcript.jsonl", run / "optimizer_permissions.jsonl"
    base = CapEvolveBaseAgent(ro, mat, manager, tasks, max_parallel=max(1, a.conc // K),
                              log_path=run / "base_agent_runs.jsonl")
    agents = LoopAgents(
        base=base,
        skill_proposer=make_optimizer_agent(get_skill_proposer_options, SkillProposerResponse, project, tr_path,
                                            perm_path, role="skill_proposer"),
        prompt_proposer=make_optimizer_agent(get_prompt_proposer_options, PromptProposerResponse, project, tr_path,
                                             perm_path, role="prompt_proposer"),          # unused in skill_only
        skill_generator=make_optimizer_agent(get_skill_generator_options, ToolGeneratorResponse, project, tr_path,
                                             perm_path, role="skill_generator",
                                             query_suffix="\n\n## Task Constraints\n" + contract),
        prompt_generator=make_optimizer_agent(get_prompt_generator_options, PromptGeneratorResponse, project, tr_path,
                                              perm_path, role="prompt_generator"),        # unused in skill_only
    )
    config = LoopConfig(
        max_iterations=a.max_iters,
        frontier_size=3,                       # §7.4
        no_improvement_limit=10**9,            # §7.4: disabled
        concurrency=max(1, a.conc // K),       # tasks in flight; each runs K rollouts
        evolution_mode="skill_only",
        selection_strategy="best",             # §7.4
        failure_sample_count=3,                # §7.4 failure sampling 3 / 3 / 2
        categories_per_batch=3,
        samples_per_category=2,
        cache_enabled=True,                    # §7.4: run cache stays on
        cache_dir=run / "evoskill_cache",      # outside the project, so the optimizer never sees it
        reset_feedback=True,
        continue_mode=False,
    )
    n_train_iter = sum(min(config.samples_per_category, len(p))
                       for p in list(train_pools.values())[:min(config.categories_per_batch, len(train_pools))])
    Loop = make_loop_class()
    loop = Loop(config, agents, manager, train_pools, val_data, scorer=scorer, task_constraints=contract)
    loop.ro = ro
    loop.per_iter_worst = (n_train_iter + len(val_data)) * K
    meta = {"arm": ARM, "seed": a.seed, "R": a.R, "k": K, "pass_threshold": "mean >= 2/3", "max_iterations": a.max_iters,
            "pools": {c: len(p) for c, p in train_pools.items()}, "val": len(val_data),
            "train_samples_per_iter": n_train_iter, "per_iter_worst_rollouts": loop.per_iter_worst,
            "concurrency_tasks": config.concurrency, "upstream_pin": "36f6f04952293d7054145550c2b9f0b0411bff1c"}
    print("EVOSKILL_START", json.dumps(meta), flush=True)

    stop_reason, result = "max_iterations", None
    try:
        result = asyncio.run(loop.run())
    except BudgetExhausted as e:
        stop_reason = f"budget: {e}"
        print("EVOSKILL_STOP", stop_reason, flush=True)

    frontier = manager.get_frontier_with_scores()
    best = frontier[0][0] if frontier else "base"
    manager.switch_to(best)
    champ = mat.current(best)
    if (run / "champion").exists():
        shutil.rmtree(run / "champion")
    shutil.copytree(champ, run / "champion")
    summary = {**meta, "stop_reason": stop_reason, "frontier": frontier, "best_program": best,
               "champion_candidate": champ.name, "iterations_completed": result.iterations_completed if result else None,
               "programs": manager.list_programs(), "budget": json.loads((run / "budget_state.json").read_text())}
    (run / "run_summary.json").write_text(json.dumps(summary, indent=1))
    print("EVOSKILL_DONE", json.dumps(summary), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
