# platform-023-splunk-guid-no-events

<!-- BEGIN:auto -->

**task:** `platform-023-splunk-guid-no-events`  
**category:** platform  
**tranche:** regression  
**services:** platform  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_platform-023-splunk-guid-no-events/run_20260920_215411` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 1.000 |
| our baseline (v4_t1_e1) | test | 3 | 0.933 |
| seed (val, v4_t2_e1) | val | 5 | 0.960 |
| cand_0001 (val, v4_t2_e1) | val | 5 | 0.800 |
| cand_0002 (val, v4_t2_e1)  <- best (val) | val | 5 | 1.000 |
| final (test, v4_t2_e1) | test | 5 | 1.000 |

delta vs JB: 0.000 · delta vs our baseline: 0.067

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_platform-023-splunk-guid-no-events/run_20260920_215411/report.md`, `.capevolve/v4_t2_e1_platform-023-splunk-guid-no-events/run_20260920_215411/JOURNAL.md`

<!-- END:auto -->

## What the optimizer tried

Two iterations, both touching `orchestrator.md` and `shared_context.md`, plus `babylon_agent.md`/`aap2_agent.md` for domain-specific Splunk guidance (`cand_0001` also lightly touched `cost_agent.md`, `icinga_agent.md`, `ocpv_agent.md` and `security_agent.md`; `cand_0002` deliberately left those four alone because none of those agents run for this task). `cand_0001` diagnosed the entire 0.2 val loss as one forbidden clause — a seed trial's "the pod **never started** and therefore never emitted logs" tripped `expected.json`'s `inferred-from-silence` ban — and tried to fix it with a `### Reporting an Empty or Negative Result` contract in both `orchestrator.md` and `shared_context.md`: a 3-part shape (absence + scope → what it does/doesn't establish → next check) plus a Do-NOT-write/Write-instead table that named the banned phrasings explicitly, and matching guidance in `babylon_agent.md`/`aap2_agent.md` about what a zero-event Splunk result does and doesn't mean. `cand_0002` (the winner) removed that table and its enumeration entirely, replacing them with a new `### When a Search Comes Back Empty` section: a 4-part worked shape (Searched → `Result: no events — 0 results.` → what that establishes → what it does not tell us → Next checks) whose only forward-looking slot is a plain checklist of next checks, never framed as possible causes; a word-level vocabulary ban (the words "never" and "confirms"/"proves"/"shows" about what a result means, rather than a ban on specific phrases); and every open question forced into a fixed `whether`-form sentence.

## Why the winning candidate won

`cand_0001` was rejected: val fell from the 0.960 seed to 0.800 (Δ−0.160). JOURNAL.md's per-trial reconstruction shows the forbidden-hit rate went 1/5 → 4/5 because `cand_0001`'s own Do-NOT-write/Write-instead table printed the banned bigram "never started" and its neighbours 8+ times literally, and the checker does negation-blind substring matching — so a careful hedge like "does NOT establish ... that it never started" still contains the banned string and scores identically to the claim it was hedging against. `cand_0002` rewrote the rule rather than resizing it: it verified by grep that zero forbidden substrings from any of the 8 `none_of` entries remain anywhere in the 8 prompt files, removed the "does/does-not-establish" enumeration structure itself (rather than reframing it, since the enumeration was the slot the banned phrase kept finding a way into), and banned the trigger words at the word level so a hedge cannot satisfy the rule by negating a banned phrase. That combination took val from the 0.800 `cand_0001` low back up to 1.000, a net Δ+0.040 over the original 0.960 seed. Val and test move together on this task: `report.md` records the baseline `seed` skills at 0.96 ± 0.04 on the held-out test split — the same number as the val-seed score — and the optimized skills at 1.0 ± 0.0 on both splits, so the val delta (+0.04) and the test delta (+0.04) are, for this task, genuinely the same figure (confirmed from `report.md`'s explicit test lines, not assumed).

## Caveats

n=5 val trials is a small sample, and this was single-task tuning; with n=1 task, JOURNAL.md itself notes the gate's standard-error calculation falls back to a stricter comparison mode ("with n=1 task the gate reports SE=0 and warns it fell back to STRICT, so a 5-trial 0.8-vs-0.96 comparison is unarbitrated"), and even the accepted `cand_0002`'s own RESULT line is flagged `unresolved={platform-023-splunk-guid-no-events}` (its +0.040 move is below 2×SE of its own measurement). `cand_0001`'s rejected regression is itself the most useful artifact in this run: it demonstrates concretely that telling an agent what *not* to write, by printing the banned phrase in a Do-NOT-write table, is exactly the mechanism that produces the violation, because the reward's forbidden-substring check has no notion of negation or hedging.
