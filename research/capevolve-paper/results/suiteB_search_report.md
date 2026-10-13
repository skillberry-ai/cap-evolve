# Suite B (tau2 retail) search report

**Search-time; not held-out.** Every "sel" number in this file is a search-time or post-hoc selection-split number. None is a result. The sealed test-40 was never touched by the Suite B runner; final test scoring belongs to final-eval-eng.

Written 2026-10-13 by tau-runner. Sources: `runs/E10B/E10B_results.{json,txt}`, per-run `cost_summary.json`, the gateway log by tag (`tag:E10B-<arm>-s<k>`), `decisions.md`.

Setup: target and user simulator `rits/openai/gpt-oss-120b-a100`, judge `azure/gpt-5.5`, optimizer `aws/claude-sonnet-5-5`. Split: opt-49 / sel-25 (seed 42), official test-40 sealed.

## 1. Results (selected artifact)

`sel (search)` is the search-time selection-split score of the champion. `post_sel` is a post-hoc re-score on sel (2 trials, fresh seed 9000+k, tag `chaser`, outside the budget; 0 missing in every run).

| arm | seed | selected | counted search rollouts | sel (search) | post_sel |
|---|---|---|---|---|---|
| hc (rule P) | 0 | seed | 637 (+25 FINAL) | 0.52 | 0.64 |
| hc | 1 | seed | 564 | 0.60 | 0.56 |
| hc | 2 | seed | 637 (+25 FINAL) | 0.60 | 0.58 |
| ao (new engine, rule P) | 0 | seed | 148 (+50 finalize) | 0.625 | 0.60 |
| ao | 1 | seed | 147 (+50 finalize) | 0.68 | 0.58 |
| ao | 2 | seed | state 907 at cutoff (882 at final-eval-eng's 06:00 snapshot; bstar.py's search-only count is theirs) | finalize 0.48 (earlier completed FINAL on 2026-10-11: 0.56; reporting rule is final-eval-eng's) | 0.58 |
| gepa 0.1.4 (policy addendum) | 0 | best_idx 7 | 613 (GEPA metric calls 611) | 0.76 | 0.60 |
| gepa | 1 | best_idx 7 | 603 (602) | 0.76 | 0.60 |
| gepa | 2 | best_idx 11 = cand_0031 (reconstructed host-side) | 607 (599) | 0.76 | 0.78 |
| ctl-oneshot | 0 | cand_0001 | 123 | 0.56 (seed 0.56) | 0.36 |
| ctl-oneshot | 1 | cand_0001 | 148 | 0.625 (seed 0.48) | 0.56 |
| ctl-oneshot | 2 | cand_0001 | 123 | 0.56 | 0.62 |
| ctl-seed (unoptimized) | 0/1/2 | seed | - | opt 0.561 / 0.602 / 0.653; sel 0.60 / 0.58 / 0.62 | - |

HarnessLens (bl-harness's arm; all four arms v0 per the lead): rollout counters 176 / 173 / 163 (baseline trials 98 plus rollout jobs 64 / 63 / 52); optimizer non-cache tokens 4,196,869 / 4,000,895 / 4,044,828. No sel or post_sel score is reported here. HarnessLens extended s0 (exploratory): 284 rollouts, 10.05M optimizer tokens, stopped at the cutoff (06:03:46Z).

Outcome of the searches: every hill-climb and AO seed ended with the seed as champion (no accepted candidate). GEPA is the only arm that changed the artifact in all three seeds. The ctl-oneshot proposal was accepted only in s1 (opt-val 0.714).

## 2. Per-candidate scores (search time)

hc and ctl-oneshot: opt-val on the 49 opt tasks. gepa: GEPA valset aggregate on sel-25 (selection-biased).

- hc s0: cand_0001 0.592 (rejected), cand_0002 0.617 (rejected by rule P: fresh +0.048, z 1.04 < 1.282). cand_0003 straddled the cap (cap_truncated, no verdict). Baseline opt-val 0.531.
- hc s1: ten candidates 0.714, 0.562, 0.592, 0.633, 0.625, 0.612, 0.551, 0.653, 0.612, 0.592; none accepted. Baseline 0.653.
- hc s2: cand_0001 0.633 (rejected, fresh +0.014, z 0.35), cand_0002 0.571. cand_0003 cap_truncated. Baseline 0.542.
- ao: s0 cand_5 and cand_6 (no scores recorded, none accepted); s1 cand_b (none accepted); s2 none accepted (in-flight cand_4 gate eval cap_truncated at the cutoff). Baseline opt-val 0.604 / 0.612 / 0.612.
- gepa valset aggregates (14 programs each):
  - s0 `[0.60, 0.56, 0.72, 0.48, 0.64, 0.44, 0.64, 0.76, 0.68, 0.72, 0.56, 0.60, 0.60, 0.56]`
  - s1 `[0.40, 0.40, 0.52, 0.60, 0.60, 0.64, 0.68, 0.76, 0.52, 0.56, 0.56, 0.44, 0.52, 0.56]`
  - s2 `[0.60, 0.48, 0.52, 0.60, 0.72, 0.60, 0.64, 0.60, 0.68, 0.68, 0.68, 0.76, 0.68, 0.56]`; the next program, cand_0036, never got a full-sel evaluation (cap_truncated).
- ctl-oneshot cand_0001 opt-val: 0.488 / 0.714 / 0.633.

## 3. Costs (millions of tokens, gateway log by tag)

Optimizer or reflection column is non-cache-read tokens, from `cost_summary.json` where it exists.

| run | target | user | judge | optimizer / reflection |
|---|---|---|---|---|
| hc s0 | 66.0 | 8.0 | 1.5 | 0.49 (log) |
| hc s1 | 50.6 | 6.4 | 1.2 | 0.81 |
| hc s2 | 66.5 | 8.9 | 1.4 | 0.34 (log) |
| ao s0 | 27.4 | 3.3 | 0.6 | 1.15 |
| ao s1 | 27.9 | 3.1 | 0.5 | 0.98 |
| ao s2 | 119.3 | 12.9 | 2.5 | 2.67 |
| gepa s0 | 66.8 | 6.0 | 1.1 | 1.05 |
| gepa s1 | 61.1 | 6.0 | 1.1 | 1.04 |
| gepa s2 | 58.7 | 5.8 | 1.1 | 0.93 |
| ctl-oneshot s0 / s1 / s2 | 19.4 / 17.6 / 15.9 | 2.1 / 2.0 / 1.8 | 0.4 | 0.29 / 0.31 / 0.23 |
| ctl-seed s0-s2 | 14.6 to 15.3 | 2.0 | 0.4 | 0 |
| HarnessLens s0-s2 | 27.9 to 31.0 | 4.1 to 5.2 (usersim) | - | 4.20 / 4.00 / 4.04 |

Post-hoc scoring (chasers) used 2.7 to 11.8M target tokens per run. The optimizer guard (4M, current attempt) held for every matched arm except HarnessLens s0 (4.20M, registered overshoot: the guard is checked only at session reservation). hc s0 and s2 have no `cost_summary.json` because their drivers were killed; their numbers come from the gateway log. USD is not computed (RITS and Azure tokens are unpriced in the ledger).

## 4. Deviations and incidents

All are recorded in `decisions.md`.

- Judge is `azure/gpt-5.5`, not gpt-oss. Hung-rollout rule: 3 h and one retry; simulator timeout 7200 s on the v2 config.
- HarnessLens: 3.5 h per-trial wall cap, prefix-defect archive and refund, s0 token-guard overshoot (4,196,869 vs 4M).
- Isolation: first AO sandbox failed (missing tau2/user_simulator overlay, contaminated project), repaired; egress and shim fixes; infra restart 2026-10-11 22:40/22:46 (in-flight evals lost, state kept). Optimizer sessions before the 14:55 restart ran unsandboxed; transcripts were scanned and showed only directory listings of the db.json path, no read of tasks.json, split or test files.
- Rule-P parity relaunch of hc and ao; AO standardized on the new engine; ctl-oneshot processes were SIGKILLed by mistake during a restart (resumed; the false chaser scoring was discarded).
- Budget: CapEvolve checks its budget only at the start of an iteration (`harness.py:4581`) and charges `metric_calls` after the evaluation (`:668`). hc s0 and s2 reached 637 against 550; ao s2 reached 907 against 550 (over_budget_override logged). hc s0 and s2 were stopped by lead decision with cand_0003 cap_truncated, then finalized host-side on sel only. GEPA s2 stopped at my hard rollout cap (631) at n=607; its best was reconstructed from saved state (`ended_by: hard_rollout_cap`, `reconstructed_host_side: true`).
- AO early stops: s0 and s1 ended natively (the agent ended its own turn, the documented v1 AO failure mode). ao s1 post_sel was redone after an infra interruption (0.58). ao s2 was stopped at the 06:00 cutoff; its host finalize used `--n-confirm 0 --seal-anyway` with `CAPEVOLVE_ALLOW_TEST_RESCORE=1` because earlier test-split attempts existed.
- Counts are search-only (uniform ruling): ao s0 and s1 exclude the champion-on-sel finalize and leftover seed-on-sel rollouts.
- Infra errors from the gateway log: hc 25 to 29 user and 10 to 25 target non-200 responses per run (about 0.1 to 0.3% of 8 to 10k calls), gepa 27 to 53 target errors per run (0.3 to 0.7%), ao s2 60 of 18k. All were absorbed by retries or left as missing cells (post_sel missing 0). Candidate-fault tagging was active (`error_kind=candidate` scores 0).

## 5. AO ablation vector (E10B ao, all seeds)

`ablation {dag_parallel: true, active_eval: true}`, other switches stock; rule P (k_se 1, n_conf 3, z_conf 1.282, dmin 0, min_cov 0.95, footprint off, joint coverage, errored_trial_policy fail); orchestration agent through the claude-code driver, `optimizer_max_turns` 300, `max_optimizer_usd` 40 (cost metering inert: no optimizer transcript); isolated in the mount-namespace shim. The dagger and sensitivity labels (amendment 10L) are not part of the E10B spec. Outcome: native early stops (s0 two candidates, s1 one candidate), cutoff stop (s2); none accepted.

## 6. Not covered

Final test scoring of the Suite B artifacts is final-eval-eng's (seed champion for hc and ao, gepa best_idx 7 / 7 / 11, ctl-oneshot cand_0001). The host `/tmp` leak scan is reported separately in `audit/`.
