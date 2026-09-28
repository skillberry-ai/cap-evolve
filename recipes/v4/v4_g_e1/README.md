# recipes/v4/v4_g_e1

The cap-evolve project config the G2 (`v4_g2_e1`) run used — copied verbatim from the live G
project (`parsec_g2` worktree, `.capevolve/v4_g2_e1/project/`), post-run edit included (see
"Recipe vs. run" below).

## What's here

- **`capevolve.yaml`** — the entire project config for the single, run-wide optimization: one
  shared bundle evolved jointly across all 34 tasks, rather than T's one-config-per-task shape.
- **`split_ids.json`** — lists all 34 tasks with `train == val == test` for each — the same
  no-holdout design as T's per-task split (see [`../v4_t_e1/README.md`](../v4_t_e1/README.md)), just
  applied to the full task set at once instead of one task at a time.
- **`../INSTRUCTIONS.md`** — shared with the T arm, not duplicated here. The G project's own
  `optimizer`/`adapters` directories are symlinks back to T's scaffolding
  (`optimizer -> ../../../scripts/v4_t2_e1/common/optimizer`, `adapters -> …/common/adapters`), i.e.
  G reused T's optimizer template verbatim rather than authoring its own. See
  [`../README.md`](../README.md).

## `gate_k_se: 0.0` — a real G-only setting

```yaml
# Any positive paired improvement counts, ignoring the SE margin —
# accept threshold becomes mean_d > 0 instead of mean_d > k_se*SE.
gate_k_se: 0.0
```

T has no analogous setting — its per-task recipe doesn't gate on paired significance at all. G's
`gate_k_se: 0.0` means the run accepted any candidate with a positive paired delta over its parent,
regardless of how small or noisy, rather than requiring the delta to clear a standard-error margin.
Worth keeping in mind when reading G's accept/reject history: an accepted candidate is not
necessarily a *significant* improvement, just a positive one.

## Recipe vs. run: a real divergence, post-run edit

Unlike the T arm (see [`../v4_t_e1/README.md`](../v4_t_e1/README.md), "no divergence found"), G's
vendored `capevolve.yaml` **does not match** what the run actually used:

| field | `capevolve.yaml` (as vendored) | actual run (`state.json`, `run_optimize_fix_20260925_082813`) |
|---|---|---|
| `max_iterations` | 10 | 15 |
| `stall` | 3 | 6 |
| `max_usd` | (not overridden above default) | 1000.0 |
| `max_optimizer_usd` | 100.0 | 400.0 |
| `stop_at_reward` | 1.0 | 1.0 (matches) |

The file on disk was modified 2026-09-26 02:55 — **after** the run finished (the run's own two
canonical dirs, `run_baseline_fix_20260925_003926` and `run_optimize_fix_20260925_082813`, both
predate that timestamp). This is a post-run edit to the live project, not a mismatch between config
and execution at run time.

**`state.json` is the authority for what actually ran** — every budget figure quoted in
[`../../../results/v4/v4_g_e1/summary.md`](../../../results/v4/v4_g_e1/summary.md) and
[`../../../results/v4/comparison.md`](../../../results/v4/comparison.md) comes from `state.json`,
not from this vendored yaml. The yaml is vendored as-found anyway, per the same "the record of what
was configured" principle as the rest of `recipes/` — readers should just know it's the *current*
project state, not necessarily the *run-time* one, unlike T's.

## No `seed_capability/` here

The seed bundle G2 evolved from is byte-identical to T's — see
[`../../../artifacts/v4/seed/`](../../../artifacts/v4/seed/) — and is shared at the `v4/` level, not
duplicated per arm.
