# Optimize your own agent

To optimize **your** capability against **your** benchmark you wire one small
**adapter** — three required methods plus optional hooks
([`ADAPTER_CONTRACT.md`](ADAPTER_CONTRACT.md)):

```python
tasks(split)                   -> list[Task]   # your eval cases for 'train'|'val'|'test'|'all'
run_target(task, ctx, *, seed) -> Rollout      # run your agent with the candidate LIVE as ctx;
                                               #   forward `seed` if stochastic; set Rollout.error on infra failure
score(task, rollout)           -> Score        # reward in [0,1] + feedback (never leak the gold)

# optional (working defaults provided):
materialize(cand_dir, edits)   -> None         # PURE write of edits into cand_dir
live(cand_dir)                 -> ctx (CM)     # make the candidate live for ONE eval
run_batch(tasks, ctx, *, seed) -> ...          # implement INSTEAD of run_target to drive a benchmark's OWN batch runner
run_trials(tasks, ctx, *, n_trials, base_seed) # batched fast path: ALL trials in ONE run
  -> {task_id: [Rollout, ...]}                 #   (collapses N eval passes; pass^k/SE unchanged)
trajectories(split)            -> Path|None    # the runner's NATIVE trace dir; copied verbatim to ./trajectories/
```

Everything else — splits, trials, gating, pass^k, the sealed test, memory, and the
dashboard — is provided by the core and must **not** be reimplemented (that is what keeps
eval honest).

There are two ways to get there.

## A — let your coding agent build it (no Python from you)

Open the coding agent you already use at the repo root and tell it to follow
[`../RUN.md`](../RUN.md). It loads the `intake` skill, asks for anything missing (never
fabricating a NEEDED input), writes the adapter, runs `cap-evolve check`, then the full
loop. A complete worked brief is
[`../examples/tau2_airline/PROMPT.md`](../examples/tau2_airline/PROMPT.md).

Fill this in and paste it to your coding agent with *"follow RUN.md"* — intake asks for
anything you omit and never fabricates a needed input:

```text
Follow RUN.md to run a cap-evolve optimization on MY benchmark/agent. If the
benchmark is not installed yet, the intake/integration step should CLONE + INSTALL
it. Here is everything intake needs (fill each field; leave a field blank only if
you want intake to ask):

# 1. CAPABILITY  (what gets optimized — a COPY is edited each iteration; the original is never touched)
- type:    <one or a list of: system-prompt | tools | mcp-tool | skill-package>
           # system-prompt = a prompt/policy text file; tools = the agent's OWN tools;
           # mcp-tool = tools served by an EXTERNAL MCP server (only docs/exposed-set edits);
           # skill-package = an Agent Skill dir (SKILL.md + refs + scripts). Combine, e.g. [system-prompt, tools].
- seed:    <path to the seed artifact to optimize, e.g. policy/policy.md | tools.json | skills/<name>/>
- NOTE for `tools`: the optimizer may edit tool docstrings/descriptions AND tool
           behavior/code, AND add/remove COMPOSITE tools that call existing tools
           (wrapping rules, loops, argument normalization) — not just reword docs.

# 2. BENCHMARK / DATASET  (the eval)
- benchmark:  <name, e.g. my-bench / SWE-bench-lite / a homegrown suite>
- repo:       <local path OR git URL>            # where the benchmark code/data lives
- install:    <how to install it, e.g. `pip install -e ../<bench>`; RECORD the resolved commit for reproducibility>
- tasks:      <path to tasks.jsonl  OR  "adapter">   # "adapter" = adapter.tasks(split) builds them in-code
- task format: each task = id + input + gold/criterion
              # one JSON object per line: {"id": ..., "input": ..., "target"/"criterion": ...}
- splits:     <one of:>
              #  seeded ratio   -> split_seed + split_train/val/test (default 0.5/0.25/0.25)
              #  explicit       -> split_ids.json  {"train":[...],"val":[...],"test":[...]} (e.g. an official split)
              #  no-holdout fit -> train == val == test == all ids (report FLAGS the test number as a fit metric)

# 3. RUNNER  (the agent under test) + MODELS + CREDENTIALS
- how to run one task:  <in-process call | subprocess | HTTP endpoint
                         | the benchmark's OWN batch runner -> implement adapter.run_batch instead of run_target>
- runner model(s):      <model id(s) the agent under test uses>
- credentials:          <env vars / repo-root .env keys, e.g. OPENAI_API_KEY, WATSONX_*, RITS_API_KEY — never hardcode a secret>
- custom/OpenAI-compatible endpoint (vLLM, IBM RITS, a gateway):
                        <api_base + any custom auth header>
                        # pass via the runner's LLM config (most benchmarks forward extra kwargs to litellm);
                        # prefer PER-CALL config — no monkeypatch, no benchmark fork
- concurrency knob:     <e.g. an env var / max-concurrency setting the runner honors>

# 4. SCORER  (what to optimize against)
- metric:     <exact-match | reward in [0,1] | rubric | pass/fail rule>
- source:     <the benchmark's own verifier  OR  your score() function in adapter.py>
- feedback:   must be GENERAL and gold-SAFE — it is the learning signal; never leak the gold answer
- objective:  maximize mean reward on the VAL split
- metrics_display:   <optional names to also SHOW, e.g. [accuracy, latency_ms]; empty = just the primary reward>
- metric_primary:    <which name GATES accept/reject; blank = the reward scalar itself>
- metric_directions: <parallel to metrics_display: higher | lower per metric>
                      # secondaries are display-only (dashboard/results JSON); ONLY the primary (= reward) gates.
                      # your score() returns them via Score.metrics — see docs/ADAPTER_CONTRACT.md

# 5. OPTIMIZER  (proposes the edits) + MODEL + CREDENTIALS
- optimizer:   <claude-code | codex | gemini-cli | opencode | cursor | droid | copilot | kimi | pi | antigravity | openclaw | ibm-bob | generic | mock>
- model:       <backend-specific model id>
- credentials: <e.g. ANTHROPIC_API_KEY or a logged-in Claude Code session; BOBSHELL_API_KEY for ibm-bob>

# 6. BUDGET / GATE
- algorithm:            <hill-climb (--focus all|cyclic|hardest-first) | gepa | skillopt>
- max_iterations:       <N — dominant cost knob>
- num_trials:           <>=3 for a stochastic agent; 1 only for a deterministic one>   # enables pass^k
- max_metric_calls:     <0 = unlimited; else stop after N runner evals>
- max_usd:              <total $ cap over runner + optimizer + intake; 0 = unlimited>
- max_optimizer_usd:    <cumulative optimizer-only $ cap; 0 = unlimited>
- optimizer_usd_per_iter: <PER-ITERATION $ cap enforced by the optimizer CLI itself, e.g. claude `--max-budget-usd N`>
- optimizer_max_turns:  <per-iteration WORK cap passed to the agent CLI, e.g. claude `--max-turns N`>
- gate:                 <significant (k_se) | strict | threshold>
                        # significant: accept only if Δ > k_se · SE — k_se is how many standard errors
                        # the val gain must clear (e.g. 0.2 = lenient, 1.0 = strict) so noise isn't mistaken for progress
- stall:                <stop after N consecutive rejects; 0 = run all max_iterations>
- store:                git          # versions every iteration as a commit for an inspectable process
```

