# AgentCapTune

<!-- badges: replace OWNER/REPO once published -->
![status](https://img.shields.io/badge/status-beta%20(0.x)-orange)
![tests](https://img.shields.io/badge/tests-28%20passing-brightgreen)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![deps](https://img.shields.io/badge/runtime%20deps-0%20(stdlib)-success)
![license](https://img.shields.io/badge/license-MIT-informational)
![skills](https://img.shields.io/badge/agent%20skills-25-7c5cff)

**Optimize any AI agent's capabilities — its skills, tools/MCP, and prompts —
against your own eval. Host-agnostic. Honest train/val/test. Every iteration
versioned in git.**

AgentCapTune is a library of [Agent Skills](https://www.anthropic.com/news/skills)
(plus a tiny stdlib core) that turns "make this agent better at X" into a
disciplined loop *any* coding agent can run: collect inputs → wire a 4-method
adapter → evaluate → diagnose failures → propose edits → keep only what beats a
held-out set → report. It optimizes what your agent *reads*, and reports a single,
honest number you can trust.

> **Status:** beta (`0.x`) — APIs may change. Working end to end; proven on a real
> benchmark (see [Results](#results)).

**Contents:** [Quickstart](#quickstart-60-seconds) · [Results](#results) ·
[Supported agent hosts](#supported-agent-hosts) · [Install](#install) ·
[Usage](#usage-swap-one-word) · [How it works](#how-it-works) ·
[Dashboard](#dashboard) · [Comparison](#how-it-compares) ·
[Skill library](#skill-library) · [Examples](#examples) ·
[Extending](#extending) · [Contributing](#contributing) · [Citation](#citation)

![AgentCapTune demo](docs/demo.gif)

## Quickstart (60 seconds)

A real, zero-API run — the `toy_calc` example (a deterministic agent whose score
depends on its system prompt; full setup in [examples/toy_calc](examples/toy_calc)):

```bash
git clone <repo> AgentCapTune && cd AgentCapTune
pip install ./core                         # the honest-eval substrate (CLI: acapo)
./install.sh                               # place skills into your agent host
bash examples/toy_calc/run.sh              # scaffold a tmp project dir and run
```
```jsonc
{
  "baseline_val": 0.0,        // seed prompt fails every task
  "test_reward": 1.0,         // optimized prompt, scored ONCE on the sealed test split
  "test_pass_k": {"1": 1.0},
  "dashboard": ".agentcapo/run_*/dashboard.html"   // open in any browser
}
```
Or, host-agnostic: point any agent at [`RUN.md`](RUN.md) and say *"follow RUN.md."*

## Results

Real [tau2-bench](https://github.com/sierra-research/tau2-bench) **airline** run —
optimizing the airline **policy + tools together** with a Claude-Opus optimizer and
`gpt-oss-120b` as both agent and user simulator, over all 50 tasks:

| | reward |
|---|---|
| baseline (seed policy + default tool docs) | **0.46** |
| **optimized** (policy + tool docstrings, 8 iterations) | **0.80** · pass^1 0.80 · pass@2 0.87 |

**+0.34** on 50 tasks (31/50 fully solved) — every iteration a git commit, the
optimizer's reasoning kept in `STATE.md` / `rejected.jsonl`. Exact commands, inputs,
and intake answers: [docs/REPRODUCE_tau2.md](docs/REPRODUCE_tau2.md); measured
numbers: [examples/tau2_airline/RESULTS.md](examples/tau2_airline/RESULTS.md).

## Supported agent hosts

Any of these can drive the **optimizer** (the agent that proposes edits). Verified
headless commands; details in `skills/optimizers/<name>/SKILL.md`.

| Host (optimizer) | Skill | Headless command | Status |
|---|---|---|---|
| Claude Code | `claude-code` | `claude -p … --permission-mode acceptEdits` | stable |
| OpenAI Codex CLI | `codex` | `codex exec --sandbox workspace-write …` | stable |
| Gemini CLI | `gemini-cli` | `gemini -p … --approval-mode=yolo` | stable |
| opencode | `opencode` | `opencode run --dangerously-skip-permissions …` | stable |
| OpenClaw | `openclaw` | configurable (`ACAPO_OPENCLAW_CMD`) | beta |
| IBM Bob | `ibm-bob` | via `AGENTS.md` (configurable) | beta |
| Any CLI agent | `generic` | `ACAPO_OPTIMIZER_CMD` template | stable |
| (tests / CI) | `mock` | deterministic, zero-API | stable |

`install.sh` auto-detects each host's skill dir (Claude Code `.claude/skills`,
Codex `.agents/skills`, opencode native, Gemini extensions, …).

## Install
```bash
pip install ./core            # package: AgentCapTune-core, CLI: acapo
./install.sh                  # copy skills into your host's skills dir (optionally --host <name>)
```

## Usage (swap one word)

Pick the optimizer in `acapo.yaml`; the loop is identical — only the host changes:

```yaml
# .agentcapo/project/acapo.yaml
capabilities: [system-prompt, tools]   # list of capabilities to optimize jointly
                                       #   any of: system-prompt | tools | mcp-tool | skill-package
optimizer_skill:  claude-code      # ← swap: codex | gemini-cli | opencode | generic | mock
algorithm_skill:  all-at-once      # all-at-once | cyclic | hardest-first | gepa-reflective
num_trials: 4
store: git                         # versions every iteration; or: copy | command (e.g. a skills store)
```
```bash
python3 -m agent_capo.cli run --spec .agentcapo/project/acapo.yaml --project .agentcapo/project
```

## How it works
1. **Intake** — interview the user, scaffold `.agentcapo/project/`, gather inputs (ask if missing).
2. **Implement & check** — fill the 4-method adapter (`tasks · run_target · score · apply`); `acapo check` is a hard gate.
3. **Baseline** — freeze seeded train/val/test (test **sealed**), score the seed on val.
4. **Optimize** — each iteration: diagnose failing traces → the optimizer edits a candidate → score on **val** → a **significance gate** (Δ > k·SE) accepts or rejects → commit to git, update memory.
5. **Finalize** — score the best candidate on the **sealed test split, exactly once**.
6. **Report** — `report.md` + a self-contained `dashboard.html`.

Honesty is enforced in code, not docs: the only place rewards are aggregated,
splits are made, the gate is applied, and test is sealed is `agent_capo` —
see [docs/HONEST_EVAL.md](docs/HONEST_EVAL.md). You implement four adapter methods
once; everything else is provided ([docs/ADAPTER_CONTRACT.md](docs/ADAPTER_CONTRACT.md)).

## Dashboard
Every run writes a single-file `dashboard.html` (run data inlined; opens offline):
KPI cards, baseline→val→test, score-over-iterations, a **per-task reward heatmap**,
an accept/reject timeline, a frontier scatter, and a candidate leaderboard with
pass^k / pass@k.

## How it compares

| | AgentCapTune | DSPy | GEPA | promptfoo |
|---|:--:|:--:|:--:|:--:|
| Optimizes prompts | ✅ | ✅ | ✅ | ❌ (eval only) |
| Optimizes tools/MCP + skills | ✅ | ➖ | ➖ | ❌ |
| **Sealed test + significance gate enforced in code** | ✅ | ➖ | ➖ | ➖ |
| pass^k *and* pass@k + bootstrap CI | ✅ | ❌ | ❌ | ❌ |
| Reflective Pareto evolution (GEPA) | ✅ | ✅ | ✅ | — |
| **Runs on any agent host (no framework)** | ✅ | ❌ | ❌ | ➖ |
| Git-versioned iterations + optimizer memory | ✅ | ❌ | ❌ | ❌ |
| Zero runtime dependencies | ✅ | ❌ | ❌ | ❌ |

Whitespace: **skills-native + host-agnostic + honesty enforced in code.** Roadmap: [docs/ROADMAP.md](docs/ROADMAP.md).

## Skill library

| Component | Skills |
|-----------|--------|
| orchestrate | `orchestrate` |
| phases | `intake` · `implement-and-check` · `baseline` · `evaluate` · `diagnose` · `gate` · `finalize` · `report` |
| capabilities | `system-prompt` · `skill-package` · `tools` · `mcp-tool` |
| algorithms | `all-at-once` · `cyclic` · `hardest-first` · `gepa-reflective` |
| optimizers | `claude-code` · `codex` · `gemini-cli` · `opencode` · `openclaw` · `ibm-bob` · `generic` · `mock` |

## Examples
- [`examples/toy_calc`](examples/toy_calc) — zero-API deterministic proof (the CI gate).
- [`examples/json_extract`](examples/json_extract) — a new benchmark from scratch (adapter + data only).
- [`examples/tau2_airline`](examples/tau2_airline) — the real tau2-bench run above.

## Extending
A new capability / algorithm / optimizer is **one folder** — clone `templates/skill`,
fill `meta.yaml`, drop it in; the registry auto-discovers it by `needs`/`provides`.
See [docs/EXTENDING.md](docs/EXTENDING.md).

## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md).
Report security issues via [SECURITY.md](SECURITY.md). Changes: [CHANGELOG.md](CHANGELOG.md).

## Citation
```bibtex
@software{AgentCapTune,
  title  = {AgentCapTune: a skills-native, host-agnostic harness for honestly
            optimizing AI-agent capabilities},
  year   = {2026},
  note   = {https://github.com/OWNER/AgentCapTune}
}
```
Builds on GEPA, DSPy, SkillOpt, SkillGrad, Trace2Skill, evo/evo-graph/governor,
tau-bench/tau2-bench, and the Agent Skills standard — see [docs/sources.bib](docs/sources.bib).

## License
MIT.
