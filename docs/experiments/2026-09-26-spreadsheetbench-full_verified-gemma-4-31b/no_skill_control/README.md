# No-skill control — run 36306060353

The anchor the headline result needs: the **same** model, dataset, split, metric and turn budget,
with **no capability at all**. Without it our `+0.1321` delta cannot be set against the reference
paper's `48.3 → 68.0`, because our "baseline" is a tuned artifact and theirs is an empty context.

| | val (40 tasks) | **sealed test (280 tasks)** |
|---|---|---|
| **no skill** (both surfaces cleared) | 0.600 | **0.629** |
| seed capability (run 36175707483) | 0.625 | 0.6321 |
| champion `r3_decide` (run 36175707483) | 0.8875 | 0.7643 |

**The no-skill agent solves 175 of 280 sealed tasks. The tuned seed solves 177.** A two-task
difference, against a binomial SE of 0.029 — about a tenth of one standard error. On val the same
comparison is 0.600 vs 0.625 (SE 0.077 on 40 tasks). By both splits, **the seed capability adds
nothing measurable over no capability at all.**

`0.629` is the figure the harness books (`data/steps.jsonl`, `finalize_baseline`): 175/278, the
tasks with a paired score. Counting the two infra-errored tasks as failures gives 175/280 = 0.625.
Both are quoted rather than one, because no conclusion here turns on the difference.

## Verification that this is a real control

The first attempt at this measurement (run 36261022325) was **not** a no-skill control:
`SB_EMPTY_SEED` blanked `prompt.md` but left `task_template.md` — 2,453 of the capability's 3,418
bytes — in place, and its 0.668 was retracted. #545 fixed the flag. So this run's blanking is
evidenced three ways rather than assumed:

1. **The run's own record of the seed's files** is a single empty file —
   `verification/seed_files.json`:
   ```json
   [{"name": "prompt.md", "text": ""}]
   ```
   `task_template.md` is **absent**, not blank. That distinction is the whole point: a *blank*
   override would hand the agent an empty user message and score every task 0, whereas a *missing*
   file restores the adapter's built-in `_TASK_TEMPLATE` — the correct no-skill condition, and
   close to the paper's own Appendix E.1 prompt with an empty `{skill_section}`.
2. **`prompt.md` is 0 bytes** (`size=0`) and present. Present-and-empty means *no system message*;
   deleting it would have fallen back to the adapter's built-in default prompt and measured that
   while claiming no skill.
3. **The log says so**, at 08:25:11Z:
   ```
   >>> spreadsheetbench: EMPTY seed (no-skill control) — prompt.md blanked,
       task_template.md removed (built-in _TASK_TEMPLATE applies)
   ```

The contrast inside the artifact is the strongest single piece of evidence: `cand_0001` carries
**both** a `prompt.md` and a 6,493-byte `task_template.md`, while the seed carries one empty file.
Both surfaces really were cleared, and the optimizer really did write to both.

## Consequences for the comparison

- **The seed-adds-nothing finding is confirmed** on the sealed split, not just inferred from val.
  Whatever the optimizer achieved, it did not start from an advantage the seed conferred.
- **The harness-comparability concern survives, and sharpens.** Our no-skill floor is **62.9**
  against the paper's **48.3** for the same model — **+14.6 points before any skill exists**, and
  within noise of their *SkillOpt* (63.1). A no-skill agent in this harness is roughly as good as
  their best-but-one published system, so a large part of both the 76.4 and the 68.0 is harness
  (scaffold, tool surface, 30-turn budget, scoring path), not capability.
- **The optimizer's contribution restated over a true floor:** 0.629 → 0.7643 = **+0.135**,
  essentially identical to the +0.132 measured over the seed — as it must be, since the seed and
  no-skill are the same thing.

## An unexpected result, flagged not leaned on

From a blank start, **one** hill-climb round produced `cand_0001` at **0.854 sealed** (239/280) —
*above* the treatment run's 8-round champion at 0.7643, and above the paper's WikiSkill 68.0. Its
edit is in `data/cand_0001.diff`; it wrote a 6,493-byte `task_template.md` from nothing.

This is n=1 from a different algorithm (`hill-climb-all`, 1 iteration) than the headline run
(`agent-optimize`, 8 iterations), and 0.854 is a *finalize* number selected on val, so some of the
gap is selection optimism. It is not a result to publish. It is a strong hint that the 8-round
agent run underperformed what the pipeline can do, and it is the most interesting thing this
control turned up.

## Provenance

| | |
|---|---|
| run | [36306060353](https://github.com/skillberry-ai/cap-evolve/actions/runs/36306060353) |
| branch / sha | `temp-no-skill-run5` (deleted) / `b1871c5c103a279f28d7fdac95bf46749638ef1c` |
| algorithm | `hill-climb-all`, `iterations=1`, `trials=1` |
| agent / optimizer | `ibm-rits/google/gemma-4-31B-it` / `ibm-ete-int/aws/claude-opus-5` |
| wall clock | 8h27m (`finalize_baseline` alone 4h57m — a blank capability burns all 30 turns) |
| optimizer cost | $15.84 |

Attempts 1–4 failed on, in order: the wrong condition (#545), a transient RITS stall, the #536
entitlement regression (#546), and an unrecoverable log from a hung poller (#551). Only attempt 5
is reported.

```
data/report.md        rendered report incl. all 280 per-task rows
data/metrics.jsonl    280 per-task records (reward_baseline = no skill, reward_opt = cand_0001)
data/steps.jsonl      4 booked steps; `finalize_baseline` is the number above
data/events.jsonl     20 events with timings
data/runmeta.json     run identity + dispatch config
data/cand_0001.diff   what one round wrote starting from nothing
verification/seed_files.json   the run's own listing of the seed capability
```