## B — drive the `cap-evolve` CLI yourself

```bash
python3 skills/phases/intake/scripts/run.py --base .capevolve   # scaffold adapter STUB + capevolve.yaml
# 1. implement tasks / run_target (or run_batch) / score in
#    .capevolve/project/adapters/adapter.py  (copy the closest example below)
# 2. set capabilities / optimizer / algorithm / splits in capevolve.yaml
cap-evolve check .capevolve/project                              # hard gate — must print {"ok": true}
cap-evolve estimate --spec .capevolve/project/capevolve.yaml     # dry-run cost preview (spends nothing)
cap-evolve run   --spec .capevolve/project/capevolve.yaml --project .capevolve/project
open .capevolve/run_*/dashboard.html
```

Interrupted (crash, timeout, pod eviction)? Re-run the same command with `--resume`
(and `--run-ts <ts>` to name the run, else the latest is reused) to continue from the
last completed state — baseline and every accepted iteration are reused, not recomputed:

```bash
cap-evolve run --spec .capevolve/project/capevolve.yaml --project .capevolve/project --run-ts full --resume
```

Start from the closest example and edit its `adapter.py`:

| You want to optimize… | Copy | `capabilities:` |
|---|---|---|
| a **prompt** (zero-API proof) | [`../examples/toy_calc`](../examples/toy_calc) | `[system-prompt]` |
| a **system prompt + tools** (real agent) | [`../examples/tau2_airline`](../examples/tau2_airline) | `[system-prompt, tools]` |
| a **skill package** | [`../examples/skillsbench`](../examples/skillsbench) | `[skill-package]` |

**Swapping the optimizer is one word** in `capevolve.yaml` — one runner (`run-optimizer`)
resolves the name via `skills/optimizers/registry.yaml`:

```yaml
capabilities:    [system-prompt, tools]   # any of: system-prompt | tools | mcp-tool | skill-package
optimizer_skill: claude-code              # ← swap: codex | gemini-cli | opencode | cursor | droid | copilot | kimi | pi | antigravity | openclaw | ibm-bob | generic | mock
algorithm_skill: hill-climb               # hill-climb (--focus all|cyclic|hardest-first) | gepa | skillopt
num_trials: 4
store: git                                # versions every iteration
```

Extending is just as small — a new capability, algorithm, or optimizer is one folder or
one `optimizers/registry.yaml` row. See [`EXTENDING.md`](EXTENDING.md).
