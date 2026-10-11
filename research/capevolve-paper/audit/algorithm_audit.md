# CapEvolve algorithm and repository audit

Base SHA `e3cb513095604f87863c0e3df914ec47f16d0c9d` (campaign branch, equal to origin/main at audit time).
Method: source reading plus small local reproductions (no provider credentials, no benchmark runs). Every claim below
has a file:line; a "REPRO" tag means a script in `audit/repro/` reproduces it (`cd /tmp && python3.12 -I <script>`).
The prior literature review and the old `paper.tex` were treated as untrusted hypotheses and not relied on.

Paths are relative to the repo root. `core/cap_evolve/` is abbreviated `ce/`; `skills/algorithms/agent-optimize/scripts/` is `ao/`.

---------------------------------------------------------------------------------------------------------------------

## 0. One-paragraph summary

Both algorithms propose with an LLM coding agent and accept with a **paired one-SE heuristic or a conservative z-test on the
validation split — the same split the proposer reads traces from**. Train is not used by either algorithm for proposal or
selection; the only unadaptive data is the sealed test split, which is scored once **per run directory**, not per campaign.
hill-climb (as shipped by `cap-evolve run`) gates with `mean(Δ) > 1·SE(Δ)` over a **footprint-masked** delta vector (default
ON, no off switch exposed), with no regression veto. agent-optimize (the digest/act engine) promotes with
`objectives.decide_reward_gated` (a Bonferroni z-test with a hard-coded SE floor of 0.031), keeps a Beta-posterior rule only as
an advisory display and probe allocator (it is the accept rule only when `cost_gating` is switched OFF), and "confirms" the
champion on pooled (selection-era + fresh) trials before sealing. The bundled GEPA and SkillOpt are re-implementations with the
same significance gate bolted on, so they are not the official methods.

---------------------------------------------------------------------------------------------------------------------

## 1. CLI-to-evaluation path (what runs when you type `cap-evolve run`)

1. `ce/cli.py` (run command, ~L780-1075) loads `capevolve.yaml`, runs `check` (adapter contract) and `baseline`, then either
   - agent orchestration mode (`orchestration_mode: agent`): prints a handoff and returns, **no algorithm subprocess and no
     auto-finalize** (cli.py ~L910-930), unless `--agent-driver` is given, in which case `ao/host.py` drives a headless agent; or
   - deterministic mode: builds `alg_cmd` for `skills/algorithms/<alg>/scripts/run.py` with
     `--n-trials spec.num_trials(default 1) --gate-mode spec.gate_mode(default "auto") --k-se spec.gate_k_se(default 1.0)`
     (cli.py:950-957). `--protected-paths` is forwarded only if the spec lists `protected_paths` (cli.py:1029-1035).
     `--no-regression`, `--gate-max-broke` and `min_coverage` are **never forwarded** by the CLI.
2. Algorithm `run.py` (e.g. `hill-climb/scripts/run.py:104-136`) builds `gate_kwargs = {"k_se": k}` (mode left to the engine) and calls
   `harness.hill_climb_loop` (`ce/harness.py:4249`).
3. `hill_climb_loop` -> `run_step` (`ce/harness.py:2818`): copy parent -> inject context -> optimizer subprocess -> (optional integrity
   verify) -> `evaluate_candidate(split="val")` (`harness.py:283`) -> footprint -> `_paired_deltas` -> `gate.decide`
   (`ce/gate.py:215`) -> optional no-regression -> `snapshot` -> `set_best` on accept -> `record_iteration`.
4. After the algorithm exits, `cli.py` runs the `finalize` phase, which calls `harness.finalize` (`harness.py:4417`) and then `report`.
5. `harness.finalize` scores best **and** seed on test once (tags `FINAL`, `FINAL_seed`), also train+val bookends, writes
   `final.json`, then `commit_test()` flips `test_used` (`ce/rundir.py:471`).

Trial semantics: trial `k` uses seed `base_seed + k` with `base_seed = splits.seed` (`harness.py:338-352`, `trials.py`), so parent
and candidate share seeds at equal `k` (common random numbers). Errored trials (`Rollout.error` or `Score.raw["errored"]`) are
dropped from means (`harness.py:437-484`); tasks with 0 valid trials are excluded from every aggregate (`loop.py:aggregate_scores`).
Splits are a seeded shuffle with ratios 0.5/0.25/0.25, no stratification (`ce/splits.py:87-120`).

---------------------------------------------------------------------------------------------------------------------

## 2. hill-climb, precisely

