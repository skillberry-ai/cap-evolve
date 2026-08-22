# Per-task fan-out — economics, briefing, canaries, assembly

Read this when the baseline's per-task `k/n` shows the loss **concentrated in a few named tasks**
rather than spread thin, and you want to spend the round's rollouts on those tasks instead of on
full-val gate rounds. SKILL.md carries the three rules that decide whether the shape is safe; this
file carries the arithmetic, the briefing contract, the canary-selection rule and the commands.

The numbers below come from real runs on a multi-turn tool-use benchmark with a mid-tier agent
model. The *shape* of each finding transfers; the figures are that run's.

## Why it is cheaper

A full-val gate round costs `val_n × n_trials` rollouts and returns *one bit per candidate*: accept
or reject. A single task at `n_trials` costs `n_trials` rollouts and returns the same bit — about the
failure that actually exists. At `val_n = 30, n_trials = 10` that is 300 rollouts per learning step
versus 10: **a 30× cheaper gradient**, on the unit the defect lives in.

Measured on one long run: five classic rounds spent ~1500 rollouts to produce **10 learning steps
and 1 accept**. The same budget under this shape buys **nine optimisers × six iterations = ~54
steps**, each aimed at one measured defect, and the per-task evals run concurrently so the
wall-clock cost is one round's.

## What to ask a parallel optimiser for

**A parallel optimiser's deliverable is a MECHANISM WITH TRACE PROOF, not a rate.** K optimisers
each evaluating is K processes, so a fan-out is BY CONSTRUCTION a high-load regime — the very regime
in which a per-task rate cannot resolve the effect anyone is looking for. Briefing K subagents to
"measure whether your edit helps" therefore asks them for the one thing their situation cannot
provide, and what comes back is K rate deltas drawn from a distribution wider than the effect.
Several prior rounds did exactly this and accepted edits on it.

Ask instead for evidence that does not depend on load:

| evidence | load-sensitive? | good for |
|---|---|---|
| the guard fired on the observed call | no | proving the mechanism engages |
| the agent's next action changed after it fired | no | proving the mechanism works |
| a direct call with the exact bad payload now succeeds / still refuses | no | proving repair logic, deterministically |
| the delivered docstring text contains the keys | no | proving the description reaches the model |
| count of clarification turns before the first write | barely | proving a behavioural prose change |
| per-task pass rate | **yes, heavily** | almost nothing, at fan-out load |

Then gate the surviving mechanisms yourself, serialised, on a quiet machine. The division of labour
is: **the fan-out finds falsifiable mechanisms and proves them structurally; the driver alone turns
mechanisms into numbers.** A subagent that reports "indistinguishable from noise" while showing its
guard firing correctly has done its job completely.

## Canary selection

**Draw canaries from the WHOLE suite, not from the neighbourhood of your mechanisms.** This is the
mistake that sank an artifact whose individual mechanisms all measured positive. The canary set was
nine tasks picked near the targets; the artifact then damaged four high scorers nobody was watching
— two at 1.00, one at 0.90, one at 0.80 — and the gate failed on exactly that collateral. **A canary
set that only covers what you aimed at cannot catch what you hit by accident.**

`integrate.py --canary-auto BASELINE.json` selects them mechanically: every task at or above
`--canary-floor` (default 0.90) that is not a target, lowest-rate-first so the most fragile high
scorers are the ones kept. Run against that round's own baseline it recovers three of the four tasks
that were actually damaged.

The fourth is the honest limit: it sat at **0.80**, under the floor. Lowering the floor catches it
and admits a noisier guard — a task at 0.80 moves about ±0.13 at n=10 by chance, so it will veto good
work at random. There is no floor that is both complete and quiet. Pick it deliberately: 0.90 for a
wide sweep where false vetoes are expensive, lower when you are integrating one mechanism and can
afford to investigate every flag.

