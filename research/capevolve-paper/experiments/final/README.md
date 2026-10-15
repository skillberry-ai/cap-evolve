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

## Counted-rollout definition for N* (one quantity for every arm)

Counted = rollouts consumed under the method's own SEARCH budget: baseline/seed evaluations, screens and confirmations, native selection evaluations (GEPA valset, SkillOpt selection evals),
HarnessLens baseline trials and retries; EXCLUDED: post-search finalize and sel re-scoring (champion and seed on sel-25 after the search), chaser/post_sel scoring, final-eval rollouts.
Source texts: decisions.md 2026-10-11 ('600 target rollouts per search, all evaluations count'; the tau runs are '550 + finalize'), CHECKPOINT_PROTOCOL.txt 2-3 (counter totals, evaluation straddling B*).
Audit of counter sources (bstar.py `search_counter`): Suite A hc/ao daemon `logs/rollout_counter.json` (starts, incl. baseline, probes, confirms; no finalize on A), GEPA/SkillOpt/EvoSkill/Meta-Harness/WikiSkill/
Trace2Skill/ACE/MIPROv2 `rollout_counter.json` (search budget counters), HarnessLens `rollout_counter.json` (baseline_used + rollout jobs + retries): all search-only, unchanged.
Only the tau CapEvolve runs (hc, ao, hcstock on B/C) had a counter (`state.json spent.metric_calls`) that includes the host-side finalize (champion and seed on sel): there the count is the number of logged
rollouts outside the sel/test/FINAL splits (ao s0 198 -> 148, s1 197 -> 147, s2 172 -> 147; C ao 110 -> 100; the sel-25 rows are finalize rollouts or, for ao s2, the seed's pre-repair sel measurement; ao s2's search is still running). Cross-check: the count equals the number of files under `.capevolve/run_main/rollouts/val`.  Both raw and search counters are written to bstar_<S>.json.

## Inert = identical rendered target-facing content

The tau adapters strip `policy/policy.md` and treat '' and '(none)' as no addendum (wt-tau examples/tau2_retail/adapters/adapter.py:210-221; wt-airE examples/tau2_airline_c/adapters/adapter.py:210-221), so '(none)' and '(none)\n' render identically;
tools code is compared right-stripped.  The SpreadsheetBench adapter uses prompt.md and task_template.md byte-for-byte (bench/patches/new/adapter.py:981-984, :921), so Suite A stays strict.
`inert` (and `inert_fraction_by_arm`) uses this rendered identity (`identical_to_seed_normalized`); the strict byte hash stays as `identical_to_seed`.

## Phase ordering (decisions 22:50)

The primary B* window runs first on every suite (`order_<S>.jsonl`: B* artifacts, seed, one-shot; END artifacts identical to B* ride along).
The distinct native end-of-run (5D) jobs are a separate file (`order.py ... --end-only` -> `order_<S>_end.jsonl`, run with `run_final.py run --extra end`)
and start only after the primary window is complete; if A's END would run past 2026-10-14 05:00 UTC it is dropped and disclosed.
HarnessLens/hl-v0 evaluation and the Azure transfer extras run after B and C primary.  `prepare` (Suite A) also checks that the sandbox has no internet egress.

## Suite B concurrency (decision 2026-10-12)

One interleaved stream per suite (drift control across arms), n=3 kept.  `run_final.py run --suite B ... --class-caps hl=24,default=12` gives HarnessLens/hl-v0
cells (33 min per rollout) their own pool of up to 24 workers next to 12 for the tau-agent cells; jobs are still dispatched in order within each class.  The shared
gpt-oss cap is the gateway's 24 in flight.  Fallback only: a separate HL order file (`order.py --arms harnesslens,hl-v0`) if the single stream measurably cannot absorb it.

Capacity (2026-10-12, bl-harness FE_dry_hl10: 8 v0 trials under search load, old timeouts): wall_s mean 2145, median 2277, p90 3336, max 3723; target_calls median 15.5,
p90 25 (about 25 gpt-oss calls per rollout with the user simulator).  HL primary = 480 rollouts = 286 worker-hours: W=16 18.9 h, W=24 12.9 h, W=32 9.9 h (each +~1 h tail).
Window 06:30 -> 2026-10-14 05:00 = 22.5 h, so B finishes with HL at W=24 (slack ~5 h); distinct HL END cells (~180 rollouts, +4.5 h) fit after the primary window; W=16 does not.
gpt-oss: HL at W=24 issues about 24 x 25 / 2145 s = 17 calls/min of the 127/min budget (total B+C call load ~9.3 h), so calls are not the limit.  The limit is the gateway's
24 in-flight slots shared with the tau-agent cells: if a call holds a slot ~40 s (assumed, to be measured), HL at W=24 occupies ~11 slots and 12 tau-agent workers ~10, i.e. ~21 of 24;
W=32 would push demand above 24 and only queue, so the decision (coordinator, 2026-10-12, superseding an earlier hl=32) is hl=24,default=12; watch_queue.py reports the median gpt-oss queue_s and, above 60 s, the class caps are rebalanced using the measured slot hold time.  END fallbacks unchanged (drop HL END first, disclosed).

