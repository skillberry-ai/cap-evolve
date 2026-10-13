# parsec v5 — `v5_t1_e1` (DISCARDED: not a baseline)

> **This run is not a baseline and must not be used as one.** It was intended to measure the
> original parsec skill on 68 v5 tasks. Instead it measured
> [`artifacts/v4/v4_g_e1/rejected/cand_0001`](../../../artifacts/v4/v4_g_e1/rejected/cand_0001) —
> a candidate produced by v4's **global optimizer** arm. **The v5 baseline is
> [`v5_b1_e1`](../v5_b1_e1/summary.md)**: same tasks plus 68 more, the verified original skill, audited
> trials.
>
> It is kept as a record of what went wrong, and because it happens to be a clean
> transfer measurement of one optimizer candidate (below).

**Skill actually evaluated:** byte-identical (8/8 prompt files) to `artifacts/v4/v4_g_e1/rejected/cand_0001`
**Agent model:** `claude-sonnet-4-6` · **Trials:** 5 per task, 340 total, 68 tasks (the `v5_2026-10-10` drop)
**Raw results:** [`source_v5_t1_e1.json`](source_v5_t1_e1.json), vendored verbatim from the intake worktree's `collect.py`
**Recipe:** [`../../../recipes/v5/v5_t1_e1/`](../../../recipes/v5/v5_t1_e1/)

## How the wrong skill got in

The v5 benchmark tree was built by copying the live `parsec-live` clone from `v4_2026-09-16`. On
2026-09-27 — four days after `artifacts/v4/seed/` was vendored — `cand_0001`'s eight prompt files had
been written into that clone's `config/prompts/` working tree and never committed. parsec's git HEAD
still read `28e2c40`, so `git status` and `git log` showed nothing; only a byte comparison against a
fresh clone of the parsec reference repo revealed it. The sweep then installed those files as every
project's seed.

**Rule this leaves behind:** pin the artifact under test to a known commit and verify it by bytes
before running an arm. `v5_b1_e1` does.

## What this run actually measures

Comparing it with `v5_b1_e1` on the same 68 tasks is a clean A/B: identical task files, identical
harness, the only difference being the skill. Both runs were audited per trial; this one had **0
dead trials of 340** (it ran on 2026-10-11, before the gateway degradation that hit the baseline).

| | `v5_b1_e1` (original skill) | `v5_t1_e1` (`cand_0001`) | Δ |
|---|--:|--:|--:|
| mean, 68 shared tasks | 0.8482 | 0.8885 | **+0.0403** (SE 0.0165) |

Small on average and concentrated: 6 tasks gain more than 0.2, none lose more than 0.2, and 56 of 68
move by less than the ~0.09 per-task noise floor.

| task | origin | original | `cand_0001` | Δ |
|---|---|--:|--:|--:|
| `cloud-024-guid-to-account` | v4-34 | 0.200 | 1.000 | +0.800 |
| `platform-003-tojson-dict-literal-rca` | v4-34 | 0.443 | 0.930 | +0.487 |
| `platform-001-ee-entrypoint-rca` | v4-34 | 0.480 | 0.884 | +0.404 |
| `platform-022-job-on-no-controller` | v4-34 | 0.700 | 0.965 | +0.265 |
| `platform-004-events-then-config` | v4-34 | 0.787 | 1.000 | +0.213 |
| `platform-031-helm-url-not-a-timeout` | v4-34 | 0.660 | 0.870 | +0.210 |
| `cloud-057-cloudtrail-select-only-refusal` | h4-rewritten | 0.560 | 0.440 | −0.120 |
| `platform-068-deprecation-warning-not-the-fatal` | new-10-10 | 0.944 | 0.828 | −0.116 |
| `platform-033-schema-change-not-the-oom` | v4-34 | 0.829 | 0.731 | −0.098 |

### The finding worth keeping: the gain does not transfer

`cand_0001` was produced by v4's global optimizer **training on v4's 34 tasks** (where it scored
0.9274 against the seed's 0.8488). Split by where each v5 task came from:

| origin | n | original | `cand_0001` | Δ |
|---|--:|--:|--:|--:|
| `v4-34` — the tasks it was optimized on | 34 | 0.8365 | 0.9217 | **+0.0853** |
| `h4-rewritten` — never seen | 21 | 0.9224 | 0.9148 | **−0.0076** |
| `new-10-10` — never seen | 11 | 0.7998 | 0.7861 | **−0.0137** |
| `renamed-content-changed` | 2 | 0.5350 | 0.6100 | +0.0750 |

The whole improvement is on its training tasks; on 32 unseen tasks it is flat. That is one candidate
and n=5 per task, so it is a signal rather than a result — but it is exactly the train-versus-held-out
gap the planned `o5`/`h5` split is designed to measure, and a reason to expect it.

## What was wrong with this PR's first version

Recorded so nobody relies on the earlier text:

1. It described this run as "the original, unmodified PARSEC skill (T1)". It was `cand_0001`.
2. Its v4 comparison used `v4_t4_e1`/`v4_t4_e2` as the baseline — those are the static merge of 21
   **optimized** bundles. v4's original-skill baseline is `v4_t1_e1` (see `v5_b1_e1`, which reproduces
   it to −0.002).
3. It understated the skill difference as "the shared `orchestrator.md` picked up routing changes";
   in fact 7 of 8 files differ from the original.
4. A later estimate that the contamination inflated the mean by +0.151 was also wrong: it compared
   against the baseline before that run's 74 dead trials were re-run. The correct figure is +0.040.

Its generated heatmap, per-task reports, ledger generators and cross-experiment comparison were
removed rather than corrected: they presented this run as a baseline arm, and the correct comparison
now lives in [`../v5_b1_e1/summary.md`](../v5_b1_e1/summary.md).
