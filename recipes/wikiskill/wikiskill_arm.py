"""exp895 WikiSkill arm (issue skillberry-ai/cap-evolve#895 §7.7; community port Stahl-G/wikiskill @ da6984ca).

There is NO official WikiSkill code; this arm runs the community port, UNMODIFIED, as a library:

  * `wikiskill.engine.initialize` + `wikiskill.engine.evolve` own the loop: baseline on val, then per iteration
    train rollouts -> Wiki Maintainer -> Skill Proposer -> val of the candidate -> Eq. 4 gate (strict improvement
    over r_best, ties rejected) -> accept or keep, with the append-only event ledger and skill-impact records;
  * `wikiskill.paper_alignment.agents.PaperAgents` supplies the two roles with the paper's appendix prompts and
    its deterministic JSON contracts (`paper_alignment.contracts`), failure/success sampling (`evidence.sample`)
    and visible traces (`evidence.visible_trace`);
  * `wikiskill.isolated.tools_server.RoleTools` is the roles' tool set (read_file over staged files + finish).

This module supplies only what the engine asks a caller to supply (README: "domain_loader / maintainer_factory /
proposer_factory callbacks"):

  1. a domain loader whose rollout scores candidates ONLY through the common exp895 rollout
     (`CommonRollout.evaluate(candidate_dir, task_ids, k=3)`). Each (task, trial) is one engine case
     `<task>__t<j>`; the engine's whole-phase batch triggers ONE evaluate(k=3) call for all its tasks, and each
     case returns its own trial's row (k stays inside the call; no task id is duplicated).
  2. the role transport `invoke(...)` that PaperAgents takes: instead of the Codex CLI (macOS sandbox-exec,
     gpt-5.6-luna), a GLM-5.3 tool loop through the metering gateway, with RoleTools executing every tool call
     on a freshly staged workspace (roles see staged files only; no shell tool exists for the roles).
  3. materialisation of the engine's skill set into a v2-seed candidate directory (skills/<name>/SKILL.md +
     scripts/, prompt.md, the wiki index + pattern pages as one more SKILL.md).

Runtime changes to upstream behaviour (all in deviations_wikiskill.json): the early stop at r_best == 1.0 is
neutralised by wrapping `engine.state`; a pre-iteration budget guard; the common surface contract appended to the
Proposer's system prompt; resume-on-error for infra trials and role-transport failures.

Usage (inside the LSF job, see lsf_wikiskill_search.sh):
    python wikiskill_arm.py --run-dir RUN --seed S --R R --train-ids F --val-ids F [--subset 30] [--max-iters N]
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
from types import SimpleNamespace

EXP = Path("/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-spread-worktrees/exp895")
REPO = Path("/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-spread-worktrees/sbv400-main")
UPSTREAM = EXP / "competitors/wikiskill"
SEED_DIR = REPO / "templates/adapters/spreadsheetbench/seed_capability_v2"
CONTRACT = EXP / "arms/common/SURFACE_CONTRACT.md"
sys.path.insert(0, str(UPSTREAM / "src"))
sys.path.insert(0, str(EXP / "arms/common"))

from wikiskill import engine  # noqa: E402
from wikiskill.isolated.tools_server import RoleTools, specs  # noqa: E402
from wikiskill.paper_alignment import contracts  # noqa: E402
from wikiskill.paper_alignment.agents import PaperAgents, paper_prompts  # noqa: E402

ARM = "wikiskill"
K = 3
SUBSET_DEFAULT = 30                 # issue §7.7: fixed seeded 30-of-80 train subset per search seed
TASK_DESC = "spreadsheet manipulation tasks with Python code execution"   # fills the paper's {task_desc}
GLM_MODEL = "rits/zai-org/glm-5-3"  # served id of GLM-5.3 (decisions.md); the gateway pins it anyway
GLM_MAX_TOKENS = 16000
ROLE_MAX_TURNS = 40
ROLE_MAX_NUDGES = 3
ROLE_CONTEXT_CHARS = 360_000        # ~100k tokens of file reads per role session (GLM context; Codex compacts)
MAX_RESUMES = 3                     # consecutive engine resumes without progress before the search stops
# Wait before each resume without progress (2026-10-25): the stops were RITS Gemma timeouts on a few cases, and an
# immediate resume re-hit the same bad stretch. 300/900/1800 s, the same idea as the GEPA and MIPROv2 arms' waits.
RESUME_WAITS = (300, 900, 1800)
WIKI_SKILL_DIR = "wikiskill-wiki"   # hyphenated: can never collide with a snake_case proposer skill name
PROMPT_SKILL = "system_prompt"      # reserved skill name whose Instructions text replaces prompt.md
SKILL_BODY_CAP = 6000               # the adapter caps each SKILL.md body at 6,000 chars (helpers.skills_prompt)
SEED_SHA256 = {  # exp895/BUILD_RECORD.json seed_v2.files_sha256
    "prompt.md": "efa493dd57aee05d5563e4f709d5c9e2fde1fb9fc9f71a3b5a3472a40b723c72",
    "task_template.md": "841967412770441da3ba2785e37194524133aca50a49b489bb57f8e22bb84295",
    "skills/spreadsheet-helpers/SKILL.md": "6679c3f28a9fa25ca376d7d143e32a9d8783bd41e2f6b1829de756b3893dae1f",
    "skills/spreadsheet-helpers/scripts/.gitkeep": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
}
# Upstream's own transport sentence, verbatim from wikiskill/spreadsheet/study.py::_learn (the paper prompts do not
# name the finish tool for the Maintainer; the Codex path relied on the tool description alone).
TRANSPORT_NOTE = ("\nSubmission transport: read_file reads staged files; finish(proposal) submits the exact paper JSON. "
                  "No extra computation or network tool is available.\n")
SCRIPT_RE = re.compile(r"^#{1,6}[ \t]*Script:[ \t]*`?([A-Za-z_][A-Za-z0-9_]*)\.py`?[ \t]*\n+```python[^\n]*\n(.*?)\n```[ \t]*$",
                       re.M | re.S)
INSTR_RE = re.compile(r"^#{1,6}[ \t]*Instructions[ \t]*$", re.M | re.I)


def _sha(b: bytes | str) -> str:
    return hashlib.sha256(b.encode("utf-8") if isinstance(b, str) else b).hexdigest()


def check_seed():
    for rel, h in SEED_SHA256.items():
        got = _sha((SEED_DIR / rel).read_bytes())
        assert got == h, f"seed file {rel} sha256 {got} != BUILD_RECORD {h}"


def surface_note() -> str:
    """Appended to the Proposer's system prompt: the common contract VERBATIM + how a proposal maps onto it."""
    contract = CONTRACT.read_text(encoding="utf-8").strip()
    return (
        "\n\n" + contract + "\n\n"
        "## How a proposal maps onto these surfaces in this experiment\n\n"
        "- Each skill you create or patch is written as `skills/<name>/SKILL.md` and appended to the agent's "
        "system prompt (its body is capped at 6,000 characters). Its scripts import as `skills.<name>.<script>`.\n"
        "- Helper scripts: inside a skill's `skill_md`, write a heading line `### Script: <module>.py` immediately "
        "followed by ONE ```python fenced block. That block becomes `skills/<name>/scripts/<module>.py`, importable "
        "as `skills.<name>.<module>`, and is removed from the SKILL.md text the agent sees. So describe each "
        "function (signature, when to call it, an example call) in the skill's prose.\n"
        f"- System prompt: a skill named `{PROMPT_SKILL}` is not shown as a skill. The text under its "
        "`## Instructions` heading REPLACES `prompt.md`. The current prompt.md is staged read-only at "
        "`surface/prompt.md`; keep its `{skills_root}` token wherever it names the helper import root.\n"
        "- The seed skill `skills/spreadsheet-helpers/` (staged at `surface/spreadsheet-helpers.SKILL.md`) is "
        "replaced by a skill you name `spreadsheet_helpers`; any other name adds a new skill next to it.\n"
        "- `task_template.md` is fixed in this arm.\n"
        f"- The Wiki index and pattern pages are ALSO shown to the agent, as one more SKILL.md "
        f"(`skills/{WIKI_SKILL_DIR}/SKILL.md`, index first, 6,000 characters), together with every candidate "
        "you propose. This overrides `executor_visibility.wiki` in the handoff.\n")


