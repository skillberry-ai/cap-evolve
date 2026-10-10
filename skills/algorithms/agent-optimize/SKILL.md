---
name: agent-optimize
description: 'Free-form optimization algorithm for agent orchestration mode: the conversational agent owns the whole search — reading a digest, proposing big coherent capability edits against failure-cluster hypotheses, probing only missing cells, promoting or pruning on a posterior, merging complementary branches, and sealing test once. Use when orchestration_mode is agent and algorithm_skill is agent-optimize. For a deterministic loop use hill-climb, gepa or skillopt instead.'
component: algorithm
argument-hint: "agent-mode only — set orchestration_mode: agent + algorithm_skill: agent-optimize"
allowed-tools: Read, Write, Edit, Bash, Task
provides: [candidate]
needs: [scores, traces, candidate]
---

# agent-optimize — the loop you own

You are the optimizer. `cap-evolve run` (agent mode) does check -> baseline and hands you `R`. Everything
else is six `act.py` verbs and one `digest.py`; the scripts decide, you judge.

## Honest statistics (read twice)

1. Noise sd of a full-val mean is ~0.05 (30 tasks x 3 trials): only big effects are resolvable. Never
   re-test a within-noise delta; make a bigger edit instead.
2. Never view test traces. Test is sealed, scored ONCE at finalize, and development-exposed after use.

Details only when needed: [`references/stats.md`](references/stats.md).

## Setup

The loop REQUIRES the new engine. Put this in `capevolve.yaml` (or export `CAPEVOLVE_<NAME>=1`):

```yaml
optimizer:
  ablation: {dag_parallel: true, active_eval: true, smart_merge: true, cost_gating: true,
             failure_clustering: true, pregate: true, context_digest: true}
```

Stock default has `active_eval` OFF: `probe --auto` then silently runs FULL val. The digest prints
`!! CONFIG: ...` at the top (after any INFRA line) when any switch is off; fix it before looping. Switches: [`references/ablation.md`](references/ablation.md).

```bash
R="<run_dir from the handoff>"; P="<project dir>"
S="${CAPEVOLVE_SKILLS_DIR:?set to the skills/ dir}"; A="$S/algorithms/agent-optimize/scripts"
mkdir -p "$R/work"
python "$A/spend.py" --run-dir "$R" --project "$P"      # parses stop_condition; ask the user if constraints.ambiguous
python "$A/digest.py" --run-dir "$R" --project "$P"     # first line must NOT start with "!! CONFIG"
BEST=$(python "$A/digest.py" --run-dir "$R" --project "$P" --format json | python -c 'import json,sys;print(json.load(sys.stdin)["champion"]["id"])')
```

`BEST` is the digest's champion (re-read it after every promote). Read once: `PROJECT.md`,
`capevolve.yaml`, the adapter, the files under `capability_path`, `optimizer/INSTRUCTIONS.md` if
present (benchmark facts only; ignore its "one edit" advice).

## The loop

```bash
python "$S/phases/diagnose/scripts/run.py" --run-dir "$R" --tag "$BEST" --split val --cluster v2 > /dev/null
python "$A/digest.py" --run-dir "$R" --project "$P"
```

Diagnose writes a SLIM `$R/clusters.json` (ids, labels, exemplar trace ids) and the heavy
`clusters_full.json`. Never `cat`/Read `clusters_full.json` (MBs of embedded traces).

1. **Digest.** One screen: budget, noise, clusters (with hypothesis status), branch tips (posterior,
   coverage, P(beat parent/champion)), merge opportunities, pregate warnings, suggestions. Act on it.
2. **Read RAW evidence** for the chosen cluster's exemplar trials: full tool-call args and the full
   conversation, never clips. Split deterministic tool bugs (fix in code) from policy failures.
   [`references/forensics.md`](references/forensics.md) has the dump command and subagent hand-off.
3. **Pick a hypothesis** covering >= 2 tasks (or headroom >= 0.06), or a deterministic tool bug. Write
   it to a JSON file ([`references/clusters.md`](references/clusters.md) for the schema).
4. **Make a BIG coherent edit** under `work/TAG`: policy and tools together when the failure needs both.
   General rules only, never a task id or answer. No single-task edits (their ceiling is below noise).
   Never hide write calls inside a composite tool. Form by failure type:
   [`references/tool-edit-lessons.md`](references/tool-edit-lessons.md).
5. **Propose, probe, decide:**

