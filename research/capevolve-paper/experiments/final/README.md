# Post-cutoff machinery: B* artifacts, interleaved final evaluation

Owner: final-eval-eng.  Status: built and dry-run on search-split smoke subsets; the real run is launched by the coordinator at the
cutoff (2026-10-13 06:00 UTC).  Python 3.9 stdlib for every orchestration script (`python3 -I`); rollout workers run in the benchmark venvs
(Suite A `bench/venv`, B/C `bench/venv-tau2-8ebb749`).  Nothing here reads a final-set task until `order.py --tasks final` is run at freeze.

## Sequence at the cutoff (commands)

```
cd research/capevolve-paper/experiments/final
# 0  all searches stopped; owners re-run their converters (to_candidates.py, cand_logger.py) once so candidates.jsonl is complete
for S in A B C; do python3 -I bstar.py --suite $S; done                                   # manifests/bstar_<S>.json (counters only)
for S in A B C; do python3 -I reconstruct.py --suite $S --bstar-file manifests/bstar_$S.json; done   # artifacts_<S>.json + frozen copies
python3 -I draw_final_a.py --T <T> --write                  # ONLY on the coordinator's word; T from capacity.py; refuses to redraw
bench/venv/bin/python -I bench/local/make_agent_view.py bench/data/extracted/all_data_912_v0.1 $FINAL_EVAL_ROOT/A/agent_view_912
for S in A B C; do python3 -I order.py --suite $S --manifest manifests/artifacts_$S.json --tasks final; done   # order_<S>.jsonl + .sha256
git add experiments/final/manifests protocol/final_set/suiteA_final_tasks.json* && git commit -s ...   # script commit, then
python3 -I freeze.py --suites A,B,C                         # experiments/registry.jsonl (hash-chained); refuses on a dirty tree
for S in A B C; do python3 -I run_final.py prepare --suite $S --order manifests/order_$S.jsonl; done
for S in A B C; do python3 -u -I run_final.py run --suite $S --order manifests/order_$S.jsonl --workers 24 & done   # A concurrent with B+C
# exploratory, after the primary window:  order.py --extra transfer ; run_final.py run --extra transfer ; rejudge.py (B, C)
```

`FINAL_EVAL_ROOT` defaults to `campaign-scratch/final_eval`; results land in `{A,B,C}/results_long.csv`.

## Phase ordering (decisions 22:50)

The primary B* window runs first on every suite (`order_<S>.jsonl`: B* artifacts, seed, one-shot; END artifacts identical to B* ride along).
The distinct native end-of-run (5D) jobs are a separate file (`order.py ... --end-only` -> `order_<S>_end.jsonl`, run with `run_final.py run --extra end`)
and start only after the primary window is complete; if A's END would run past 2026-10-14 05:00 UTC it is dropped and disclosed.
HarnessLens/hl-v0 evaluation and the Azure transfer extras run after B and C primary.  `prepare` (Suite A) also checks that the sandbox has no internet egress.

## Files

| file | role |
|---|---|
| `fe_common.py` | suite/arm registry, run-dir map, hashing, atomic jsonl; imports `collect_metrics` (counter + classifier) rather than copying |
| `bstar.py` | B* from rollout counters only; `bstar_<S>.json` with every run's counter and counter source |
| `reconstruct.py` | native-selection artifact per arm/seed at B* and at the cutoff; frozen read-only copies + manifest with content hashes |
| `order.py` | one seeded random permutation of every rollout of a suite (seed 20261013); hashes the file |
| `run_final.py` | executes an order: one worker process per rollout, hang rule, retries, classifier, canary, resumable; aggregates CSVs |
| `draw_final_a.py` | Suite A stratified draw (T about 70, n=1); not run until freeze |
| `freeze.py` | analysis plan section 8/10 registry entries |
| `rejudge.py` | extra (a): re-judge saved tau2 simulations with gpt-4.1 |
| `capacity.py` | rollouts and wall clock at measured throughput |
| `tests/test_final.py` | unit tests (rules, order determinism, retry/hang rule, contract CSV parsed by `paired_cluster_bootstrap.load_long`) |

## Native selection rules (what `reconstruct.py` replays)

Mode B uses only events with `rollout_index <= B*` (an `evaluated` event is written when its evaluation ENDS, and events carrying
`start_rollout_index` are checked too, so a straddling evaluation is excluded).  Mode END uses all events (searches are stopped at the cutoff).
If nothing qualifies the arm's own seed candidate is returned and flagged `fallback_seed`.  Line numbers are in the local copies under
`campaign-scratch/baselines/`; the ones marked (checked) were read by me, the others come from a sub-agent read and should be spot-checked.