# ---------------------------------------------------------------------------------------------------------
class GLMRoleTransport:
    """PaperAgents' `invoke(directory, payload, system, user, mode, model, effort) -> archive`.

    Replaces the Codex CLI session (isolated/runtime.execute) with a chat/completions tool loop on GLM-5.3 via
    the gateway. Tools = RoleTools(mode) from upstream, unchanged (maintainer/proposer: read_file + finish).
    The archive holds what PaperAgents reads: submission.json (written by RoleTools.finish), final.txt and
    tool-events.jsonl (receipts in tools_server.main's format)."""

    def __init__(self, arm: "WikiSkillArm", api_base: str):
        from openai import OpenAI
        self.arm = arm
        self.client = OpenAI(base_url=api_base, api_key="tag-not-a-secret", timeout=1800, max_retries=1)
        self.calls = 0

    def __call__(self, directory, payload, system, user, mode, model, effort):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        n = 1 + sum(1 for p in directory.glob("attempt-*") if p.is_dir())
        att = directory / f"attempt-{n:02d}"
        work, control = att / "input", att / "runtime"
        work.mkdir(parents=True)
        control.mkdir()
        for rel, text in payload.items():
            p = work / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        system = system + TRANSPORT_NOTE
        if mode == "proposer":
            system = system + surface_note()
            inc = self.arm.incumbent_dir()
            (work / "surface").mkdir(exist_ok=True)
            (work / "surface/prompt.md").write_text((inc / "prompt.md").read_text(encoding="utf-8"), encoding="utf-8")
            (work / "surface/spreadsheet-helpers.SKILL.md").write_text(
                (inc / "skills/spreadsheet-helpers/SKILL.md").read_text(encoding="utf-8"), encoding="utf-8")
        (control / "tool-events.jsonl").write_text("")
        (att / "system.md").write_text(system, encoding="utf-8")
        (att / "user.md").write_text(user, encoding="utf-8")
        server = RoleTools(work, control, mode, sys.executable)
        tools = [{"type": "function", "function": {"name": s["name"], "description": s["description"],
                                                   "parameters": s["inputSchema"]}} for s in specs(mode)]
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        texts, nudges, logged, read_chars, turn = [], 0, 0, 0, 0
        tlog = open(att / "transcript.jsonl", "a", buffering=1)
        glog = open(self.arm.run / "optimizer_transcript.jsonl", "a", buffering=1)

        def log(rec):
            nonlocal logged
            rec = {"t": time.time(), "mode": mode, "attempt": str(att.relative_to(self.arm.run)), **rec}
            line = json.dumps(rec, ensure_ascii=False)
            tlog.write(line + "\n")
            glog.write(line + "\n")

        try:
            for turn in range(ROLE_MAX_TURNS):
                log({"turn": turn, "request_new_messages": messages[logged:]})
                logged = len(messages)
                t0 = time.time()
                resp = self.client.chat.completions.create(model=GLM_MODEL, messages=messages, tools=tools,
                                                           max_tokens=GLM_MAX_TOKENS, reasoning_effort=effort)
                self.calls += 1
                msg = resp.choices[0].message
                am = {"role": "assistant", "content": msg.content or ""}
                if msg.tool_calls:
                    am["tool_calls"] = [{"id": tc.id, "type": "function",
                                         "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                                        for tc in msg.tool_calls]
                messages.append(am)
                log({"turn": turn, "latency_s": round(time.time() - t0, 1), "finish_reason": resp.choices[0].finish_reason,
                     "usage": resp.usage.model_dump() if resp.usage else None, "response": am})
                logged = len(messages)
                if msg.content and msg.content.strip():
                    texts.append(msg.content.strip())
                if not msg.tool_calls:
                    if server.finished or nudges >= ROLE_MAX_NUDGES:
                        break
                    nudges += 1   # transport-level: a Codex session would simply have ended incomplete
                    messages.append({"role": "user", "content": "No tool was called. Use read_file on the staged "
                                     "files and call finish(proposal) with the complete JSON when ready."})
                    continue
                for tc in msg.tool_calls:
                    name = tc.function.name
                    rec = {"at": time.time(), "tool": name}
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                        if not isinstance(args, dict):
                            raise ValueError("tool arguments must be a JSON object")
                        rec["arguments"] = args
                        if name == "read_file" and read_chars > ROLE_CONTEXT_CHARS:
                            # transport limit (a Codex session would compact its context instead)
                            raise RuntimeError("context budget for file reads is used up; call finish(proposal) now")
                        value = server.call(name, args)
                        if name == "read_file":
                            read_chars += len(value)
                        rec.update(ok=True, result=value)
                        text = value if isinstance(value, str) else json.dumps(value)
                    except Exception as exc:  # noqa: BLE001 - surfaced to the model exactly like the MCP server
                        rec.setdefault("arguments", {"raw": tc.function.arguments})
                        rec.update(ok=False, error=f"{type(exc).__name__}: {exc}")
                        text = rec["error"]
                    with (control / "tool-events.jsonl").open("a", encoding="utf-8") as f:
                        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": text})
                if server.finished:
                    break
                if turn == ROLE_MAX_TURNS - 4:
                    messages.append({"role": "user", "content": "Only 3 turns remain: call finish(proposal) with "
                                     "your complete JSON now."})
            log({"turn": "end", "finished": server.finished, "nudges": nudges, "request_new_messages": messages[logged:]})
        finally:
            tlog.close()
            glog.close()
        (control / "final.txt").write_text("\n\n".join(texts) or "(no final text)", encoding="utf-8")
        if not server.finished or not (control / "submission.json").exists():
            raise RuntimeError(f"{mode}: GLM role ended without an accepted finish() after {turn + 1} turns")
        return control


# ---------------------------------------------------------------------------------------------------------
class _Phase:
    def __init__(self):
        self.lock = threading.Lock()
        self.result = None
        self.error = None
        self.returned_infra: set = set()


class WikiSkillArm:
    def __init__(self, run: Path, *, seed: int, R: int, train_ids, val_ids, ro, max_iters: int | None,
                 glm_api_base: str | None):
        self.run, self.seed, self.R = Path(run), int(seed), int(R)
        self.root = self.run / "engine"
        self.cands = self.run / "candidates"
        self.cands.mkdir(parents=True, exist_ok=True)
        self.train_ids, self.val_ids = list(train_ids), list(val_ids)
        self.ro = ro
        self.max_iters = max_iters
        self.budget_stop: str | None = None
        self._phases: dict = {}
        self._lock = threading.Lock()
        self._cand_lock = threading.Lock()
        self._evals = open(self.run / "arm_evals.jsonl", "a", buffering=1)
        self._tasks = getattr(ro, "_tasks", {})   # CommonRollout's id -> Task table (instruction, answer_position)
        self.transport = GLMRoleTransport(self, glm_api_base) if glm_api_base else None

    # ---- candidates -----------------------------------------------------------------------------------
    def seed_dir(self) -> Path:
        d = self.cands / "seed"
        with self._cand_lock:
            if not d.exists():
                shutil.copytree(SEED_DIR, d)
        return d

    def _index(self) -> dict:
        p = self.cands / "index.json"
        return json.loads(p.read_text()) if p.exists() else {}

    def candidate_for(self, skill_text: str, phase: str = "incumbent") -> Path:
        """The candidate dir for an engine skill text.

        `iterations/NNN/val` = that iteration's NEW proposal: materialised once, from NNN's paper-candidate.json
        and the Wiki as it stands right after NNN's Maintainer (frozen with the candidate). Any other phase uses
        the INCUMBENT, i.e. the candidate dir of the iteration whose gate accepted this exact text."""
        if skill_text == "":
            return self.seed_dir()
        h = _sha(skill_text)
        m = re.match(r"iterations/(\d{3})/val$", phase)
        if m:
            it = m.group(1)
        else:
            acc = [e for e in engine.events(self.root) if e.get("type") == "gate" and e.get("accepted")
                   and e.get("skill_sha256") == h]
            if not acc:
                raise RuntimeError(f"incumbent skill {h[:12]} has no accepting gate event")
            it = f"{acc[-1]['iteration']:03d}"
        key = f"it{it}:{h}"
        with self._cand_lock:
            idx = self._index()
            if key in idx:
                return self.cands / idx[key]
            p = self.root / f"iterations/{it}/proposer/paper-candidate.json"
            skills = json.loads(p.read_text())
            if contracts.skill_text(skills) != skill_text:
                raise RuntimeError(f"{p} does not produce skill text {h[:12]}")
            name = f"it{it}_{h[:12]}"
            self.materialize(skills, self.root / "wiki", self.cands / name)
            idx[key] = name
            (self.cands / "index.json").write_text(json.dumps(idx, indent=1))
            return self.cands / name

    @staticmethod
    def materialize(skills: dict, wiki_dir: Path, dest: Path):
        """Skill map + Wiki -> a v2-seed candidate dir. Seed files are untouched unless a surface is edited."""
        tmp = dest.with_name("." + dest.name + ".tmp")
        if tmp.exists():
            shutil.rmtree(tmp)
        shutil.copytree(SEED_DIR, tmp)
        manifest = {"skills": {}, "prompt_md": "seed", "wiki_chars": 0}
        for name in sorted(skills):
            md = skills[name]["skill_md"]
            if name == PROMPT_SKILL:
                m = INSTR_RE.search(md)
                body = md[m.end():].strip() if m else ""
                if body:
                    (tmp / "prompt.md").write_text(body + "\n", encoding="utf-8")
                    manifest["prompt_md"] = "replaced"
                continue
            scripts = {}

            def take(mt, name=name, scripts=scripts):
                scripts[mt.group(1)] = mt.group(2)
                return f"(Helper script preloaded as `skills.{name}.{mt.group(1)}`.)"
            text = SCRIPT_RE.sub(take, md)
            # `spreadsheet_helpers` imports exactly as the seed's skills/spreadsheet-helpers, so it REPLACES that
            # seed skill (the only way the seed SKILL.md surface is editable here); any other name is a new dir.
            d = tmp / "skills" / ("spreadsheet-helpers" if name == "spreadsheet_helpers" else name)
            (d / "scripts").mkdir(parents=True, exist_ok=True)
            (d / "SKILL.md").write_text(text.strip() + "\n", encoding="utf-8")
            (d / "PURPOSE.md").write_text(skills[name].get("purpose_md", "").strip() + "\n", encoding="utf-8")
            for mod, code in scripts.items():
                (d / "scripts" / f"{mod}.py").write_text(code.rstrip() + "\n", encoding="utf-8")
            manifest["skills"][name] = {"dir": d.name, "skill_md_chars": len(text), "scripts": sorted(scripts)}
        wiki = wiki_text(wiki_dir)
        if wiki:
            d = tmp / "skills" / WIKI_SKILL_DIR
            d.mkdir(parents=True)
            (d / "SKILL.md").write_text(
                f"---\nname: {WIKI_SKILL_DIR}\ndescription: Patterns (problem, root cause, fix) compiled from past "
                f"spreadsheet episodes; consult the index for the task at hand.\n---\n\n{wiki}\n", encoding="utf-8")
            manifest["wiki_chars"] = len(wiki)
        (tmp.parent / f"{dest.name}.manifest.json").write_text(json.dumps(manifest, indent=1))
        tmp.rename(dest)

    def incumbent_dir(self) -> Path:
        st = engine.state(self.root)
        return self.candidate_for((self.root / st["skill"]).read_text(encoding="utf-8"), "incumbent")

    # ---- domain loader (engine callback) --------------------------------------------------------------
    def domain_loader(self, config, split):
        if split not in ("train", "val"):
            raise ValueError("Evolution only reads train and val")
        ids = self.train_ids if split == "train" else self.val_ids
        cases = [SimpleNamespace(uid=f"{t}__t{j}", split=split, task=t, trial=j) for t in ids for j in range(K)]

        def rollout(case, *, workdir, model, reasoning_effort, skill_text, timeout_seconds):
            return self._case(split, case, Path(workdir), skill_text)
        return cases, rollout

    def _phase(self, phase_dir: Path, skill_text: str) -> _Phase:
        key = (str(phase_dir), _sha(skill_text))
        with self._lock:
            return self._phases.setdefault(key, _Phase())

    def _evaluate(self, split, phase_dir, skill_text, task_ids, k=K):
        if self.budget_stop:
            raise RuntimeError(f"budget stop: {self.budget_stop}")
        if split == "train" and k == K and not self.ro.would_fit(len(self.train_ids) + len(self.val_ids), K):
            # iteration guard: an iteration = train phase + (at most) one val phase
            raise _budget(self, f"iteration guard: train {len(self.train_ids)}x{K} + val {len(self.val_ids)}x{K} "
                                f"does not fit ({self.ro.spent}/{self.R})")
        phase = str(phase_dir.relative_to(self.root))
        cand = self.candidate_for(skill_text, phase)
        try:
            res = self.ro.evaluate(cand, task_ids, k=k, candidate_id=cand.name, split=split)
        except Exception as e:
            if type(e).__name__ == "BudgetStop":
                raise _budget(self, str(e)) from e
            raise
        self._evals.write(json.dumps({"t": time.time(), "phase": phase, "split": split, "candidate": cand.name,
                                      "n_tasks": len(task_ids), "k": k, "eval_call": res.eval_call, "counted": res.counted,
                                      "mean": res.mean, "missing_tasks": res.missing_tasks,
                                      "spent": self.ro.spent}) + "\n")
        return res

    def _case(self, split, case, workdir: Path, skill_text: str) -> dict:
        phase_dir = workdir.parent.parent
        ph = self._phase(phase_dir, skill_text)
        with ph.lock:
            if ph.error is not None:
                raise ph.error
            if ph.result is None:
                ids = self.train_ids if split == "train" else self.val_ids
                try:
                    ph.result = self._evaluate(split, phase_dir, skill_text, ids)
                except BaseException as e:
                    ph.error = e
                    raise
            tr = ph.result.per_task[case.task]
            if tr.infra[case.trial] and case.uid in ph.returned_infra:
                # engine resume after an infra trial: re-run every task with a returned infra trial, ONE call (k=3)
                # (only the missing trials: tasks grouped by how many trials they miss, one evaluate per group)
                miss = {}
                for t in {c.split("__t")[0] for c in ph.returned_infra}:
                    js = [j for j in range(K) if ph.result.per_task[t].infra[j]]
                    if js:
                        miss[t] = js
                for m in sorted({len(js) for js in miss.values()}):
                    group = sorted(t for t, js in miss.items() if len(js) == m)
                    fresh = self._evaluate(split, phase_dir, skill_text, group, k=m)
                    for t in group:
                        old, new = ph.result.per_task[t], fresh.per_task[t]
                        for j, jn in zip(miss[t], range(m)):
                            if not new.infra[jn]:
                                for f in ("trials", "trial_seeds", "feedback", "errors", "infra", "traces"):
                                    getattr(old, f)[j] = getattr(new, f)[jn]
                ph.returned_infra.clear()
                tr = ph.result.per_task[case.task]
            if tr.infra[case.trial]:
                ph.returned_infra.add(case.uid)
        return self._row(split, case, workdir, tr, ph.result, skill_text)

    def _row(self, split, case, workdir: Path, tr, res, skill_text) -> dict:
        j = case.trial
        task = self._tasks.get(case.task)
        inp = task.input if task is not None else {}
        trace = tr.traces[j] or []
        rt = workdir / "runtime"
        rt.mkdir(parents=True, exist_ok=True)
        # The common rollout's transcript as tool receipts, the shape evidence.visible_trace() renders.
        receipts, msgs = [], [m for m in trace if isinstance(m, dict) and m.get("role") != "system"]
        predicted = ""
        if msgs and msgs[0].get("role") == "user":
            receipts.append({"tool": "task_message", "arguments": {}, "result": _text(msgs[0].get("content")), "ok": True})
            msgs = msgs[1:]
        i = 0
        while i < len(msgs):
            m = msgs[i]
            if m.get("role") == "assistant":
                nxt = msgs[i + 1] if i + 1 < len(msgs) and msgs[i + 1].get("role") == "user" else None
                receipts.append({"tool": "agent_turn", "arguments": {"reply": _text(m.get("content"))},
                                 "result": _text(nxt.get("content")) if nxt else "(episode ended)", "ok": True})
                predicted = _text(m.get("content"))
                i += 2 if nxt else 1
            else:
                receipts.append({"tool": "environment", "arguments": {}, "result": _text(m.get("content")), "ok": True})
                i += 1
        if not receipts:   # e.g. a candidate stopped by the helper gate: no episode ran
            receipts.append({"tool": "episode", "arguments": {}, "ok": True,
                             "result": f"(no agent transcript) {tr.errors[j] or tr.feedback[j] or ''}"[:3000]})
        with (rt / "tool-events.jsonl").open("w", encoding="utf-8") as f:
            for r in receipts:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        infra = bool(tr.infra[j])
        err = tr.errors[j]
        return {"uid": case.uid, "split": split, "task_id": case.task, "trial": j, "trial_seed": tr.trial_seeds[j],
                "eval_call": res.eval_call, "candidate": Path(res.candidate_dir).name,
                "score": 0.0 if infra else float(tr.trials[j]),
                "fail_reason": "exec_failed" if infra else ("candidate_error" if err else
                                                            ("" if tr.trials[j] == 1 else "wrong_answer")),
                "question": {"question": inp.get("instruction", ""), "instruction_type": inp.get("instruction_type", ""),
                             "answer_position": inp.get("answer_position", "")},
                "predicted": predicted, "feedback": tr.feedback[j], "error": err,
                "workspace": str(workdir), "model": "google/gemma-4-31B-it", "returncode": 0,
                "skill_sha256": _sha(skill_text)}

    # ---- the search -----------------------------------------------------------------------------------
    def config(self) -> dict:
        return {"domain": "exp895-spreadsheetbench-v400", "model": "google/gemma-4-31B-it", "effort": "temperature-0",
                "workers": 8, "iterations": int(self.max_iters or 10_000), "timeout": 1800,
                "optimizer_model": GLM_MODEL, "optimizer_effort": "low",
                "exp895": {"seed": self.seed, "R": self.R, "k": K, "train_ids_sha256": _sha("\n".join(self.train_ids)),
                           "val_ids_sha256": _sha("\n".join(self.val_ids)), "n_train": len(self.train_ids),
                           "n_val": len(self.val_ids)}}

    def search(self) -> dict:
        t0 = time.time()
        if not (self.root / "manifest.json").exists():
            engine.initialize(self.root, self.config(), wiki_template="spreadsheet",
                              agent_prompts=paper_prompts(TASK_DESC))
        agents = PaperAgents(self.transport, seed=self.seed, training_feedback=_feedback)
        stop, resumes, errors, last_iter = None, 0, [], None
        while True:
            try:
                st = engine.evolve(self.root, domain_loader=self.domain_loader,
                                   maintainer_factory=agents.maintainer_factory,
                                   proposer_factory=agents.proposer_factory)
                stop = st["status"]
                break
            except Exception as e:  # noqa: BLE001
                if self.budget_stop:
                    stop = "budget_R"
                    break
                st = engine.state(self.root)
                errors.append({"t": time.time(), "iteration": st["next_iteration"], "error": f"{type(e).__name__}: {e}"[:2000]})
                print("ENGINE_ERROR", json.dumps(errors[-1]), flush=True)
                resumes = resumes + 1 if st["next_iteration"] == last_iter else 1
                last_iter = st["next_iteration"]
                if resumes > MAX_RESUMES:
                    stop = "engine_error"
                    break
                if resumes > 1:   # the first resume is immediate, as before; later ones wait out the outage
                    w = RESUME_WAITS[min(resumes - 2, len(RESUME_WAITS) - 1)]
                    print(f"[wikiskill] resume {resumes}/{MAX_RESUMES} without progress; waiting {w}s", flush=True)
                    time.sleep(w)
                with self._lock:   # a failed phase is re-evaluated on resume (completed rows are kept by the engine)
                    for k, ph in list(self._phases.items()):
                        if ph.error is not None:
                            del self._phases[k]
        st = engine.state(self.root)
        champ = self.candidate_for((self.root / st["skill"]).read_text(encoding="utf-8"), "incumbent")
        if (self.run / "champion").exists():
            shutil.rmtree(self.run / "champion")
        shutil.copytree(champ, self.run / "champion")
        gates = [e for e in engine.events(self.root) if e.get("type") == "gate"]
        base = next((e for e in engine.events(self.root) if e.get("type") == "baseline"), None)
        summary = {
            "arm": ARM, "seed": self.seed, "R": self.R, "rollouts_used": self.ro.spent,
            "binding_on_R": stop == "budget_R", "stop_reason": stop, "budget_stop_detail": self.budget_stop,
            "champion": champ.name, "champion_val_score": st["r_best"], "baseline_val_score": base and base["score"],
            "iterations": len(gates), "n_candidates_evaluated": sum(1 for g in gates if g["candidate_score"] is not None),
            "accepted": sum(1 for g in gates if g["accepted"]),
            "rejected": sum(1 for g in gates if g["verdict"] == "REJECT"),
            "no_action": sum(1 for g in gates if g["verdict"] == "NOT_GATED"),
            "gates": [{k: g[k] for k in ("iteration", "verdict", "incumbent_score", "candidate_score", "skill_sha256")}
                      for g in gates],
            "engine_errors": errors, "role_calls_glm": getattr(self.transport, "calls", 0),
            "train_ids_n": len(self.train_ids), "val_ids_n": len(self.val_ids), "k": K,
            "wall_s": round(time.time() - t0, 1),
        }
        (self.run / "run_summary.json").write_text(json.dumps(summary, indent=1))
        return summary


_UPSTREAM_STATE = engine.state


def _state_no_ceiling(root):
    """engine.state with the r_best == 1.0 early stop neutralised (issue §7.7). Everything else is upstream's.

    engine.evolve and PaperAgents look `state` up on the engine module at call time, so rebinding the module
    attribute is enough; engine.py itself is not edited."""
    r = _UPSTREAM_STATE(root)
    if r["status"] == "early_stop_validation_ceiling":
        iterations = engine.read(Path(root) / "manifest.json")["iterations"]
        r["status"] = "evolution_complete" if r["next_iteration"] > iterations else "evolving"
        r["early_stop_neutralized"] = True
    return r


engine.state = _state_no_ceiling


def _budget(arm, msg):
    arm.budget_stop = msg
    return RuntimeError(f"BudgetStop: {msg}")


def _text(c) -> str:
    if isinstance(c, list):
        return "\n".join(str(x.get("text", x)) if isinstance(x, dict) else str(x) for x in c)
    return "" if c is None else str(c)


def _feedback(row) -> dict:
    """TRAIN evaluator feedback for the roles: the common scorer's gold-SAFE message only (never gold values)."""
    out = {"scorer_feedback": row.get("feedback"), "score": row.get("score")}
    if row.get("error"):
        out["candidate_error"] = str(row["error"])[:1500]
    return out


def wiki_text(wiki_dir: Path) -> str:
    """index.md, then pattern pages in index order, up to the 6,000-char SKILL.md body cap (cut at a page)."""
    wiki_dir = Path(wiki_dir)
    pats = sorted((wiki_dir / "patterns").glob("*")) if (wiki_dir / "patterns").is_dir() else []
    pats = [p for p in pats if p.is_file() and not p.name.startswith(".")]
    if not pats:
        return ""
    index = (wiki_dir / "index.md").read_text(encoding="utf-8").strip() if (wiki_dir / "index.md").exists() else ""
    out = index[:SKILL_BODY_CAP]
    for p in pats:
        page = f"\n\n## Pattern page: {p.name}\n\n" + p.read_text(encoding="utf-8").strip()
        if len(out) + len(page) > SKILL_BODY_CAP:
            break
        out += page
    return out


def train_subset(pool, seed: int, n: int):
    """Fixed seeded subset of the train pool for one search seed (issue §7.7: 30 of 80)."""
    pool = sorted(map(str, pool))
    if len(pool) <= n:
        return pool
    return sorted(random.Random(f"exp895-wikiskill-train-subset-seed{seed}").sample(pool, n))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--R", type=int, required=True)
    ap.add_argument("--train-ids", required=True, help="train POOL (official train 80); the subset is drawn here")
    ap.add_argument("--val-ids", required=True)
    ap.add_argument("--subset", type=int, default=SUBSET_DEFAULT)
    ap.add_argument("--max-iters", type=int)
    a = ap.parse_args(argv)
    check_seed()
    run = Path(a.run_dir)
    read = lambda f: [ln.strip() for ln in open(f) if ln.strip()]  # noqa: E731
    pool, val = read(a.train_ids), read(a.val_ids)
    train = train_subset(pool, a.seed, a.subset)
    (run / "train_subset.txt").write_text("\n".join(train) + "\n")
    from rollout import CommonRollout
    ro = CommonRollout(run, arm=ARM, search_seed=a.seed, R=a.R)
    tag = f"exp895-{ARM}-s{a.seed}:optimizer"
    arm = WikiSkillArm(run, seed=a.seed, R=a.R, train_ids=train, val_ids=val, ro=ro, max_iters=a.max_iters,
                       glm_api_base=f"http://127.0.0.1:4115/t/{tag}/v1")
    print("WIKISKILL_ARM_START", json.dumps({"seed": a.seed, "R": a.R, "n_train_pool": len(pool),
                                              "n_train_subset": len(train), "n_val": len(val)}), flush=True)
    s = arm.search()
    print("WIKISKILL_ARM_DONE", json.dumps({k: s[k] for k in ("rollouts_used", "R", "stop_reason", "champion",
                                                               "iterations", "accepted", "n_candidates_evaluated")}),
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
