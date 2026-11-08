# Demo — onboarding SkillsBench and optimizing its shared office skills with cap-evolve

This example takes **SkillsBench** (the first benchmark for how well agents USE skills)
from a single prompt (`PROMPT.md`) to an honest, optimized, **held-out** result. The
capability under optimization is the FOUR shared office-document Agent Skills the
benchmark hands its agent — `docx`, `pptx`, `xlsx`, `pdf`. The same four skills are
deployed to every task, so improving them moves many tasks at once.

- **Agent under test:** `claude-sonnet-4-6`, run by BenchFlow in a **Docker** sandbox.
- **Optimizer:** `claude-code @ claude-opus-4-8`.
- **Metric:** SkillsBench verifier pass rate (binary per task).

> SkillsBench is just the worked example — cap-evolve optimizes any agent capability
> (prompt, tools, or skill) against any eval. The fixes that made this run work are
> framework-level and benchmark-agnostic (see *What made it work*).

## Headline results

**Validation** (train == val = 7 tasks, 3 trials each — the metric the optimizer fits):

| | val pass rate |
|---|---|
| Baseline (seed skills) | **0.333** |
| Best candidate (`cand_0004`) | **0.714** |
| **Improvement** | **+0.381 (≈ +114% relative)** |

**Held-out TEST** (3 sealed tasks the optimizer never saw, 3 trials each, scored **once**
at finalize — on BOTH the baseline and the optimized skills):

| | held-out test pass rate | per-task (pdf-excel-diff · pptx-reference-formatting · reserves-at-risk-calc) |
|---|---|---|
| Baseline (seed skills) | **0.556** | 1.0 · 0.67 · 0.0 |
| Optimized skills (`cand_0004`) | **0.667** | 1.0 · **1.0** · 0.0 |
| **Improvement** | **+0.111** | the optimized `pptx` skill made `pptx-reference-formatting` reliable |

Raw numbers: [`run_full/final.json`](run_full/final.json) · [`run_full/report.md`](run_full/report.md).
`reserves-at-risk-calc` stays 0 for both — the optimizer diagnosed it (and the last
val task) as a **broken/hardcoded oracle** and correctly refused to overfit it.

## How the run progressed (7 iterations, paired significance gate on val)

Each iteration: diagnose the current best's val trajectories → `claude-opus-4-8` proposes
edits to the four skills → re-evaluate on val (3 trials) → the **paired gate** accepts
only gains that clear `0.2·SE` → commit. Full handover in [`run_full/JOURNAL.md`](run_full/JOURNAL.md).

| iter | val | Δ | verdict | what the optimizer did |
|---|---|---|---|---|
| seed | 0.333 | — | baseline | unmodified skills |
| cand_0001 | 0.381 | +0.048 | **accept** | a real **PivotTable creation script** + "recalc after editing a workbook" rule + FK-reconcile sentinel note |
| cand_0002 | 0.571 | +0.190 | **accept** | pptx **embedded-xlsx recalc** + xlsx percent-format & join-hygiene rules (fixed exceltable-in-ppt, sales-pivot, weighted-gdp, offer-letter) |
| cand_0003 | 0.619 | +0.048 | **accept** | a directive worked-example for **unmatched-foreign-key → null** (invoice-fraud) |
| cand_0004 | **0.714** | +0.095 | **accept** | an **anti-stall activation directive** at the top of all four skill bodies (fixed invoice-fraud + sales-pivot) — **final champion** |
| cand_0005–0007 | 0.62–0.71 | ≤0 | reject | no skill edit helps: the 2 remaining failures are **broken oracles** (gold internally inconsistent / hardcoded). Ceiling reached; champion held. |

## What the optimizer changed (the FULL skill directory, not just prose)

`cand_0004` vs the seed edited **all four** `SKILL.md` bodies **and added executable
scripts inside the skills**: `pptx/scripts/recalc.py` and a new `xlsx/scripts/`. That the
optimizer ships *verified scripts* (not just prose) is deliberate — see below.

### Real edits the optimizer made — and the failure each one fixed

These are the optimizer's own additions (the `+` lines), tied to what the **trajectories**
showed the agent doing wrong. They generalize across the task class (no hardcoded answers).