| Item | What the code does | Evidence |
|---|---|---|
| Proposer | A coding-agent CLI subprocess (`optimizer_from_command`) with cwd = a copy of the parent in `run/work/<cid>`. No sandbox, full parent environment inherited. | `harness.py:935-971`; `skills/optimizers/run-optimizer/scripts/run.py:499` (cwd=workdir); `skills/optimizers/registry.yaml:92` (`claude -p ... --permission-mode acceptEdits --allowedTools Bash`) |
| Proposer input | Prompt rendered from the template with the parent's **val** per-task rows (always-failing / flaky / infra / solid), failure feedback, the parent's **val** trajectories copied verbatim to `./trajectories/`, capability guidance, `LEDGER.md` (framework-written broke/fixed lists per prior candidate, **val** ids), `JOURNAL.md`, rejected-edit memory. | `harness.py:3853` (`_focus_instructions`), `2454-2514` (`_inject_optimizer_context`, `split=eval_split="val"`), `2309` (`_copy_step_trajectories`), `hill_climb_loop` focus order built from `read_splits().val` (`harness.py:4313`) |
| Does the optimizer see val outcomes? | **Yes, per-task, per-trial, with full traces, every iteration.** It never sees test (not injected). It never sees train either: train is only evaluated by baseline and finalize bookends. | same; `hill-climb/SKILL.md` "All three index the val per-task results, because those are the only per-task data the loop holds" |
| Editable artifacts | Whatever files are in the capability dir (skills/tools/prompts); `--capabilities` merely adds guidance text. Edit scope is advisory except `tool_surface` policy (itself fail-open, #352). | `harness.py:2454`; `ce/tool_surface.py` |
| Action decision | One agent call = one candidate per iteration (a "bundle" of edits). No explicit action menu. | `run_step` |
| Parent selection | Always the current best (`run_dir.best_id`). `--focus all/cyclic/hardest-first` only changes which val failures are emphasized in the prompt. | `harness.py:4333` |
| Eval cache | None in hill-climb (`EvalCache` is GEPA-only, `cache.py` docstring). Per-tag rollout files `<task>__<tag>__t<k>.json`. The evidence ledger (`eval_index.jsonl`, keyed by `cap_hash` + `env_fp`, `eval_index.py`) is written by the evaluate phase and used for seed offsets (`harness.py:345-352`) and by agent-optimize; not consulted by the hill-climb gate. | `cache.py:1-30`, `eval_index.py` |
| Screening | None (every candidate pays full val x n_trials). | `run_step` |
| Gate (default) | `mode="paired"` iff a paired delta vector exists. Accept iff `mean(Δ) > k_se·SE(Δ)`, `SE = sd(Δ)/sqrt(n)` over shared valid val tasks, `k_se=1.0`. If `SE==0` (e.g. `n_trials=1` and all deltas equal, or n=1): "STRICT fallback" `mean>0`, with a `gate_warning` event. | `gate.py:422-459`; `harness.py:3005-3006, 3019-3024` |
| Footprint (default ON) | `run_step(footprint_gate=True)`; no CLI/spec switch to turn it off (grep: only `gate_check.py --no-footprint`). Tasks outside the footprint enter the delta vector as exact 0.0; vector keeps length n. For a restricted vector, `paired_se_floor = sqrt(Σ_footprint (σp²+σc²))/n` lower-bounds the SE (inactive at `n_trials=1` because per-task stderr is 0). | `harness.py:2837, 2984-3003, 1024-1070, 1421-1445`; `footprint.py` |
| Footprint derivation | Regex "named surfaces" (`def`/`class`/`call(`/`"name": "x"`) on the changed `+/-` lines plus the enclosing definition; a task is "in" if any symbol appears as a substring anywhere in the serialized rollout of parent **or** candidate; if any symbol hits >= 80% of tasks the whole footprint is abandoned (returns `None`); also `None` if no symbols, > 40 symbols, no rollouts, or footprint == all tasks. Prose-only edits (policy text, prompt wording) name no surface and therefore yield no symbols unless a `def`/call/`"name":` line is also in the diff. | `footprint.py:115-178 (_UBIQUITOUS_FRACTION, touched_symbols), 180-231 (in_footprint_tasks), 233-261 (footprint)` |
| Coverage / invalid rollouts | `decide(coverage=cand_val.coverage)`: `n_scored/n_tasks` of the **candidate only**; `min_coverage=0.6` default, **not configurable from CLI or spec**. Below it: `indecisive` (no accept, no stall tick). The parent's coverage is not checked, nor the joint (paired) coverage. Errored trials are dropped, so a task the candidate crashes on is removed from the pair. | `gate.py:397-406`; `harness.py:3019-3024`; `loop.py:has_valid_trials`, `SplitResult.coverage`; `_paired_deltas` `harness.py:1058-1064`. REPRO r2 |
| Regression veto | `--no-regression` (default False, not forwarded by `cap-evolve run`): reject if any shared task dropped by more than `2·SE` of its own pair. `--gate-max-broke` (default None, not forwarded). Composition (`broke`/`fixed`) is recorded over the full split but is descriptive only. | `harness.py:3028-3056`; `gate.py:282-294`; `cli.py` (no forwarding) |
| Other gate modes | `significant` (unpaired `Δ > k·sqrt(se_c²+se_p²)`), `threshold`, `strict`, `pareto`, `epsilon_constraint` (hill-climb only wires `--objectives`), `reward_gated`. Non-default. | `gate.py:461-595` |
| Incumbent update | On accept: `run_dir.set_best(cid)` and `current_val := candidate's own measured val SplitResult` (a single noisy measurement of the winner). The next candidate is compared against that stored measurement. | `harness.py:3069`, `4358-4359` |
| Stopping | `RunDir.budget_exhausted`: `max_iterations` (spec `max_iterations`, default 10 in the CLI path; `Budget` default 20), `max_metric_calls`, `max_usd`, `max_optimizer_usd`, `stall`, `stop_at_reward` (compared to **best val**, i.e. selection-biased), optional `--convergence` plateau signal (off by default). | `rundir.py:368-383`; `cli.py:953`; `hill-climb/scripts/run.py` |
| Finalization | `finalize` phase after the loop: best and seed on test once (n_trials from spec), train/val bookends, `final.json`, seal burned. **No confirmation stage**: best was selected on val and test is the first fresh look. | `harness.py:4417-4497` |

### 2.1 Defaults vs experimental switches vs documented-only (hill-climb)

- **Default ON:** paired gate, k_se=1.0, footprint masking, `paired_se_floor` (when restricted), coverage guard at 0.6, errored-trial dropping,
  common-random-number seeds, broke/fixed recording, git store.
- **Opt-in:** `--no-regression`, `--gate-max-broke`, `--protected-paths` (the seal; **OFF** unless spec lists it; the shipped template has it commented
  out, `templates/project/capevolve.yaml:130-131`; benchmark CI sets it only for the tau2 blackbox arm, `ci/benchmarks/lib/run_suite.sh:498`),
  `--convergence`, `--n-trials > 1`, `--workers > 1`, non-paired modes.
- **Documented but not enforced:** "optimizer cannot touch the scorer" (see section 5); `hill-climb/SKILL.md` "Known gate edge case (open, issue #351)"
  — #351 is **closed** on GitHub but still reproduces at this SHA (n=20 accept, n=30 reject, n=40 accept for a one-task gain; see D14).
  `SKILL.md` line references (`harness.py:1409`, `1524-1532`, ...) point at code that moved (run_step is now at 2818).

---------------------------------------------------------------------------------------------------------------------

## 3. agent-optimize, precisely (digest/act engine)

The "algorithm" is mostly prose in `SKILL.md` executed by a conversational agent; scripts enforce a subset. Verbs: `propose`, `probe`,
`promote`, `prune`, `merge`, `finalize` (`ao/act.py`), plus `digest.py` (state summary), `commit.py` (booking), `gate_check.py`, `pregate.py`.

| Item | What the code does | Evidence |
|---|---|---|
| Proposer | The driving agent itself (an interactive agent, or `host.py` launching `claude -p ... --allowedTools Bash` etc.). It edits `run/work/<TAG>` with arbitrary tools. It also chooses hypotheses, probes, promotes and prunes. | `SKILL.md`; `ao/host.py:1-80`; `registry.yaml:92` |
| Proposer input | `digest.py` one-screen state (budget, noise sd from repeat cells, failure clusters from `diagnose --split val --cluster v2`, branch-tip posterior, merge opportunities, pregate warnings, suggestions); plus raw **val** exemplar traces it reads itself ("never test" is a prose rule); plus PROJECT.md, adapter, capability files. | `SKILL.md` steps 1-2, `ao/digest.py:1-40`; `SKILL.md:53` (`--split val`) |
| Does the optimizer see val outcomes? | **Yes.** Everything it learns from is val: clusters, per-task rates, posterior, exemplar traces. Train is not used. Test is excluded only by prose and by `probe_ids` refusing ids not in val (`act.py:256-262`). | same |
| Editable artifacts | Any file under the capability path, composite tools included; `pregate` checks tool compilation, "hidden writes" call-graph, policy growth. No protected-path/integrity check exists in agent-optimize (grep `protected|integrity` in `ao/*.py` returns nothing) although SKILL.md says "Core enforces ... the tamper guard". | `ao/pregate.py:1-40`; `SKILL.md` Invariants |
| Action decisions | Verbs. `propose` (2-call protocol: copy parent -> edit -> hypothesis rule + pregate + record node), `probe` (evaluate missing ledger cells), `promote` (full-val coverage needed, then judge vs champion), `prune` (commit reject, `driver_judgement`), `merge` (N-way fold). Hypothesis rule: >= 2 tasks or headroom >= 0.06, `hypotheses.validate`; checked only if `failure_clustering` on and `clusters.json` exists (else warn + continue). | `act.py:183-244, 329-380, 417-469, 474-509`; `ce/hypotheses.py` |
| Parent selection | The agent passes `--parent` freely (DAG); `dag_parallel` off forces `best_id`. Merge candidates come from digest `merge_opps` (complementarity > 0.5). | `act.py:188-191`; `digest.py:COMPLEMENTARY` |
| Cache keys | Ledger row = `(cap_hash, split, task, trial_idx, tag, k, env_fp)`; `cap_hash` = SHA-256 of capability bytes excluding scratch files (`cache.hash_candidate_dir`); `env_fp` = env var `CAPEVOLVE_ENV_FP`, **empty by default**, so model, adapter, scorer and benchmark version are not in the key. Errored rollouts are not indexed. `claim_cells` serializes concurrent probes of the same `(cap_hash, task)`. | `eval_index.py:49-125`; `act.py:286-326` |
| Screening / allocation | With `active_eval` ON: `sched.pick` posterior allocator (greedy variance reduction); with it OFF (stock default, `optimizer_config.py:34`): `probe --auto` runs **full val** (needs `--yes`). Legacy `screen.py` is a subset kill-only triage (tier 1 ~25% / tier 2 ~50% of val, 1 trial). | `act.py:256-270`; `sched.py`; `ao/screen.py:1-40` |
| Gate rule used at promote | `judge()` (`act.py:388`): `cost_gating` ON (default) -> `gate_check --mode reward_gated` -> `objectives.decide_reward_gated`. `cost_gating` OFF -> the posterior rule. In both, `P.verdict` p_beat is computed and shown. Footprint is **not** applied in the reward_gated path (task_records only, `gate.py:408-420`); `gate_check` still computes it for display. | `act.py:388-408`; `gate_check.py:225-285`; `gate.py:408-420` |
| reward_gated rule | Stage 1: `dR` = mean over parent-tasks of (cand task mean - parent task mean) with missing candidate task = 0; `se = max(sd_tasks/sqrt(n), 0.031)`; reject if `(dR+0.03)/se <= -z(0.8)`; indecisive if `< z(0.8)=0.84`; stage 2 (matched-success cost): accept if `dR/se > z_accept = 2.734` (Bonferroni `0.05/(2*8)`) and matched cost within +5%, cost-per-success non-inferior, matched vs strict cost sign agrees; or a cost-win branch. `NOISE_FLOOR=0.031` is a constant measured on one run (`run_20261008_150326`). `looks=8` is a config number; **no counter limits re-evaluations** of a candidate and there is no multiplicity control across candidates. | `objectives.py:41-100, 166-176, 302-380` |
| Posterior rule (`posterior.py`) | Per task: parent rate `p ~ Beta(.5+s, .5+n-s)` clipped to [.01,.99] from the pooled ledger; candidate rate `q|p ~ Beta(k p, k(1-p))` updated with the candidate's trials; `k=3` for flaky/failing tasks, `k=6` for parent-stable (>=0.85) "canaries". `D = mean_i(q_i-p_i)` over **all frozen val tasks** (unobserved tasks contribute prior mean 0 and extra variance). Accept iff `P(D>0.02) >= 0.95` and every parent-stable task has >= 3 candidate trials; prune if `P<=0.10` (0.25 after 100 rollouts) once 40 rollouts are used; a canary collapse (flat-prior P(q < p-0.3) > 0.9) prunes. M=400 draws seeded `Random(0)`. Used for: display, `probe --auto` allocation, and as the accept rule only when `cost_gating` is OFF. | `posterior.py:15-100`; `act.py:395-408` |
| Incumbent update | `commit.py --decision accept` -> `run_dir.set_best(tag, val=measured)` (`commit.py:868`). `promote` is the only caller that couples accept to a gate verdict; `commit.py` itself performs **no** gate check for accept (only checks `--val` equals the measured mean). | `act.py:433-438`; `commit.py:638, 868` |
| Stopping | Budget (`budget_exhausted`; spending verbs refuse unless `--over-budget REASON`), goal met, or `stop_condition` parsed by `spend.py`; the new engine has no stall rule (`act.py:461-462`). | `act.py:120-131`; `spend.py` |
| Finalization / confirmation | `act.py finalize`: if the champion is not the seed and `--n-confirm > 0` (default 3): top up the champion's **same tag** on full val by `n_confirm` extra trials per task (fresh seeds via ledger offset), then `judge(champion, "seed")`. If the verdict is not `accept`, refuses to seal unless `--seal-anyway REASON`. Then runs the finalize phase (test once, best + seed). | `act.py:514-548` |
| Is confirmation fresh-only? | **No.** `gate_check` loads *all* rollouts of the champion tag (`objectives.load_trials(run_dir, tag)`, `gate_check.py:260-263`, `objectives.py:113-136`), i.e. selection-era trials plus the 3 new ones, and compares against the seed's baseline val rollouts. The confirmation gate therefore re-uses the evidence that drove the promote (pooled), so winner's-curse bias is diluted, not removed. The digest's `p_beat` additionally pools by `cap_hash` across tags (ledger), a different pool than the gate's tag-scoped pool. | same; `eval_index.counts` |

### 3.1 Defaults vs experimental vs documented-only (agent-optimize)

`optimizer_config.DEFAULTS` (`ce/optimizer_config.py:34`): `dag_parallel=True, active_eval=False, smart_merge=True, cost_gating=True,
failure_clustering=True, pregate=True, context_digest=True`. `SKILL.md` says the loop "REQUIRES the new engine" (`dag_parallel` AND
`active_eval`) and tells the operator to switch `active_eval` on; with stock defaults `new_engine()` is False and `probe --auto` silently runs full val.
A paper must therefore state the exact ablation configuration; "agent-optimize" is not one configuration.

- **Enforced in code:** hypothesis size rule (if clusters exist), pregate (compile / hidden-write / policy growth), budget refusal, test never probed,
  one finalize per run dir, accept-through-promote requires full-val ledger coverage and a gate verdict, `finalize` confirm gate.
- **Procedural only (prose):** "never view test traces", "never hand a subset result to gate_check", journal entries, big-coherent-edit guidance,
  the tamper guard for agent-optimize.
- **Experimental:** posterior-as-accept-rule (`cost_gating` off), `active_eval`, `smart_merge` interaction scores ("weights are guesses, not fitted",
  `merge_n.py` docstring), reward_gated cost objectives, `pareto`/`epsilon_constraint` modes.

---------------------------------------------------------------------------------------------------------------------

## 4. The audit targets, verified

### 4.1 Causal-footprint masking (REPRO r1) — CONFIRMED, default ON
- Mechanism: `harness._paired_deltas(..., footprint=fp)` replaces every out-of-footprint paired delta with `0.0` (`harness.py:1067-1070`); `run_step` builds
  `fp` from the candidate's own val rollouts and diff (`2989-2998`) and `footprint_gate=True` is the default (`2837`); nothing in `cli.py`, `hill-climb/scripts/run.py`,
  `skillopt` or `gepa` run scripts can switch it off. GEPA's `_full_val_gate` does not use it (`gepa.py:772`). `gate_check.py` (agent-optimize `--mode paired`, legacy rounds)
  uses it unless `--no-footprint`; the new-engine `promote` (reward_gated) ignores it.
- Failure demonstrated: a candidate whose diff contains a tool change (`def refund_order`) plus a prose rule that breaks 6 unrelated tasks has full-vector
  `Δ̄ = -0.067` (reject) but footprint-masked `Δ̄ = +0.133 > 1·SE=0.063` (accept), while the stored candidate `val` mean is *lower* than the parent's.
  Cause: the footprint is built from named code surfaces only, so any behaviour change carried by prose is invisible to it; the module's safety rule
  ("never under-include") is a heuristic about rollout substrings, not a guarantee. `gate_max_broke` would catch it but is off and not forwarded.
- Selection effect: the footprint is chosen *after* the candidate's val rollouts exist (it greps them), so the test set of tasks that count is chosen with
  the outcomes' traces in hand. It does not read rewards, which limits but does not remove the dependence.
- Scale: `Δ̄` is divided by the full n, so masking shrinks both `Δ̄` and `SE` (a footprint of m of n tasks scales both by about m/n); the accept condition is still
  `Δ̄ > 1·SE`, i.e. it becomes a test on the in-footprint tasks only. It is a *different statistic* from the one hill-climb docs and `val` curves report.

### 4.2 `min_coverage` and invalid rollouts (REPRO r2) — CONFIRMED, partial
- `decide(min_coverage=0.6)` (`gate.py:228, 397-406`); hard-coded at the call sites (no CLI/spec key; `grep min_coverage` shows only gate/objectives and a comment).
- Coverage is `n_scored/n_tasks` for the **candidate alone** in `run_step` (`harness.py:3022`) and `min(candidate, reference)` of each side's *marginal* coverage vs the frozen
  split in `gate_check` (`gate_check.py:239-247`) — never the joint (paired) coverage. r2: both marginals 0.70, joint paired n = 12/30 = 0.40, gate not indecisive.
- Errored trials (infra *or* an exception inside the candidate's code running in the adapter, since `trials.py:run_trials_pool` converts any exception to an error rollout) are
  removed from the mean and from the pair. r2: a candidate that crashes on 6 tasks the parent passes is accepted (`Δ̄=+0.167 > 1·SE=0.078`, paired n=24, val 0.733 -> 0.833).
  Adapter contract (`adapter.py:94`) tells authors to set `Rollout.error` for *infrastructure* failures only; nothing audits that.
- The reward_gated path does the opposite: `load_trials` keeps errored trials as reward 0 (`objectives.py:113-136`; its own docstring contradicts itself), while the ledger and `evaluate_candidate`
  drop them. Digest `p_beat` (ledger) and `promote` (rollouts) therefore see different evidence.

### 4.3 The one-SE heuristic (REPRO r3) — CONFIRMED
- Rule `mean(Δ) > 1.0·SE(Δ)` is a one-sided z-test at alpha ≈ 0.159. Simulation (null candidate = same true per-task rates, heterogeneous task difficulty):
  single-test accept rate 0.15-0.17 for T in {30,60,140} and 1-5 trials; over 10 sequential null candidates in a hill-climb (parent replaced on accept) the chance of at least one false
  accept is 0.51-0.58 (mean 0.54-0.63 accepts per 10 iterations). Gate docs call it what "makes an accept mean something"; `act.judge`'s docstring cites a measured 39% cumulative
  false-accept for this gate over 8 looks, consistent with this.
- Edge: one-task gains have `Δ̄ == SE` algebraically and resolve by float error (n=20 accept, n=30 reject, n=40 accept; #351 is closed but reproduces).
- With `n_trials=1` (spec default) per-task stderr is 0, `paired_se_floor` is 0, and the gate relies only on cross-task spread.

### 4.4 Posterior assumptions (REPRO r4) — mostly sound on the null, but narrowly scoped
- Priors: Beta(.5,.5) on the parent rate; `q|p` centred at `p` with strength 3 or 6 (a null-centred, regularising prior); unobserved tasks stay at prior (zero mean, extra variance);
  accept threshold 0.95 on `P(D > 0.02)`; canary cover >= 3 trials; M=400 draws with a fixed seed (the draws are identical on every call, so the verdict is a deterministic function of the counts).
- Claims: `posterior.py` docstring "Sequential paired posterior decision rule"; `act.judge` docstring "validated under repeated looks" (`posterior.py` + `research/design/sim_eval.py`).
  Local check (T=30/60, parent 1 or 3 trials, 8 looks at n=1..8 trials of full coverage, 250 sims each): false-accept 1.6%-2.4% on the null, 3.6% with zero-mean heterogeneous trades
  (CI about ±1.7 pp). So the sequential-validity *claim* is supported for a **fixed, unadaptive** pair on a fixed val set.
- Not covered by any guarantee: (i) `D` is the mean difference over *these* val tasks (finite population), so it says nothing about generalization and it is conditioned on tasks the proposer has
  studied; (ii) multiple candidates/merges (the family-wise rate across a run); (iii) hand-set constants (`K_IMPACT=3`, `K_CANARY=6`, `STABLE=.85`, `DMIN=.02`, etc.); (iv) it is **not the default accept rule** (reward_gated is).
  Docs/comments that say "sequentially valid" apply to a single candidate re-evaluated up to `looks`/many times, not to the search.

### 4.5 Test seal: per run, not per campaign — CONFIRMED
- `Splits.test_used` lives in `splits.json` of **one run dir** (`splits.py:26-60`, `rundir.py:428-477`). `harness.reuse_baseline` copies the prior run's frozen split and **resets `test_used`**
  (`harness.py:861-933`), and carries the seed's *test result* across runs. `make_splits(seed)` is deterministic, so two runs with the same seed score the same held-out tasks. A campaign that compares
  many arms/configurations/seeds on one test split, then selects or reports the best, consumes the test set repeatedly; the framework has no cross-run ledger and no warning.
- `begin_test_attempt` refuses a second look inside a run unless `CAPEVOLVE_ALLOW_TEST_RESCORE=1` (`rundir.py:441-469`). `evaluate_candidate(split="test")` is callable outside `finalize` (open #361).
- agent-optimize adds a confirm-before-seal step but then still seals test per run.

### 4.6 `protected_patterns` and optimizer isolation (REPRO r6) — NOT isolated
- `integrity.DEFAULT_PATTERNS` = `*gold*, *answer*key*, tasks/*, data/*, tests/*, conftest.py, */conftest.py, scorer.py, */scorer.py, adapter.py, */adapter.py, splits.json` (`integrity.py:60-73`).
  The patterns apply to the **candidate workdir** only: `snapshot(workdir, patterns)` is taken after context injection, `set_readonly` clears write bits (best effort), and `verify` runs before evaluation (`harness.py:2885-2925`).
  The adapter and scorer live in the *project* directory, outside the workdir, so a default `DEFAULT_PATTERNS` seal hashes nothing relevant (r6: manifest has no files), and an optimizer subprocess rewriting
  `project/scorer.py` leaves `verify().ok == True`.
- The seal is OFF unless `protected_paths` is set (`cli.py:1029-1035`, `templates/project/capevolve.yaml:130`), and `gepa`, `skillopt`, `hill-climb` are the only wired algorithms; **agent-optimize has none**.
- The optimizer is an unsandboxed subprocess inheriting `os.environ` (including provider keys; `harness.py:947`), with cwd = workdir, and the registry grants Bash (`claude -p ... --allowedTools Bash`,
  `codex exec --sandbox workspace-write`, `opencode run --dangerously-skip-permissions`, `bob --yolo`; `registry.yaml:92,113,135,155`). The Claude plugin hook `deny_sealed_edits.py` matches only `Edit|Write|MultiEdit|NotebookEdit`
  (`plugins/cap-evolve/hooks/hooks.json`), so shell writes and reads (`cat splits.json`, reading test tasks through the adapter or the `--bench-repo`) are not blocked.
- Existing issues: #276 (open), #365 (meta, open), #142 (closed). Not re-drafted.

### 4.7 `combined_stderr` (REPRO r7) — definition and bias
- `stats.combined_stderr` = `sqrt( var_between(task means)/n + Σ se_i² / n² )` (`stats.py:42-60`). The first term already contains within-task trial noise (`E[var of task means] = var(p) + E[σ²/n_trials]`), so the second term double counts it
  for `n_trials > 1`; for `n_trials=1` the within term is 0. For a *fixed* val set re-measured, true sd of the val mean was 0.054 / 0.034 / 0.027 / 0.019 at 1/3/5/10 trials while `combined_stderr` was 0.080 / 0.069 / 0.065 / 0.057 (1.5x-3.0x too large and
  essentially flat in trials). It is a population-of-tasks SE that cannot shrink below the between-task term.
- Where used: `SplitResult.stderr` (reported "val ± se", final.json), `significant` mode, pareto fallback, `convergence`. Not used by the default paired gate.

### 4.8 Fresh-trial confirmation in agent-optimize `act.py` — see section 3 ("Is confirmation fresh-only?"): NOT fresh-only, pooled with selection-era trials and compared with the seed's baseline val rollouts.

---------------------------------------------------------------------------------------------------------------------

## 5. Bundled GEPA and SkillOpt vs the official methods (brief)

### GEPA (`ce/gepa.py`; official: arXiv 2507.19457, `gepa-ai/gepa`, `src/gepa/core/engine.py`)
Matches: reflective mutation on a train minibatch, strict `new_sum > old_sum` minibatch acceptance, per-instance Pareto frontier with frequency-weighted parent sampling, round-robin component selection, scheduled merge, metric-call budget, eval cache.
Deviations (cite `gepa.py`):
1. **Extra acceptance gate.** After the minibatch test the official engine evaluates the proposal on the full valset *unconditionally* and adds it to the pool (the best program is chosen by val aggregate). Here a candidate must also pass the paired one-SE significance gate (`_full_val_gate`, `gepa.py:756-820`) to join the pool/frontier, so the frontier contains only gate-accepted candidates and rejected-but-diverse programs never become parents. The bundled variant is a different search.
2. **Proposer.** Official: an LLM call with a reflection prompt rewrites one text component. Here: a coding-agent CLI with Bash edits files in a work directory (`REFLECTION.md`, `FOCUS.md`); component discipline is advisory (`component_selector=round_robin` is text in the prompt).
3. **Minibatch economics.** Default `minibatch_size=4` (official default 3); one trial per task with a **fixed seed** (`_eval_minibatch(..., seed=seed)`), and the cache key is `(cap_hash, task_id)` only (`cache.py`) so a repeated candidate replays one stochastic draw forever and the cache ignores model, seed, scorer/adapter version.
4. **Gate details.** `_paired_deltas` without footprint (`gepa.py:772`); default `k_se=1.0`; `n_trials=1` default.
5. Official uses the valset only for scoring/selection and the trainset for reflection; here the same split discipline holds (minibatch from train, gate on val) — this is the one place the bundled GEPA does *not* feed val traces to the proposer (`ctx.inject(split="train")`, `gepa.py:597`).
6. Budget: `max_metric_calls` is primary only if set (default 0 = unlimited, then `max_iterations=50`).
Open issues touching it: #376 (trajectory tag stops resolving from iteration 2), #638.

### SkillOpt (`ce/skillopt.py`; official: `microsoft/SkillOpt`, arXiv 2605.23904)
The official README states: bounded add/delete/replace edits with a textual learning-rate budget, a rejected-edit buffer, an epoch-wise slow/meta update, and acceptance "only when [a candidate] strictly improves a held-out validation score". Defaults beyond that are not documented in the README, so a line-by-line parameter comparison is **not possible from the public text** (could not verify).
Deviations observable in the bundled code:
1. Acceptance is the paired one-SE gate (via `harness.run_step`, footprint ON), not a strict improvement.
2. The mini-batch is cosmetic: every step evaluates the **full val split**; the train mini-batch ids are passed as `focus_ids` and filtered against val rows, so the focus block is empty (`skillopt.py:297-310`; open #371). The proposer reads val trajectories through `run_step`.
3. The edit budget `L` is advisory text; nothing enforces it (open #382); `applied_changes` counts injected context (open #395).
4. Slow update is a gated extra step on a sampled train subset comparison; the official slow-update details are not specified in the README.

---------------------------------------------------------------------------------------------------------------------

## 6. Test-suite health (CONTRIBUTING.md: `python -m pytest core/tests -q`)

Environment: Python 3.12.15, pytest in `/tmp/auditvenv`, `PYTHONPATH=core CAPEVOLVE_CORE=core`. Result at base SHA:
**2199 passed, 1 failed, 16 skipped in 444.6 s** (`audit/repro/pytest_core_base_e3cb513.txt`).
- The one failure: `core/tests/test_spreadsheetbench_verify_turns.py::test_a_correction_supersedes_the_earlier_answer` (`assert 'SOLVE_V1' == 'SOLVE_V2'`), deterministic (reproduces in isolation); an adapter test, unrelated to the gate/seal logic.
- Without `pip install -e ./core` (or `PYTHONPATH`/`CAPEVOLVE_CORE`), subprocess-based tests such as `test_eventstream.py::test_tail_is_a_registered_subcommand` fail with `No module named 'cap_evolve'`; that is an environment requirement, not a defect.
- Coverage note: tests exist for the footprint safety rules, the coverage guard, `reward_gated`, and the posterior rule; none exercises the failures reproduced in section 4 (prose edit hidden from footprint, joint coverage, pooled confirmation).

---------------------------------------------------------------------------------------------------------------------

## 7. What could not be verified

- Real-run behaviour (no benchmarks, no provider calls): the rate at which real candidate edits are "prose-only" and thus bypass the footprint, how often adapters mislabel candidate exceptions as infra errors, and the realised false-accept rate under real, non-null task-effect structure.
- The 39% figure and the design sims in `research/design/sim_eval.py` (cited by comments) were not re-run; my posterior and one-SE simulations are independent and use an iid-Bernoulli task model with Beta(.7,.7) difficulties, which is only a model.
- Official SkillOpt internals beyond the README (parameters, slow-update rule); official GEPA `reflective_mutation` prompt details beyond `engine.py`.
- Whether adapter `Score.feedback` strings leak gold answers to the proposer (adapter-specific; the framework copies full rollouts including `score.feedback` into `./trajectories/`).
- Whether any benchmark CI arm turns `active_eval` / `protected_paths` on beyond what `ci/benchmarks/lib/run_suite.sh` shows; I only grepped that script.
- The `--bench-repo` content: it is passed as read-only optimizer context (`cli.py` (--bench-repo forwarding, ~L1000-1010)), and the claim "read-only" is only a prompt statement; I did not check whether test gold is reachable from it for each benchmark.