## Suite D (tau2 retail, Azure target gpt-4.1-mini; added 2026-10-12)

`--suite D`: approved set only (Tier 1 + E26-nohist): runs/E20/{PT,P,T,CTL,GEPA}, runs/E21/{ruleP,1S}, runs/E26/nohist (names after tau-runner; `fe_common.D_DIRS`), arm keys pt p t ctl gepa rulep 1s nohist.
Final state compared (no B*): last promoted candidate, else the seed, filed under mode B.  Models fixed in `order.py` D_MODELS (target `azoai/gpt-4.1-mini-2025-04-14`, user simulator and NL judge `azoai/gpt-4.1-2025-04-14`,
gateway :4112, tags `FINAL-D-*`).  Tasks = H65 (sel-25 + sealed test-40) with a `split` column everywhere (primary = test-40, H65 descriptive); GEPA cells are test-40 only; trials: champions 5, seed 10 (+ one seed-check cell), all in one stream.
`run_final.py run --suite D --workers 128` (Azure only; 429-aware sleep before infra retries).  A champion whose `surface_violations.json` is non-empty keeps its cell (ITT) and gets the dagger flag (second computation without it).
Capped-token guard: `run_final.py` polls the gateway and stops dispatching with a PAGE_CAPPED_TOKENS file if the capped counter passes `--capped-stop` (default 198M, cap 200M).  Comparison family rows (D m=11, D-sec m=4) are in freeze.py.
## Suite E (tau2 airline replication of D; added 2026-10-12)

`--suite E`: same shape as D on the airline split (official test-20 primary, H30 = sel-10 + test-20 descriptive, trials 5 per champion/competitor, seed 10, tags `FINAL-E-*`, gateway :4112, adapter worktree
`wt-airE` = eb112a08 + logging b797886c8, pinned and hashed in freeze.py).  Run roots (fe_common.E_DIRS): E30/{PT,P,T,CTL,GEPA}, E31/{ruleP,1S}, E36/NOHIST (the 8 ablation cells; GEPA cells test-20 only);
competitors E32/{ace,mipro,gepafull,ao} (own Holm; ao daggered; GEPA-full selects on sel-10, so test-20 only) and E10E/harnesslens (1 exploratory seed).  No B*/N*: each cell's final state.  Cell order if time is short:
E30-PT, P, T, seed, then E31-ruleP, E36, E30-CTL, E31-1S, E30-GEPA, then competitors, then E25 (`decompose.py --suite E`, n=3 on H30).  E searches may end after the A/B/C cutoff: E scoring starts when they end.
Suite E has its own order file and its own single interleaved window (never pooled with D); the seed artifact (n=10) and all cells are in one seeded random order, hashed before the first rollout.
E25 placement (coordinator decision 2026-10-12): Suite D MERGES the decomposition into its window (`order.py --suite D ... --merge-decomp manifests/decomp_D.json`) so the P-only/T-only cells are interleaved with their champions and the seed; Suite E keeps E25 as a SEPARATE extra order run after E's main window (`order.py --suite E --extra decomp --decomp-manifest manifests/decomp_E.json`, then `run_final.py run --extra decomp`), so it can be cut first.  Cut order if time is short:
E25 first, then competitors, GEPA, 1S, CTL, nohist, ruleP; never PT, P, T or the seed (use `order.py --arms ...` to rebuild the order without the cut arms BEFORE the window starts; a started window is not reshuffled).
Dry run: dryrun/E (fake E30 root of links to E10C runs, Azure).