| arm | rule replayed | source | status |
|---|---|---|---|
| hc, ao (CapEvolve, rule P) | last `accepted` event (promotion after screen + fresh-trial confirmation) with index <= B*, else seed; END = `final.json`/`state.json` `best_id` | analysis_plan section 8, decisions 2026-10-11 11:00; E10B/cand_logger.py (accept flag) | ok on B and C. A: ao has a candidates.jsonl, hc not yet; fallback to events.jsonl `kind=step` + eval_index timestamps is implemented (partial) |
| GEPA 0.1.4 (A, B, C) | argmax of mean val over candidates fully val-evaluated by B*; ties to the earliest | `gepa/core/result.py:76-78` `best_idx = max(range(len(scores)), key=scores[i])` (checked) | ok; A indexes come from `to_candidates.py` (`exact:false` on created events, `exact:true` on evaluated) |
| SkillOpt@79124b37 (A) | last `selected` event (best_skill = last `accept_new_best`: strictly beats current AND best) | `skillopt/engine/trainer.py:1598-1599, 1706-1707` (checked), `evaluation/gate.py` ~176-224; final promotion `trainer.py:2194-2240` | partial at B*: indexes reconstructed from results.jsonl mtimes; decisions.md says "current accepted skill", native deployed artifact is `best_skill` (see below) |
| EvoSkill (A) | frontier replay (size 3, admit if room or score > worst), top by (score, tag index) | `src/registry/manager.py:325-344, 366-376, 378-427` (checked), `loop/runner.py:353`, `evoskill_run.py:167` | ok; partial only when the top of the frontier is a tie (tag-name order) |
| Meta-Harness (A) | running best by val over completed candidates (`incomplete:false`), ties earliest | campaign wrapper `metaharness/sb/mh_sb_run.py:152-166, 281-293` (checked); official `reference_examples/terminal_bench_2/meta_harness.py:373-393` | ok |
| WikiSkill community (A) | hill climb: accept iff strictly better than the incumbent, S0 first | `wikiskill/officeqa/loop.py:94-96` `eq4_accepted`, `engine.py:64-80, 269-272` | ok |
| Trace2Skill (A, cheap) | seed vs each variant scored once on val; strict argmax, seed wins ties; counts only if all variant val evals finished by B* | campaign wrapper `trace2skill/t2s_run.py:150-162` (checked); no official best-variant rule was found | ok, completion index from `rollouts_metrics.jsonl` row order |
| ACE (A, cheap) | best val playbook among val evaluations by B* | `ace/ace.py:781-783` (checked), wrapper `ace_run.py:199-205` | partial/impossible at B*: budget-coupled schedule (final_stop eval) cannot be replayed; impossible when no val evaluation happened by B* |
| MIPROv2 (A, cheap) | running strict max over FULL-valset evaluations only, seed program first | `dspy/teleprompt/mipro_optimizer_v2.py:548-549, 592-595` (checked), `mipro_run.py:132-141` | ok when a full eval exists; the default program's artifact differs from the CapEvolve seed (own prompt rendering) |
| HarnessLens (B) | last version accepted by a confirmed paired review, else v0; selection signal is train | `evolution/controller.py:578-603, 1050-1066, 1079-1088` | impossible until bl-harness provides the accepted-version chain with counter totals |
| one-shot control (B, C) | its single revision `cand_0001`, no selection, B*-independent | `E10B/collect_cap.py` | ok |
| seed | the seed candidate of every search (hashes compared; majority frozen, deviants listed) | | ok |

The artifact compared is always the canonical editable surface: A = `prompt.md` + `task_template.md`; B/C = `policy/**` + `tools/**`
(the seed capability tree is overlaid with them at evaluation time, exactly as the search harness did).  Identical artifacts are listed
in `duplicate_groups`; they are still evaluated per (arm, seed) cell (independent trials) unless the coordinator decides otherwise.

## Evaluation semantics

* One order file per suite; all arms (B* artifacts, END artifacts, seed with >= 2 trials, one-shot control) in one random permutation.  An END
  artifact identical to the arm's B* artifact is not rerun (its B jobs are flagged `also_end` and feed both result sets).
* Common random numbers: the trial seed is H(suite, task, trial), the same for every arm; a retry adds 7919 x attempt.
* Reward A = LibreOffice 25.8.7.3 recalculated hard score (`hard_restriction`), as-saved (`hard_no_recalc`) logged; B/C = tau2 reward from the
  campaign adapters.  Gateway tags `tag:FINAL-<S>-<arm>-s<seed>:<arm>:<role>` (END artifacts use arm label `<arm>-end`; canary `FINAL-<S>-canary-s0`).
* Hang rule: 3 h per rollout (process group killed after SIGTERM grace) = infra error, one retry with a new trial seed, then a MISSING cell.
  Other `infra` errors (uniform classifier): up to 3 further attempts.  `candidate`/`unverifiable` errors stand with their reward.  A harness
  failure (worker crash without result) is `infra`, never a 0.  Missing cells have no row.
* Outputs per suite in `FINAL_EVAL_ROOT/<S>/`: `results_long.csv` (contract: arm, seed, task, reward = mean over valid trials, family; extra: n_trials,
  reward_as_saved, t_start (min), t_end (max), error_class, error_text), `results_trials.csv` (one row per trial: trial, t_start, t_end, error_class,
  error_text, attempts, empty_output, raw_tool_text_last, tag), the same two with `_end` for the 5D secondary analysis, `per_arm_report.json`
  (attempted, retried, missing, infra, hangs, candidate errors, empty-output, raw tool text), `canary.jsonl`, `interruptions.jsonl`
  (start/stop/interrupt events = block boundaries), `raw/rollouts.jsonl` (every attempt, append-only), `raw/attempts/*/a*/` (job spec, worker log, trace, tau2 simulation).
* Resumable: rerun the same command; finished jobs are never re-executed; attempts that completed while the orchestrator was down are ingested.

## Open points / assumptions (also in the report to the coordinator)

* SkillOpt: decisions.md says "current accepted skill at B*"; I replay the native deployed `best_skill`.  Needs a coordinator ruling if they differ.
* Task family for tau suites = task id (no family metadata exists), so clusters = tasks.
* HarnessLens artifact/harness format is pending from bl-harness; its worker is not implemented (tau worker runs the CapEvolve tau agent).
* Suite A `hc` has no `candidates.jsonl` yet; ACE/MIPROv2/Trace2Skill have few events yet (search is early).
