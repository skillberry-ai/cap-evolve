# cap-evolve roadmap

cap-evolve's differentiator is real whitespace: **skills-native + host-agnostic +
honest train/val/test**, which no top optimization repo combines. This roadmap is
derived from a survey of the best optimization/eval repos (DSPy, GEPA, OpenEvolve,
Inspect, promptfoo, DeepEval, tau-bench, SWE-bench, the Agent Skills standard) and
prioritizes what makes cap-evolve best-in-class and widely adopted.

## Done (v0.1)
- Honest eval as a structural invariant: seeded splits, **sealed** test, val-only
  significance gate, multi-trial variance, **pass^k (reliability) + pass@k
  (capability)** + bootstrap CIs.
- Skills-native pipeline (intake → implement-and-check → baseline → algorithm →
  diagnose → gate → finalize → report) + auto `orchestrate` + a `using-cap-evolve`
  session-start router.
- Algorithms: **`gepa`** (flagship — real GEPA: two-stage minibatch-then-full-val
  economy, per-instance Pareto frontier, reflective dataset, system-aware merge;
  arXiv:2507.19457), **`skillopt`** (flagship — epochs × mini-batches, decaying
  textual-LR edit budget, rejected-edit buffer, gated slow update; arXiv:2605.23904),
  **`hill-climb`** (one skill, `--focus all|cyclic|hardest-first`)
  (a thin precursor).
- Capabilities: system-prompt, skill-package, tools, mcp-tool (action-policy / mutation-lock); capabilities chosen as a LIST.
- Optimizers: one **`run-optimizer`** skill + `optimizers/registry.yaml`
  (claude-code, codex, gemini-cli, opencode, openclaw, ibm-bob, generic, mock) —
  verified headless commands; adding one is a single YAML row.
- Honest-eval upgrades: paired significance gate (default), seal-on-success test,
  structured `Rollout.error` infra signal, per-trial seed for real pass^k variance.
- Rich **self-contained** `dashboard.html` + `cap-evolve report --terminal` ANSI report.
- Host-agnostic installer + Claude Code plugin (honesty hooks in core-owned scripts,
  diagnoser/proposer subagents, router) — `claude --plugin-dir ./plugins/cap-evolve`.
- Real proof: tau2-bench airline (gpt-oss-120b agent + user simulator) optimized
  policy + tools jointly with a claude-opus optimizer; toy_calc zero-API gate green in CI.

## Next (prioritized from the research)
1. **Optimizer strategy registry + one `optimize(seed, train, val)` API** (DSPy
   ergonomics) so algorithms swap in one line; `gepa` as the default flagship.
2. **Scorer library** (batteries-included): `match`, `regex`, `contains`,
   `numeric`, `json`, `f1`, `choice` (shuffled-MCQ-safe), `llm_judge` (NL criteria
   → 0–1, DeepEval GEval style), and **first-class `cost`/`latency` scorers** —
   token/$ as an optimizable objective. (Inspect, promptfoo, DeepEval)
3. **Dual-gate / no-regression acceptance** (SWE-bench FAIL_TO_PASS +
   PASS_TO_PASS): reject candidates that fix the target but regress previously
   passing val tasks.
4. **Tiered datasets + cascade evaluation**: a cheap Lite subset for iteration, a
   sealed Verified tier for the headline; a cheap filter before the expensive eval.
5. **Artifacts side-channel** (OpenEvolve): pipe failing stderr/trace text directly
   into the next proposal prompt (richer than the current reflection).
6. **More algorithms**: cluster_cyclic (issues-graph clustering),
   dspy_instruction_search (MIPRO). *(GEPA and SkillOpt — `gepa`, `skillopt` — are
   now **DONE**; see "Done".)*
7. **More capabilities**: skill-package (full SKILL.md dir), retrieval_config.
8. **Distribution polish**: `pip install cap-evolve`, an `llms-full.txt`, an MCP
   server + CLI to query results, and `skills-ref validate` against the
   agentskills.io spec. *(`llms.txt` and the self-contained static-HTML dashboard
   now ship — see "Done".)*
9. **Evals as a CI gate** (`assert_skill(candidate, suite)` pytest helper) and a
   **trace → dataset → experiment** loop turning real runs into held-out sets.
10. **Numeric meta-knob tuning** (temperature, population size, retrieval-k) via
    Optuna TPE / Ax-BoTorch with early-stopping pruners, composed with the
    evolutionary content optimization.

## Design tenets (don't regress)
- The honesty guarantees live only in `cap_evolve` — never fork them.
- Every user-facing capability is a drop-in skill; adding one never edits core.
- Skills stay host-agnostic; the plugin is a convenience, not a requirement.