**1. `pdf/SKILL.md` — unmatched foreign key → `null` (cand_0003 → fixed `invoice-fraud-detection`).**
*Trajectory:* the agent extracted a purchase-order id, found it wasn't in the reference table,
classified it "Invalid PO", and then **echoed the raw string** `PO-INVALID` — but the verifier
asserts `po_number == None`. The optimizer added a reconcile-then-null rule with a worked example:
```diff
+ ### Reconciling extracted data against reference tables
+ A key read from the document is only valid if it is found in the reference data. If it is
+ NOT found, the field is "missing/invalid" and you record the not-found sentinel (null/None)
+ — you do NOT echo the raw string the document printed for it.
+ "Missing" means *fails its lookup*, regardless of what the document shows: a non-empty
+ placeholder (e.g. `PO-INVALID`, `N/A`, a typo'd id) absent from the reference table is still
+ "missing" → write null, not the placeholder.
+ ```python
+ po = po_raw if po_raw in known_po_numbers else None   # unmatched -> null sentinel
+ # WRONG: record["po_number"] = po_raw  # echoes an unmatched placeholder
+ ```
```

**2. `xlsx/SKILL.md` — match the cell's number format (cand_0002, part of the +0.190 jump).**
*Trajectory:* a "percent of" cell was written as a bare ratio (`0.197`) while the target cell's
format was a plain number, so it read **100× too small** vs the expected `19.7`. The optimizer
added a number-format rule:
```diff
+ ### Percentages: scale the stored value to match the cell's number format
+ - If the cell's number format includes `%` (e.g. `0.0%`), store the raw ratio (`=a/b`).
+ - If it's a plain number (e.g. `0.0`, `General`), the stored value IS the displayed value,
+   so a "percent of" result must be the ratio times 100 (`=a/b*100`). A bare `=a/b` would
+   store 0.197 where the task expects 19.7.
+ ### Joining two data sources: drop rows that fail the join
+ Use an inner join (or drop unmatched rows) so every output row has all required fields;
+ carrying NaN/blank totals through makes a verifier reject the record.
```