E25: `decompose.py --suite D --manifest manifests/artifacts_D.json --arms pt,rulep,1s,ctl` writes P-only / T-only sub-artifacts of each champion that differs from the seed on BOTH surfaces
(frozen read-only, hashed; a sub-artifact equal to the seed or the champion is skipped), then `order.py --suite D --extra decomp --decomp-manifest manifests/decomp_D.json` (n=3; B/C: `--suite B|C --arms oneshot`, n=1,
run last, dropped first) and `run_final.py run --extra decomp`.  Dry run: FE_D_RUNROOT points D at a fake E20 root of links to E10B runs.

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
  failure (worker crash without result) is `infra`, never a 0.  Missing cells have no row.  Amendment 5O: a cell still infra after 3 retries (`infra_final`) is scored 0 in `results_long.csv` (column `n_infra_final`, trial-level `infra_final`) and absent from `results_long_infra_missing.csv`; a 3 h hang that used its one retry is absent from both.  `rollout_log.csv` (every attempt: class, rule, hang, cell final status ok/retry_k_ok/infra_final/hang_retried/hang_missing/artifact_fail, timestamps, error text) and `infra_diagnostic.json` (per artifact, per arm and for the seed artifact in the same window: cells by final status, first-attempt infra rate and infra_final rate with Wilson 95% CI) are written next to it; retries depend only on the error class, never on a previous reward.  `results_long_first_attempt_infra_zero.csv` is the no-retry-credit sensitivity (a cell whose first attempt hit an infra error scores 0, so retries cannot hide candidate-induced errors); `infra_diagnostic.json` flags (`flagged_above_seed`) every artifact/arm whose first-attempt or final infra rate is >= 5% with a Wilson interval clearly above the seed artifact's in the same window.  `per_artifact_infra_rates.json` logs infra attempt and infra_final rates per (mode, arm, seed).
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

## v2 scoring window (amendment 11F; added 2026-10-13)

`v2_window.py build --suite A|D|E --champions champions_V2_<S>.json` freezes the v2 champions (hc2, ao2: final state of each search, read-only copy + tree hash under `final_eval/V2/<S>/artifacts/B/<arm>/s<k>`),
writes `manifests/artifacts_V2_<S>.json` (v2 entries + the v1 GEPA champions + the seed artifact, copied from `artifacts_<S>.json`) and `manifests/order_V2_<S>.jsonl(.sha256)` through `order.py`
(arms hc2, ao2, gepa, + seed and seed-check cells; tags `FINAL-<S>-V2-...`; held-out set only: A T = 70, D test-40, E test-20, the sel cells are dropped; trials as v1: A 1/2, D and E 5/10).
`v2_window.py register --suite S` appends the hashes (champions file, manifest, tree hashes, order, 11G comparison family, scripts, commit) to the registry; run `git fetch && git merge` first (the registry is shared).
Run: `run_final.py prepare|run --suite S --order manifests/order_V2_S.jsonl --root <FINAL_EVAL_ROOT>/V2/S --workers N` (same adapters, worker and scorer as the v1 windows).
Dry test (fake champions from v1 artifacts): order sizes A 840, D 2,400, E 1,200 jobs; `prepare` passes for all three.

## V3 final tests (added 2026-10-15; two benchmarks)

`v3_order.py` (collect / build, `--smoke` for a dry-run order on search-split tasks): B1 = tau2 airline (suite E worker; V3 adapter scripts/V3/adapters/airline sha 8d4cf8b7; agent, user simulator and judge
openai/aws/gpt-oss-120b via :4113; official 20 test ids; k = 10 trials per task for a champion cell; seed and seed-check cells; infra retries up to 30 per order (zero-error rule); a tool-consistency failure is a candidate fault,
reward 0, not retried), B2 = SpreadsheetBench (suite A worker, main's adapter with the helpers carrier like the v2 A window; `--taskset clean70|test280`; gateway `--sb-gateway`).
`collect` builds champions_V3_<B>.json from runs/V3/<B>/<framework>/s<k>/final/. Tags FINAL-E-V3B1-..., FINAL-A-V3B2-...; capped_stop 228000000; inert champions are mapped to the seed-check cell.
Dry run (fake champions, no scoring of test ids): B1 smoke order on 2 train tasks, 32/32 jobs done through :4113 with 0 errors; B2 clean70 (630 jobs with 2 fake frameworks) and test280 (2,520) preflight clean.
V3 HarnessLens (framework 'harnesslens' in B1): its champion is a VERSION of the OpenCode harness (`final/selected.json` selected_version, snapshot under rollout_evidence/v3-hl-s<k>/versions_percell/airline/<vN>), scored through bl-harness's `baselines/harnesslens/tau_v3/hl_final_eval_v3.py`
(the three pinned file shas are in the order meta and checked at preflight); an `hl-v0` baseline cell (unmodified OpenCode harness, n = seed-trials) is added; a harnesslens champion that kept v0 is mapped to it. The HL sandbox masks /tmp: the run root must be under campaign-scratch.
