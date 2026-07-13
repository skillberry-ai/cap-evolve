# How cap-evolve compares

**Positioning.** Most agent-optimization tools tune *prompts* against a metric.
cap-evolve optimizes prompts **and** executable tools, MCP surfaces, and whole skill
packages against *your* eval, keeps the evaluation honest in code (sealed test +
val-only significance gate), versions every iteration in git, and stays host- and
agent-agnostic. This page defines the comparison criteria and places cap-evolve next to
adjacent work — including external results as *context, not a leaderboard*.

## Feature comparison

Each criterion is defined below the table. ✅ = first-class; ➖ = partial / possible with
effort; ❌ = not a goal.

| Criterion | cap-evolve | DSPy | GEPA | promptfoo |
|---|:--:|:--:|:--:|:--:|
| Optimizes prompts | ✅ | ✅ | ✅ | ❌ (eval only) |
| Optimizes tools/MCP **and** skill packages | ✅ | ➖ | ➖ | ❌ |
| Sealed test + significance gate enforced **in code** | ✅ | ➖ | ➖ | ➖ |
| Host- & agent-agnostic (no framework lock-in) | ✅ | ❌ | ❌ | ➖ |
| Onboard a benchmark from a single prompt | ✅ | ❌ | ❌ | ➖ |
| Git-versioned iterations + optimizer memory | ✅ | ❌ | ❌ | ❌ |
| Live cost-aware dashboard | ✅ | ❌ | ❌ | ➖ |
| Zero runtime dependencies | ✅ | ❌ | ❌ | ❌ |

**Criterion definitions**
- **Optimizes prompts** — improves system-prompt / policy text against a metric.
- **Optimizes tools/MCP and skill packages** — edits executable tool *code* (add / wrap /
  swap tools), MCP tool surfaces, and Agent Skill packages (SKILL.md + references +
  scripts), not just prose.
- **Sealed test + significance gate in code** — the held-out split is scored exactly once
  and acceptance is a paired val-only significance gate (Δ > k·SE); both live in the core,
  not in editable docs. See [`HONEST_EVAL.md`](HONEST_EVAL.md).
- **Host- & agent-agnostic** — the optimizer is any coding-agent CLI resolved by one
  registry row; no framework lock-in.
- **Onboard from a single prompt** — one intake brief installs the benchmark, wires the
  adapter, and passes `cap-evolve check` before any budget is spent.
- **Git-versioned iterations + memory** — every candidate is a commit; rejected approaches
  are remembered and never re-proposed.
- **Live cost-aware dashboard** — per-iteration optimizer & runner cost + time, lineage,
  diffs, and a tasks × iterations heatmap.
- **Zero runtime dependencies** — the core is pure Python stdlib.

Primary sources: [DSPy](https://github.com/stanfordnlp/dspy),
[GEPA](https://github.com/gepa-ai/gepa) (arXiv:2507.19457),
[promptfoo](https://github.com/promptfoo/promptfoo). Roadmap positioning:
[`ROADMAP.md`](ROADMAP.md).

## External context — tool-optimization results (NOT apples-to-apples)

These numbers come from other papers on **different benchmark versions, models, task
splits, simulators, trial protocols, metrics, and budgets**. They are contextual
evidence, not a controlled comparison. We deliberately avoid "beats" / "state-of-the-art"
claims.

| Work | Benchmark | Result | Relative |
|---|---|---|---|
| **EvoTool** (arXiv:2603.04900) | **original τ-Bench** airline, GPT-4.1 | ReAct 35.9 → **39.1** (+3.2) | **~+8.9%** |
| **EvoTool** | original τ-Bench airline, Qwen3-8B | ReAct 14.4 → **15.7** (+1.3) | **~+9.0%** |
| Evolutionary Context Search | τ²-Bench | reported **+23.3%** | +23.3% |
| **cap-evolve** (this repo) | **τ²-Bench** airline, held-out 30/10/10 | sealed test 30.0 → **47.5** (+17.5 pp) | **+58.3%** |

Notes and honest caveats:
- **EvoTool evaluates the *original* τ-Bench** (Yao et al., 2024), while cap-evolve and
  Evolutionary Context Search use **τ²-Bench** — a different, harder benchmark. The rows
  are therefore not directly comparable.
- EvoTool figures are quoted from its Table 1 (verified against arXiv:2603.04900).
- The **Evolutionary Context Search +23.3%** figure is referenced in cap-evolve issue #46;
  its primary-source citation is **still to be confirmed** — treat it as unverified until a
  reference is added here.
- cap-evolve's +58.3% is a **within-run relative** improvement on its own held-out split
  ([`RESULTS.md`](RESULTS.md)); a different split, model, and simulator than the rows above.

---

*Last reviewed: 2026-07-13. Update this date and re-verify the external rows whenever a
number changes.*