**3. All four `SKILL.md` bodies — anti-stall activation directive (cand_0004, +0.095 → champion).**
*Trajectory:* on the hardest tasks the agent **narrated waiting** for the skill ("waiting for
the skill to finish/return") instead of doing the work — a behavioral STALL the optimizer
diagnosed across trajectories and fixed by prepending one activation line to every skill:
```diff
+ > **You are now running with this skill loaded.** This is reference guidance injected into
+ > your context — it does not execute on its own or return results for you to wait on. Do the
+ > task yourself, starting now… Never pause "waiting for the skill to finish" — you are the
+ > one doing the work.
```
This single behavioral fix (plus a re-added reconcile rule) flipped `invoice-fraud-detection`
and `sales-pivot-analysis` and took the champion to **0.714**.

> The optimizer also added executable scripts it **verified by running** (it can now run Bash):
> a real OOXML PivotTable / recalc helper under `pptx/scripts/` and `xlsx/scripts/` — a script
> the agent runs, for a deterministic step prose kept failing to elicit.

## What made it work (general, benchmark-agnostic fixes)

An earlier run plateaued; the forensics (in `JOURNAL.md`) showed the limiters were **not**
trajectory analysis or state-passing (those worked) but four fixable issues:

1. **The optimizer couldn't run code** — `--permission-mode acceptEdits` blocks shell, so
   it "could not verify a script, so refused to ship it" and fell back to `SKILL.md` prose.
   Fix: the `claude-code` optimizer now gets `--allowedTools Bash` (`optimizers/registry.yaml`)
   → it **writes scripts and verifies them by running**, hence the `scripts/` additions above.
2. **Single-trial noise** — 2 tasks flipped randomly run-to-run, so the gate rejected real
   gains as noise. Fix: `num_trials: 3` → a real per-task mean + SE.
3. **Serial evaluation** (~50 min/iter). Fix: the adapter runs all tasks of a split in **one
   `bench eval run` with `--concurrency`** → ~one-task-time per trial.
4. **One-sided finalize** — only the optimized best was scored on test. Fix: `harness.finalize`
   now scores **both the baseline (seed) and the optimized best on the sealed test split**
   (each only *reserves* the seal; it is committed once), so the headline is the honest
   held-out *improvement* — for any benchmark.

## The pieces (what following `PROMPT.md` produced)
| File | What it is |
|---|---|
| [`adapters/adapter.py`](adapters/adapter.py) | `tasks` (the 10 task ids), `run_batch` (ONE `bench eval run --concurrency` over all the split's tasks, sonnet agent in Docker, candidate skills injected at `/skills`), `score` (binary verifier reward + gold-safe failed-test feedback from the CTRF report), `materialize` (multi-skill-package aware). Deploys only the four real sub-packages from a unique, absolute, per-candidate jobs dir. |
| [`adapters/anthropic_env.py`](adapters/anthropic_env.py) | Reads the IBM Anthropic-compatible gateway creds from repo-root `.env` (no dep) for `--agent-env` propagation into the sandbox. Token never hardcoded. |
| [`seed_capability/`](seed_capability/) | The four shared skills are **not vendored** (they are Anthropic-licensed); `setup.sh` **extracts** them from your SkillsBench clone into `.capevolve/project/seed_capability/`. See [`seed_capability/README.md`](seed_capability/README.md). That copy is what the optimizer edits and what is deployed to every task. |
| [`optimizer/INSTRUCTIONS.md`](optimizer/INSTRUCTIONS.md) | Optimizer guidance scoped to **skill-package** (full edit surface: SKILL.md · references · **scripts** · description; verify scripts by running; placement; INTENT-only JOURNAL + framework RESULT lines; non-overfitting). |
| [`capevolve.yaml`](capevolve.yaml) · [`split_ids.json`](split_ids.json) | Run spec (hill-climb · **7 iters** · **3 trials** · paired gate `k_se 0.2` · opus-4-8 optimizer · `$40`/iter cap) and the pinned split (train == val = 7, test = 3 sealed). |
| [`setup.sh`](setup.sh) · [`smoke.sh`](smoke.sh) · [`run.sh`](run.sh) | Onboarding transcript (install + clone SkillsBench + `benchflow` + scaffold + `cap-evolve check`); 1-task smoke; full run. |
| [`run_full/`](run_full/) | Saved result artifacts: `final.json`, `report.md`, `events.jsonl`, `JOURNAL.md`, `baseline.json`, `rejected.jsonl`, `SKILLSBENCH_COMMIT.txt`. |

## Reproduce
```bash
bash examples/skillsbench/setup.sh   # install + onboard + GREEN cap-evolve check
bash examples/skillsbench/smoke.sh   # 1 val task — sonnet in Docker → real verifier reward
bash examples/skillsbench/run.sh     # full run (7 iters · 3 trials) + dashboard on :7878
```
Prereqs: Docker, `uv`, a logged-in Claude Code session, and the Anthropic gateway creds in
repo-root `.env` (`ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`). Step-by-step:
[`docs/REPRODUCE_skillsbench.md`](../../docs/REPRODUCE_skillsbench.md).

## The key mechanism — skill injection
`run_batch` calls `bench eval run … --skill-mode with-skill --skills-dir <candidate>`.
Because `<candidate>` differs from each task's own `environment/skills`, BenchFlow STRIPS
the task's bundled skills (and the Dockerfile `COPY` of them) and mounts the candidate's
four optimized skills at `/skills` instead — so one optimized set is deployed to every task.

## Honesty
- Train/val/test split once; **test scored only at finalize** (3 held-out tasks), on both
  baseline and optimized skills, exactly once on the sealed split.
- Acceptance gated on **val**; train == val here (the engine logs a `splits_warning` — val is
  the fit metric; the **test** numbers above are the held-out result).
- `score()` is deterministic (reads the recorded verifier reward; never re-runs); feedback is
  gold-SAFE: only the agent's own failed test names + assertion messages, never the oracle.
- SkillsBench commit pinned in [`run_full/SKILLSBENCH_COMMIT.txt`](run_full/SKILLSBENCH_COMMIT.txt).