```bash
python "$A/act.py" propose cand_1 --run-dir "$R" --project "$P" --parent "$BEST"     # 1st call: creates work/cand_1
python "$A/act.py" propose cand_1 --run-dir "$R" --project "$P" --parent "$BEST" --hypothesis-file "$R/work/h1.json"   # 2nd: rule + pre-gate + record
python "$A/act.py" probe cand_1 --run-dir "$R" --project "$P" --auto --plan          # missing cells, spends nothing
python "$A/act.py" probe cand_1 --run-dir "$R" --project "$P" --auto --n 3 --budget 60
python "$A/act.py" promote cand_1 --run-dir "$R" --project "$P"                      # needs full-val coverage
python "$A/act.py" prune cand_1 --run-dir "$R" --project "$P" --reason "<why>"
```

   Pre-gate failure: fix the edit (the text says what), propose again. Probe runs only cells the ledger
   lacks, on the hypothesis tasks plus sentinels (`--tasks a,b` to choose). The digest posterior says
   promote (P(beat champion) high at full coverage), prune (clearly worse) or continue (probe more).
   `promote` that does not accept leaves the node `alive`; best_id does not move. Full-val probes need `--yes`.
   When the budget is EXHAUSTED even `propose` refuses (`--over-budget REASON` is recorded).
   Before each promote/prune append `## Iteration TAG` to `work/TAG/JOURNAL.md`: what changed (file ->
   cluster), expected effect, what the numbers said, next focus.
6. **Merge** complementary branches (digest `merge_opps`):

```bash
python "$A/act.py" merge cand_1 cand_2 --run-dir "$R" --project "$P" --tag cand_m
```

   then probe and promote `cand_m` like any node. [`references/merge.md`](references/merge.md).
7. **Repeat** from the digest until it says stop (budget, goal met, or `stop_condition`). Then finalize.

## If the digest says X, do Y

| digest says | do |
| --- | --- |
| cluster open, >= 2 tasks or headroom >= 0.06 | hypothesis + big edit + `propose` |
| cluster stuck (2 failed attempts) | re-read raw full traces (never test), change the edit FORM, not wording |
| same tool-error signature across tasks | fix it in tool code; no multi-task argument needed |
| pregate warning (tool fixture fails, policy growth) | fix before any probe; it is free |
| tip at full coverage, P(beat champion) high | `promote` |
| tip P(beat parent) low after full probe | `prune` with the numbers |
| tip partial coverage, undecided | `probe --auto` for more cells |
| gate verdict inconclusive (low coverage / unstable) | not a reject: `probe` more cells (legacy `commit.py --decision inconclusive`); never `prune` on it |
| delta within noise (`noise.sd_est`) | do not re-test; make a bigger or different edit |
| `noise.stale` | buy a seed duplicate probe, then re-read noise |
| merge_opps listed | `merge`, probe the union of wins, `promote` |
| budget EXHAUSTED | stop; `finalize` (spending verbs refuse; `--over-budget REASON` is recorded) |
| infra warnings | read them; `--strict` makes them refusals |
| objectives / cost constraints | [`references/objectives-cost.md`](references/objectives-cost.md) |
| need to turn a switch off or run legacy | [`references/ablation.md`](references/ablation.md) |

## Finalize (once)

```bash
python "$A/act.py" finalize --run-dir "$R" --project "$P" --n-confirm 3
python "$S/phases/report/scripts/run.py" --run-dir "$R"
```

Confirms the champion on full val with fresh seeds, tests it against the seed, seals test ONCE, writes
`final.json`. If the confirm does not accept, finalize refuses to seal (`--seal-anyway REASON` records
"no accepted change"). Report refusals unsoftened: `best_id == seed` is a null result with a diagnosed
cause; an empty split is `empty`, not 0.0; a no-holdout spec is a FIT metric. No finalize, no result.

## Invariants

Core enforces the split seal, val-only gating and the tamper guard. Yours: never hand a subset result to
`gate_check.py`; every round leaves run-dir artifacts (JOURNAL.md entry in `work/TAG`, DIAGNOSIS.json);
report a broken framework file, do not work around it. Wait for finalize to exit or the seal is wasted.

## References

One level deep; load only when the digest points there.

- [`references/forensics.md`](references/forensics.md) — raw-trace dump, subagent diagnosis, composite-tool pitfall. **Load** before your first edit and when stuck.
- [`references/clusters.md`](references/clusters.md) — hypothesis schema, per-task rates. **Load** when picking or writing a hypothesis.
- [`references/merge.md`](references/merge.md) — merge flow and conflicts. **Load** when `merge_opps` is non-empty.
- [`references/objectives-cost.md`](references/objectives-cost.md) — cost gating, budget, stop_condition. **Load** when objectives are set or budget is tight.
- [`references/ablation.md`](references/ablation.md) — the seven switches. **Load** before disabling any.
- [`references/tool-edit-lessons.md`](references/tool-edit-lessons.md) — edit forms, guard closure. **Load** before editing a surface the first time or after a stuck cluster.
- [`references/stats.md`](references/stats.md) — what the numbers resolve, sign test. **Load** when a result surprises you.
- [`references/legacy.md`](references/legacy.md) — all switches off: pointer to the archived round-loop docs. **Load** only in legacy mode (old SKILL sections live in docs/archive/agent-optimize-legacy/legacy-SKILL.md).
