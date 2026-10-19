# parsec v6

v6 is a **unified task set** — v4's original 34 tasks plus v5's held-out 166 (merged from both
`v5_2026-10-10` and `v5_2026-10-12` drops), renamed under a `bench-v6-` prefix, **200 tasks total**,
4 categories (platform, icinga, cloud, cost) — and the first parsec arm family to run with a
genuine **3-way hidden split**: feedback (F, visible to the optimizer), confirm (C, hidden, the
only split the accept/reject gate reads), and test (sealed, scored exactly once).

It exists to answer the question every prior parsec arm (v1/v2/v4/h4/v5) could not: **does an
accepted candidate's gain survive genuinely held-out data**, rather than just the split the
optimizer was tuned against. v4's G2 arm never completed its one `FINAL` test-split attempt;
v5's arms ran `train == val == test` with no holdout at all.

## Shared setup

- **Task set:** all 200 v6 tasks, built by
  `examples/parsec/v6/build_v6_tree.py` (in the `parsec-intake_v6` worktree) from JB's two
  2026-10-16 bundles. Every task is renamed `bench-v6-<id>` but otherwise byte-identical to its
  v4/v5 source (`verify.py`/`expected.json` untouched).
- **Split:** `split_mode: pooled`, `promotion_rule: P2`. 67 feedback / 67 confirm / 66 test, a
  stratified random partition fixed once per run via `split_seed`, published in full
  (`recipes/v6/v6_g2_e1/split_ids.json`) alongside this benchmark's own public release. During
  the search itself the optimizer only ever saw the feedback split and an accept/reject bit from
  the confirm split's gate — never a confirm/test task id or score — but that's a property of how
  the search was run, not a secrecy claim about the split definition.
- **Agent model:** `claude-sonnet-4-6`. **Optimizer model:** `claude-opus-5`
  (`optimizer_skill: claude-code`, `algorithm_skill: hill-climb`).
- **Gate:** the confirm split's accept/reject decision comes from a group-sequential paired test
  at increasing cumulative sample size (16/33/67/133/200 rollouts), not a single fixed-size test —
  a candidate can be accepted, rejected, or killed early (at the feedback-split screening rung,
  before any confirm-split spend) at any look.

## Arms

| arm | scope | result | links |
|---|---|---|---|
| **g2** (`v6_g2_e1`) | global: one shared 8-file bundle evolved jointly, hill-climb, 6 iterations | sealed test-split reward **0.8496** vs. seed's **0.8126** — **+0.0369 (3.69pp)**, the first parsec arm with a positive, completed, held-out test-split result | [`summary.md`](v6_g2_e1/summary.md) · [`results.json`](v6_g2_e1/results.json) · [`cost_time/`](v6_g2_e1/cost_time/) · [heatmap](../../ui/heatmap_v6_g2_e1.html) · [per-candidate process](v6_g2_e1/source/process/) · [recipe](../../recipes/v6/v6_g2_e1/) · [reports](../../reports/v6/v6_g2_e1/) · [artifacts](../../artifacts/v6/v6_g2_e1/) |
