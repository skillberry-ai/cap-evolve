# Does cap-evolve optimize actual tool/script CODE, or only prompt text?

**Short answer: yes — confirmed with two independent, checked-in, git-tracked examples
where cap-evolve rewrote real Python code and the reward improved in lockstep with the
code changes. The mechanism that gets that code running inside a sandboxed benchmark
container is whole-file deployment + subprocess execution — not a `PYTHONPATH`/`sys.path`
import trick, which does not exist anywhere in this codebase today.**

This report answers three questions: (1) can cap-evolve edit real code, not just prose;
(2) is there evidence it has actually done so; (3) how does an evolved script end up
running inside a Docker sandbox.

---

## 1. The capability types

cap-evolve's optimizer edits a "capability" — the artifact under optimization. Four
types exist, each governed by its own `SKILL.md` under `skills/capabilities/`:

| Type | What's editable |
|---|---|
| `system-prompt` | A prompt/policy text file only |
| `tools` | The agent's **own** tools — docstrings/descriptions **and tool behavior/code**, plus adding/removing composite tools |
| `mcp-tool` | Tools served by an **external** MCP server — docs/exposed-set only; code is explicitly NOT editable (the server isn't yours) |
| `skill-package` | A whole Agent Skill directory: `SKILL.md` + `references/` + `scripts/` + `assets/` — **all of it editable**, including creating brand-new bundled scripts |

The `tools` capability's own `SKILL.md` states directly: *"names, descriptions,
parameter docs, in-description examples, the JSON Schema, and the implementation code
are all fair game."* The `skill-package` capability's `SKILL.md` lists "a skipped step →
a bundled script" as one of its highest-leverage optimization moves, with `apply()`
explicitly allowed to "rewrite or CREATE" a script.

So the capability to edit real code is real, not aspirational — but capability
documentation alone isn't proof it was *used*. Two concrete runs confirm it was.

---

## 2. Example A — `tau2_airline` (capability: `system-prompt` + `tools`)

`examples/tau2_airline` optimizes a tau2-bench airline agent's system prompt **and**
its own tool implementations jointly. Results are recorded in `docs/RESULTS.md`:
**val +90.5%, sealed test +125%** when `[skill-package, system-prompt, tools]` are
optimized together versus the seed.

The evolved tool code is loaded via `importlib.util.spec_from_file_location(...)` +
`spec.loader.exec_module(mod)` in `adapters/adapter.py`'s `_load_candidate_tools_class()`
— executed fresh, in-process, on every candidate. This runner is not containerized (it's
an in-process/subprocess litellm agent), so there's no sandbox-injection step to
describe for this example — it's included here purely to establish that tool-*code*
optimization, not just prompt optimization, is real and measured.

---

## 3. Example B — `exam-block-sequencing` (capability: `skill-package`)

This is the more striking example: the optimizer **wrote an entire new solver from
scratch**, not just SKILL.md text.

**Location:** `intake_skillbench_c3/.capevolve/project_exam-block-sequencing`, run store
`intake_skillbench_c3/.capevolve/run_task_exam-block-sequencing_v1_KILLED_ceiling_reached_1.0`
— a real git repo (`store: git` in `capevolve.exam-block-sequencing.yaml`), so every
iteration is a commit.

**Seed state:** the seed skill package contained **only two `SKILL.md` files**
(`ordered-window-sequencing-mip/SKILL.md`, `mip-solver-and-solution-audit/SKILL.md`).
No script existed. Seed reward: **0.1**.

**Iteration 1 (`cand_0001`, val 0.9):** the optimizer **created**
`ordered-window-sequencing-mip/scripts/solve_sequencing.py` — a 465-line heuristic
solver implementing a feasible front-loaded initializer followed by restarted 2-swap
simulated-annealing / steepest-descent local search.

**Iteration 2 (`cand_0002`, best/final, val 1.0):** the optimizer **modified** that
script to 549 lines, adding new functions `build_feasible()` and `relocate()`, and
widening the search neighborhood from plain 2-swap to 2-swap + or-opt(1) relocation.
`history.jsonl` logs this explicitly as a "script-only" edit:

> *"enlarged the local-search neighborhood from 2-swap-only to 2-swap + or-opt(1)
> relocation... added `build_feasible`... + `relocate` helper."*

Diff excerpt (cand_0001 → cand_0002):

```diff
<   2. runs restarted steepest-descent 2-swap local search on the EXACT objective
---
>   2. runs restarted local search over a combined 2-swap + or-opt(1) relocation
>      neighborhood (simulated annealing then steepest descent) on the EXACT
```

`git log --stat` on the run store shows both accept commits (`iter 1: ACCEPT candidate
cand_0001`, `iter 2: ACCEPT candidate cand_0002`) touching `scripts/solve_sequencing.py`
alongside the SKILL.md files each time — and a compiled
`__pycache__/solve_sequencing.cpython-312.pyc` sitting next to it confirms the script
was actually **executed**, not just written and ignored.

No `policy.json` existed anywhere in this project or run store, so script edits were
fully unrestricted for this run.

**Reward trajectory** (`results.json`, task `exam-block-sequencing`): seed 0.1 →
cand_0001 0.9 → cand_0002 1.0 (final, status `KILLED_ceiling`). The reward jump tracks
the code changes directly, not a prose reword.

---

## 4. How the evolved code actually runs inside the sandboxed container

Using SkillsBench (the benchmark `exam-block-sequencing` and similar tasks run under)
as the concrete pipeline, from `examples/skillsbench/adapters/adapter.py`:

**Step 1 — materialize.** The optimizer's edits are written as plain files into the
candidate's `seed_capability/<sub-skill>/` directory on the host/pod filesystem. No
container yet.

**Step 2 — stage a clean copy.** The adapter copies (never symlinks — deliberately,
because BenchFlow's own deploy step `copytree`s the skills dir and *silently skips
symlinked entries*) each sub-skill into a fresh temp directory:

```python
skills_root = Path(tempfile.mkdtemp(prefix="skillsbench_skills_", dir=str(_BENCH_CWD)))
for sub in sorted(candidate_dir.iterdir()):
    if sub.is_dir() and (sub / "SKILL.md").exists():
        shutil.copytree(sub, skills_root / sub.name)
```

**Step 3 — hand it to the benchmark's own CLI.** cap-evolve never touches Docker
directly; it shells out to BenchFlow:

```python
cmd = [BENCH_BIN, "eval", "run", ...,
       "--sandbox", "docker",
       "--skill-mode", "with-skill", "--skills-dir", str(skills_root), ...]
```

**Step 4 — BenchFlow deploys it into the container at `/skills`.** Per the adapter's
own docstring: *"the CANDIDATE'S four skills injected verbatim at /skills."* BenchFlow
owns the container's full lifecycle (build, start, teardown).

**Step 5 — the in-container agent runs the script as a subprocess.** The Claude agent
inside the Docker sandbox reads `SKILL.md`, sees the instruction to invoke
`scripts/solve_sequencing.py`, and runs it **as a command-line program via its own Bash
tool** — not via any Python `import`. This is exactly why the exam-block-sequencing
run left behind a `__pycache__/*.pyc`: that's the interpreter *inside the container*
compiling the script on first execution, independent of the host.

**Step 6 — results flow back out.** BenchFlow writes the verifier reward, CTRF report,
and transcript to a jobs directory on the host; the adapter reads those back into a
`Rollout` that the optimizer scores.

### Why not `PYTHONPATH` / `sys.path`?

A separate, exhaustive search across the main repo and all 15 worktrees found **every**
`PYTHONPATH`/`sys.path` occurrence to be host-side plumbing — the cap-evolve CLI, its
tests, or adapter helper scripts importing `cap_evolve` or a sibling helper module on
the *host* process. None of them set or manipulate the Python path **inside** a
benchmark's container. The mechanism that actually gets tool code into a container is
the copy-and-execute pipeline above: the whole file lands on disk inside the sandbox,
and the agent's own Bash tool runs it as a subprocess. If a PYTHONPATH-based import
trick was discussed previously, it was never implemented — it would be a plausible
extension of this existing "copy the whole directory in" pattern, but no such code,
config, or design doc exists in the repository today.

---

## Bottom line

- **Real, measured, code-level optimization exists** — twice over, via two different
  mechanisms: in-process `importlib.exec_module` reload (tau2_airline, tool code) and
  whole-directory container deployment + subprocess execution (exam-block-sequencing,
  skill-bundled script, from-scratch solver).
- **The reward numbers back it up** — both examples show reward moving with the actual
  code changes, not just wording changes.
- **No PYTHONPATH/import-based container injection exists** in this codebase. Don't
  claim that specific mechanism was built — it wasn't. The copy-and-execute pattern
  above is the real, working answer to "how does evolved code get into the container."