**A canary needs two separately-launched readings, not 20 trials in one.** Measured: a task read
1.00 in 20/20 rollouts and then 2/5 the next day on byte-identical code at the same seeds. It had
been promoted to canary on the strength of that 20/20 — evidence which does not support the claim,
because repeats launched inside one occasion share whatever makes the task come out the way it does.
Two separate readings caught it; more trials in the first reading never would have. The consequence
cuts both ways:

* a task that disagrees between occasions must be dropped from the canary set, **and** must not be
  used to judge a candidate either — two of twelve target tasks moved +0.45 between occasions, so a
  per-task delta on them is uninterpretable;
* the discipline itself survives — the other eight canaries read exactly 1.00 on both occasions — so
  the fix is the selection criterion, not the idea.

**And a per-task effect that clears 2 SE once can still be wrong.** Measured: a task regression of
−0.288 at n=40 (z −2.61, resolvable) read −0.80 in one full-val block and **+0.30** in the next. A
single powered reading is not the floor for a per-task claim; agreement across separately-seeded
occasions is.

Cross-occasion drift on a hosted gateway turned out NOT to be the dominant term: mean per-task
movement was 0.123 across a day at low load versus 0.100 within a day, against 0.250 at high load.
Load dominates elapsed time. Check it rather than assuming either way.

## Running the fan-out, merging it, and remembering what it found

Each optimiser evaluates its own task at full trials **plus a canary of tasks measured stable at
baseline**, in one call, and writes traces so the next edit aims at an observed decision:

```bash
python "$A/taskeval.py" "$R/work/$TAG" <its-tasks> --project "$P" --n <num_trials> \
       --canary <stable-task-ids> --canary-n 3 --conc <low> --traces /tmp/tr_$TAG.json
```

Run every eval **detached** (`nohup … &`, then poll for the output file): under endpoint contention
a per-task eval can take 15-50 minutes, and a harness-level timeout has killed an eval that was
still healthy.

Findings go in a shared ledger, never in the coordinator's head — independent optimisers on
different tasks keep rediscovering one cause, and two of them implementing the same fix collide at
merge with only one of the two actually measured:

```bash
python "$A/mechanisms.py" list --run-dir "$R" --task "$TASK" --compact
python "$A/mechanisms.py" add --run-dir "$R" --owner "$TAG" --status proposed \
       --mechanism "<the cause, one sentence>" --evidence "<what you measured>" \
       --touches <function-the-fix-edits>
python "$A/mechanisms.py" add --run-dir "$R" --owner "$TAG" --status rejected \
       --supersedes <seq> --mechanism "<what turned out to be false>" --evidence "<the test>"
```

Assemble the result **one branch at a time, measuring after each** — never in a single merge:

```bash
python "$A/integrate.py" --base "$R/work/<parent>" --branches "$R/work/t7" "$R/work/t17" \
       --out "$R/work/cand_merged" --tasks <targets> --canary-auto "$R/<baseline-per-task>.json" \
       --n <num_trials> --conc <low> --floor <measured-null-delta>
python "$A/round.py" --run-dir "$R" --project "$P" --candidates cand_merged \
       --n-trials <num_trials> --k-se <gate_k_se>
```

`funcmerge.py` is the merge engine `integrate.py` drives per step; call it directly only to inspect
a single combination, and read its `dropped_additions` — a line a branch ADDED that the merge did not
carry is how a rejected subtraction gets silently re-applied:

```bash
python "$A/funcmerge.py" --base <parent>/<file> --out /tmp/try.py \
       --inputs <branchA>/<file> <branchB>/<file> --union-pure-insertions --json /tmp/fm.json
```

`merge_taskopt.py` remains for the whole-file case (a capability whose artifact is prose, where
per-function merging does not apply):

```bash
python "$A/merge_taskopt.py" --root "$R/work" --base "$R/work/<parent>" \
       --out "$R/work/cand_merged" --include t7 t17
```
