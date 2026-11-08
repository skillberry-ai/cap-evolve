# parsec — multi-agent RCA benchmark

Optimizes the **system prompts** of PARSEC, a multi-agent root-cause-analysis
assistant, against authored RCA scenarios. Unlike the other examples, the thing
under test runs **outside** this repo: a live PARSEC clone plus five
simulated-service MCP endpoints, with the benchmark fixtures in a separate
`rhdp-parsec` checkout.

## Layout

```
adapters/adapter.py   the Harbor adapter — shared by every arm
optimizer/            optimizer instructions — shared
parsec_paths.py       single source of truth for $PARSEC_V4N/$PARSEC_V5N and the MCP ports
v4_t2_e1/             arm: per-task optimization over the original 34 scenarios
h4/                   arm: held-out evaluation over 30 later scenarios
  audit/              trial-integrity checks (see below)
v5/                   from-scratch 136-task rebuild (no shared content with v4/h4);
                      same mechanics as h4 (scaffold/make_lane/run_one_eval/fan_out/collect),
                      against a separate $PARSEC_V5N checkout
  audit/              pool_valid_trials.py — pool clean trials across every
                      resubmission attempt when one run alone can't reach N
ccc/                  bring the external stack up on the CCC cluster
RUN_H4.md             running h4 as one parallel job per task
tests/
```

`ccc/` holds the four parsec-specific cluster scripts — stack up/down, the
bootstrap, and the two run wrappers. `scripts/ccc/` keeps only the scripts that
are benchmark-agnostic.

The adapter and optimizer sit at this root rather than inside an arm because
both arms symlink the same files into every generated project — they are shared,
not copied.

## Running

Both v4 arms scaffold one cap-evolve project per task under `.capevolve/`, then
evaluate each task in its own process. They need:

```bash
export PARSEC_V4N=.../rhdp-parsec/v4_2026-09-16     # fixtures + live stack
export PARSEC_H4_BUNDLE=.../artifacts/v4/seed       # h4 only: which prompts
```

Neither variable has a default, deliberately. `PARSEC_V4N` has no single "the"
checkout to guess at, and `PARSEC_H4_BUNDLE` selects which bundle an arm
measures — guessing would make two arms silently compare the same thing.

`v5/`'s scripts are the same shape (`scaffold_eval_projects.py` →
`fan_out.sh` → `run_one_eval.sh` → `make_lane.sh` → `collect.py`), reading a
separate `$PARSEC_V5N` checkout instead:

```bash
export PARSEC_V5N=.../rhdp-parsec/v5_2026-10-10
python3 examples/parsec/v5/scaffold_eval_projects.py \
    --suite-id t1_e1 --artifact <dir-of-8-md-files>
bash examples/parsec/v5/fan_out.sh --suite-id t1_e1
python3 examples/parsec/v5/collect.py --suite-id t1_e1
```

v5 has no `--tasks targets` subset (unlike h4) — every v5 sweep so far has run
against the full task set, `--tasks all` (default).

The prompt bundles and all results live on the **`parsec-history`** branch
(`artifacts/`, `reports/`), which is an orphan branch holding no code. So a run
wants both branches checked out. Start from
`reports/v4/h4/handoff-t1-vs-g2.md` there.

## `h4/audit/` — read this before trusting a score

This benchmark has three ways for a failed trial to produce a plausible number,
and the harness's own accounting catches only the first:

| failure | how it looks | detector |
|---|---|---|
| harness error | reward `null`, `errored_trials` increments | built in |
| agent cancelled | scored **0.0**, `errored_trials` still **0** | `audit_trials.py` |
| simulator errored or invented data | plausible **partial** credit | `audit_absence_traps.py` |

A cancelled agent still writes a `reward.json`, and the verifier's completion
gate multiplies it by zero — so it reads as a legitimate wrong answer. Detect it
from the agent's final result event, never by searching the transcript for error
text: a structured `error_during_execution` contains no matching string, so the
search returns nothing and its silence looks like proof the trial was sound.

`compare_arms.py` applies that filter to every arm uniformly and prints
per-trial vectors, because a single mean per task hides the distribution — and
on a bimodal task, differencing means across arms manufactures findings.

## `v5/audit/pool_valid_trials.py` — when one run can't reach N clean trials

Re-evaluating a cap-evolve tag always overwrites `t0..t{n-1}`, it never
appends — so a task whose gateway keeps hanging mid-sweep can cycle through
several resubmissions without any single run landing N clean trials, even
though plenty of individually-clean trials exist once every attempt is
pooled. Move the short run aside to `run_<task>.dead-<timestamp>/` before
resubmitting (never delete or overwrite it in place) and this script finds
every clean trial across all of them, samples N at random, and reports the
mean — rather than requiring N-in-one-run or declaring the task a failure.
First used for `v5_g2_e1` (`results/v5/v5_g2_e1/summary.md` on
`parsec-history`); applies to any arm whose runs live under `.capevolve/`.
