# R4: overnight experiment designs (design only; nothing launched)

Written 2026-10-28 ~23:30 UTC. Deadline 2026-10-30 20:00 UTC; experiments, scoring and analysis must finish by about 2026-10-30 12:00 UTC.
Reviewer asks: R1 fresh held-out with frozen procedure; R2 replicated gate ablation and alternative gates; R3 isolate capability editing; R4 matched dollars/tokens; R5 cross-model; R6 budget robustness.

## 0. What the data say (facts used below)

- Search logs. Candidate-level events for the three GATE-K2 searches are in `/tmp/audit_x_abl/runs/ABL/GATE-K2/s{0,1,3}/.capevolve/run_main/events.jsonl` (19 `step` events each; fields accept, val, parent_val, delta_full, se_full, n_fixed, n_broke, opt_cost_usd, candidate). `/tmp` is volatile; copy it.
- The original run dirs `campaign-scratch/runs/ABL/GATE-K2/s*` hold only `env.sh` and `claude_cfg`. The candidate snapshots and `state.json` exist only in `/tmp/k2g_arc/runs_ABL.tar.gz.part000/001` (2.9 GB, sha file beside it; extract each into its own empty directory). That tarball is the single copy. Back it up before anything else.
- Candidate trees: `candidates/cand_NNNN/{policy/policy.md, tools/tools.py, ...}`. Naive-gate searches have theirs on disk in `runs/K2GATE_AWS/GATE-NAIVE-K2A/s*/.capevolve/run_main/candidates`.
- Step events record `opt_cost_usd` only. `cost_usd` is 0 for tau2 (agent and user-sim are unpriced in the event). Target and user cost come from `cost_summary.json` (s0: target $63.1, user $4.1, optimizer $61.4, total $128.6; about $0.0223 per counted rollout for target and user). A cost-matched incumbent must be computed on the same total-cost definition as the $116.63 vs $68.01 in the paper. Define it once in the pre-registration.
- A counted rollout is 150 per evaluation (30 tasks x 5 trials); the seed is 150 and each iteration adds 150, so counted rollouts at iteration i are 150(i+1). R=3000 is reached at iteration 19.
- Accepts and incumbent trajectory (val; only accepts shown):
  - s0: cand_0003 (0.70, iteration 3), cand_0008 (0.81, 8), cand_0014 (0.91, 14).
  - s1: cand_0002 (0.72), cand_0005 (0.84), cand_0013 (0.93).
  - s3: cand_0002 (0.73), cand_0011 (0.83).
  - Accepts are front-loaded; the last accept happens at iteration 11-14 of 19.
- The optimizer, not the evaluator, sets wall time. The naive-gate step logs show optimizer_seconds 1240 against runner_seconds 397 at 48 workers. So 12-18 h per search is nearly independent of worker count, and 16 workers per search costs little wall time.
- Existing airline test-20 results (`final_eval/MERGED/main/results_long.csv`, 10 trials): CapEvolve s0/s1/s3 0.630/0.645/0.625 (s2 excluded, 0.565); seed 0.50; SkillOpt 0.572; Trace2Skill 0.553; EvoSkill 0.557; GEPA(full) 0.557; ACE 0.538; Meta-Harness 0.530. K30 has GATE-K2 s0/s1/s3, NAIVE, NONE, and V2-A* ablation arms at 30 trials.
- Existing k coverage on tau2 airline: k=0 naive (3 searches in progress or done; s0, s3 done, s1 about 03:00), k=1 (hcstock, V3 B1, 3 seeds, a different launch campaign), k=0.5 (ABL, 1 search), k=2 (3), none (NONE-K2A). Missing: 1.65. k=1 is partly covered by hcstock, but only if its yaml matches K2 apart from k and route; check before spending on a new k=1.
- Gateway limit: `DEFAULT_LIMITS` is 128 concurrent for aws/gpt-oss-120b, shared with everyone, and 429s have been seen. Eight searches at 24 workers (192) will throttle. Budget about 100 concurrent worker slots for searches plus scoring windows.

## 1. Free re-analysis, already run (experiment c0)

Counterfactual gate decision per logged step: accept iff delta_full >= k*se_full (and delta>0), on the 6 searches with step logs. Counts are accepts out of 19 steps (s1 of naive: 15).

| search | k=0 | 0.5 | 1 | 1.65 | 2 | sign test p<0.05 | actual |
|---|---|---|---|---|---|---|---|
| K2 s0 | 16 | 15 | 13 | 7 | 3 | 0 | 3 |
| K2 s1 | 12 | 10 | 9 | 5 | 3 | 0 | 3 |
| K2 s3 | 10 | 8 | 7 | 3 | 2 | 0 | 2 |
| NAIVE s0 | 8 | 4 | 3 | 2 | 0 | 0 | 8 |
| NAIVE s1 | 7 | 4 | 3 | 2 | 1 | 0 | 7 |
| NAIVE s3 | 7 | 6 | 2 | 0 | 0 | 0 | 7 |

Read-outs:
- The paired sign test on n_fixed vs n_broke (30 tasks) never fires. It has almost no power at this scale; this is a usable statement for the "SAGE-like sign test" ask. An e-value version (anytime-valid, mixture over delta) can be computed on the same deltas and se. It will be even more conservative.
- Caveat to state in the paper: this is per-decision re-analysis along the realized path. Once a rule diverges, its incumbent chain, and thus all later deltas, differ. It answers "how many logged candidates would each rule have let through", not "what would the search have reached". Only new searches (b2/c below) answer the second question.
- Free extension: compute, for all 6 searches, the false-accept proxy "accepted but delta_full < 1 SE". For K2 this is 0 by construction; for NAIVE use the shadow field `gate_override_shadow`.

Pre-registration text: "Using the logged paired deltas and standard errors of the six GATE-K2 and GATE-NAIVE-K2A searches, we report, for k in {0, 0.5, 1, 1.65, 2}, a two-sided paired sign test at 0.05 and an e-process, the number of steps each rule would have accepted. Rules and thresholds are fixed here; no held-out data are used." Code: a 40-line script, no framework change.

## 2. Experiments

### E1 (R4, R6). Cost-matched and budget-curve frozen incumbents (candidate "a")

Question: at equal dollars (SkillOpt $68) and at 1,000/1,500/2,000 counted rollouts, does the CapEvolve incumbent already beat the comparators?

Incumbents per iteration from events.jsonl. Counted-rollout cut: the last iteration with 150(i+1) <= target, so 1,000 -> iteration 5 (900), 1,500 -> 9 (1,500), 2,000 -> 12 (1,950). From the approximate cost recomputation (optimizer cumulative + $0.0223 x counted rollouts), the incumbent at total cost <= $68 is: s0 cand_0008 (iteration 8), s1 cand_0005 (9), s3 cand_0002 (9). Recompute exactly from `cost_summary.json` plus per-step optimizer costs when writing the final script.

Unique candidate set (a few coincide across targets):
- s0: cand_0003, cand_0008, cand_0014.
- s1: cand_0002, cand_0005, cand_0013.
- s3: cand_0002, cand_0011.
- Total 8 unique CapEvolve incumbents.
- Plus SkillOpt champions s0-s2 and the seed (4). Optionally Trace2Skill (3), which has the best gain per dollar.

Scoring: airline test-20, 30 trials. Existing artifacts already have 10 trials, so add 20 trials (new trial seeds): final CE champions (3, add 20 each), plus 5 intermediate CE incumbents x 30, plus SkillOpt x3 and seed x 20 extra. Jobs: (3+5)x(20 or 30)... about 11 artifacts x 400-600 = about 5,000 rollouts. At 2,400 rollouts/h this is about 2.1 h at 48 workers.

Expected result: at $68, s0 cand_0008 val 0.81 and s1 cand_0005 val 0.84 are above their $68 SkillOpt equivalents on val. Test gap shrinks relative to the final (full-budget) incumbents; honest expectation is a mean test of about 0.58-0.62 at $68, still at or above SkillOpt's 0.572 but not significantly (SE about 0.03-0.04, power under 0.5). The paper statement can then be a descriptive budget curve with CIs, not a significance claim.

Power: one frozen incumbent vs SkillOpt, 3 searches each, SE about 0.03; detects a 0.07 difference with about 55% power. State it plainly.

Pre-registration text: "Incumbent definition: the champion state after the last iteration with cumulative counted rollouts <= T (T in {1000, 1500, 2000}) or cumulative total cost <= $68.01 (cost = optimizer usd from step events + 0.0223 x counted rollouts, constants fixed from cost_summary.json of s0). The primary contrast is the mean over 3 searches of the $68 incumbents vs the mean over 3 SkillOpt champions, paired by task, 20 tasks x 30 trials per artifact. The curve over T is descriptive. No incumbent is added or dropped after scoring."

Code changes: a script to materialize candidate dirs into the final_eval champion JSON format (`champions_E1.json`), after extracting the tarball. No framework change.

### E2 (R3). Replicated surface ablation (candidate "b")

Run two more policy-only searches (CAP-P s1, s2) so that 3 policy-only face 3 full CapEvolve (K2 s0/s1/s3) with the same optimizer, feedback, budget, gate k=2, split seed 42, R=3000, K=5. The spec for CAP-P is in the tarball; recover `capevolve.yaml` from `runs/ABL/CAP-P/s0` in the tarball and diff it against K2 s0 (expect only the editable-surface restriction and arm name; diff must be in the pre-registration, like the K2GATE DESIGN.md).

Cost: 2 x about $117-130 = about $250. ETA 13-18 h.

Scoring: 2 new champions plus existing CAP-P s0 at 30 trials = 3 x 600 = 1,800 rollouts (about 45 min). Full-CapEvolve already has 30 trials via K30/K2 windows (check that K30 covers s0/s1/s3; it does).

Power from the K30 policy-only effect of -0.112 (the effect from one search each, k=3, SE about 0.036-0.044). With 3 vs 3 searches the trial and search terms shrink; the task-by-surface heterogeneity term (25-60% of variance) does not. Estimated SE about 0.028-0.032, so at the observed -0.112 the paired t (19 df) has power about 0.9; at a shrunk effect of -0.075 about 0.7. If the effect is truly under 0.05, no outcome here will show it.

Optional E2b tools-only (CAP-TD or CAP-TC, whichever K30/ABLW1 labelled "tools only"; confirm in the registry). Two more searches, $250, same slot cost. Value lower than E2 because the paper's argument runs through policy-only (AppWorld policy-only is nearly equal to full). It also provides the contrast R3 asks for between editing tool code and editing text.

Extra contrast at no cost: policy-only CapEvolve (3) vs SkillOpt/GEPA (prompt-only, 3 seeds). Same edit surface, different feedback and optimizer. If policy-only CapEvolve is about 0.55-0.58, this says the edit surface rather than the feedback or optimizer explains most of the lead. Pre-register this as the second R3 contrast.

Pre-registration text: "Primary: mean test reward of the champions of 3 policy-only searches (CAP-P s0, s1, s2) minus 3 full searches (GATE-K2 s0, s1, s3), paired by task over the 20 test tasks, 30 trials each, bootstrap over tasks and search level (t with 2 df as a secondary interval). H0: no difference; the direction expected is negative. Champion = the search's own final incumbent. The searches are run to R=3000 or stopped at the pre-set wall limit and the incumbent at that time is scored; any search whose optimizer hits the 80-turn cap in more than 8 of 19 sessions is reported but not excluded (the s2 exclusion rule is not reused)."

Needs code changes: none if the CAP-P yaml/env.sh from the tarball reproduce (verify with the `wt-abl-cap` worktree commit used originally; the K2GATE shim and AWS route differ from the original ABL run, so use the K2GATE_AWS recipe: wt-k2gate, aws route, with the surface restriction). That mixes the route: K2 ran at the K2 serving route and the policy-only s0 as well; the new ones run at aws. Both K2 and CAP-P s0 used the aws/gpt-oss route per DESIGN.md ("the SAME route K2 search 1 used"), so the route is consistent. Confirm CAP-P s0 env.sh.

### E3 (R2). Alternative gates (candidate "c")

E3a (free): re-analysis in Section 1.

E3b: new searches at k=1.65 (RLMOpt level) x 3 seeds, everything else equal to K2 (one yaml line, `gate_k_se: 1.65`). This completes the k-curve {0 (naive), 0.5, 1 (hcstock), 1.65, 2}. Expected from the logs: at k=1.65 the realized chain accepts about 2-4 steps (the counterfactual: 7/5/3 at the K2 incumbents, but the chains diverge), final val about 0.85-0.90, test about 0.60-0.64, i.e. equal to k=2. If k=1.65 equals k=2, the finding is "gate level is insensitive between 1.65 and 2", which answers R2 and Q1 from review 1 directly. Cost 3 x $120 = $360. ETA 13-18 h.

E3c: k=1 x 2 only if hcstock turns out not to be comparable (different route/instructions); otherwise skip and cite hcstock. Needs a one-hour check, not compute.

E3d: SAGE-like sign-test gate. The 6-search table shows a sign test on 30 tasks never accepts, so a live search would almost never move. Do not run; report as a counterfactual only, with the power argument. This is the honest answer and cheaper than a degenerate search.

Pre-registration text: "Three searches with gate_k_se=1.65 (split seed 42, K=5, R=3000, same instructions/optimizer/route as GATE-K2; byte-diff of yaml and env.sh attached), champions scored on the 20 test tasks at 30 trials. Primary contrast: mean test of k=1.65 minus mean test of k=2 (3 vs 3), with a non-inferiority margin of 0.05 reported; secondary: the monotone k-curve 0 / 1 / 1.65 / 2 / none."

Power: 3 vs 3 searches, SE 0.03; can show equality only within +/-0.06 (non-inferiority margin 0.05 is too tight for 80% power; say so). It distinguishes k=1.65 from k=0 only if the 0.067 gap (naive minus K2 gap) is real.

Needs no code changes.

### E4 (R5). Cross-model transfer of frozen champions (candidate "d")

Score frozen test-20 champions with a second agent model; user-sim and judge unchanged. Candidates for the second agent: `rits/google/gemma-4-31B-it` (listed in the :4113 /v1/models, was SpreadsheetBench's target), `rits/Qwen/Qwen3.6-35B-A3B` (listed), or `aws/claude-haiku-5-5` (not confirmed on the gateway; probe needed; stronger models compress effect sizes). Pick Qwen3.6-35B-A3B or Gemma after a 20-rollout smoke for tool-call format errors (a model that breaks on tool-call format will make a policy edit look like noise). Use the 20-rollout smoke to also check cost.

Artifacts: seed, CE s0/s1/s3 finals, SkillOpt s0-s2, Trace2Skill s0-s2, Meta-Harness s0 (the strongest tool-editing comparator). 11 artifacts x 20 tasks x 10 trials = 2,200 rollouts, about 1-2 h (slower model: up to 3 h).

Expected: CE gain over seed shrinks and maybe halves; CE vs SkillOpt unresolved. Power: 3 vs 3, SE about 0.04; only a 0.10+ difference is detectable. The value is the sign and the seed-relative gain on a different model, framed as transfer, not significance. Also useful: whether CE's tool edits break on a model with different tool-call habits.

Pre-registration text: "Second agent model M2 (chosen by smoke, fixed here before scoring). Same 20 test tasks and judge, 10 trials per artifact, no re-tuning. Primary: gain over the seed artifact for CapEvolve (mean of 3) vs the pooled prompt-only comparators; report fractions of artifacts above the seed."

Needs: model alias in the final-eval harness (`run_final.py` takes the target from the frozen settings; a per-window override flag or an env var is needed), a stats-reviewer-registered window, and a smoke. Small code change.

### E5 (R1). Fresh held-out (candidate "e")

Per r4_fresh.md: no unused tau2 airline task exists, retail test-40 has been scored many times, and a retail CapEvolve search would be 1 seed plus 1 comparator at best (adapter port 2-3 h, 30-of-49 task subsample, launch by 04:00 or it misses). I rank it below the following.

E5a (recommended): AppWorld test_challenge (417 tasks never in a registered window) with the frozen AppWorld artifacts (CE ce2_k1/k2, seed, Trace2Skill, GEPA-Full, SkillOpt, ACE), 2 trials: 6-7 artifacts x 834 = 5,000-5,800 cells. At 343 cells/h that is 15-17 h; with doubled workers, 8 h. Needs the artifact paths, the harness (`/tmp/aw/awenv`, `/tmp/aw/root`, volatile; snapshot first), and a smoke. It starts as soon as the smoke passes (target 03:00) and finishes by about 14:00 Oct 29. Expected: CE within noise of Trace2Skill, ahead of the weaker comparators (SE about 1.5-2.0 TGC points); it is a generalization-to-unseen-difficulty check, not a significance fix. AppWorld artifacts were selected with gate k=0.2 and the paper's frozen AppWorld procedure, so "frozen procedure, fresh tasks" holds for AppWorld.

E5b: one fresh-domain retail CapEvolve search at the frozen airline config, 1 seed only. Cost about $120 and 2-3 h of engineering. Launch only if the engineering is done by 04:00; otherwise cancel. A single search cannot carry a statistical claim; its value is a data point for "frozen procedure on a new domain" (accept/reject steps, test gain vs seed on the 40 retail tasks, previously scored for other artifacts). I recommend skipping unless a spare worker (engineer) exists, and disclosing that retail test-40 has been scored.

Pre-registration text (E5a): "Frozen artifacts (list and sha256 fixed in champions_E5a.json before launch), AppWorld test_challenge, 2 trials per task, all 417 tasks; metric TGC; paired scenario-clustered bootstrap CI for CapEvolve minus each comparator; no artifact added or dropped."

### E6 (diagnostic, R2). Decision-level audit of every accepted candidate

Using the same E1 machinery, score every accepted candidate of the K2 searches (8) and the naive searches (8+7+7=22, s1 once finished) on test-20 at 10 trials (200 rollouts each; about 30 x 200 = 6,000 rollouts, about 2.5 h). Report, for each accept, the test delta vs its parent. This measures the gate's false-accept rate directly: how often an accepted step was a test regression. It supports "what does the gate buy" with step-level evidence instead of one champion per arm. Expected: naive accepts include several test regressions; k=2 accepts almost none. This is a diagnostic on a test set that has been scored already, so label it exploratory. Order below E1 in value, but cheap and eval-only.

## 3. Ranking by value to an accept decision

1. E2 policy-only replication (R3, also the reviewers' third ask). High information, about $250, power about 0.9 at the observed effect. Do first.
2. E3b k=1.65 searches plus the free counterfactual table (R2 and Q1/Q2 from review 1). Directly supplies the sensitivity range and an RLMOpt-level gate. $360.
3. E1 cost-matched and budget curves (R4, R6). Eval-only, about 2 h, answers the "matched dollars" objection partly; the answer may be unflattering, but it is better known now. Free of search cost.
4. E5a AppWorld test_challenge (R1). Fresh tasks, frozen artifacts; the only genuinely new held-out available overnight. Risk: artifact and harness location, /tmp volatility.
5. E4 cross-model (R5). Cheap, easy, but not significance-bearing.
6. E6 decision-level audit. Cheap, eval-only, strengthens the gate story.
7. E2b tools-only, E3c k=1, E5b retail: only with spare slots.

## 4. Schedule (UTC) and parallelism

Slots. Optimizer time dominates, so use 16 workers per search (about 112 total across 7 searches would exceed the 128 shared limit with a scoring window running; so cap searches at 6 concurrent with a window, or 16 workers x 5 searches = 80 plus a 48-worker window).

| time | action |
|---|---|
| Oct 28 23:30-02:00 | Stats-reviewer registration of E1, E2, E3, E4, E5a, E6 designs (this file's pre-reg statements). Back up `/tmp/k2g_arc`, `/tmp/audit_x_abl`, `/tmp/aw` to campaign-scratch. Extract tarball into an empty directory; diff CAP-P yaml vs K2 s0; write `gate_k_se: 1.65` yaml; DESIGN.md for each arm like GATE-NAIVE-K2A. |
| about 02:00-03:00 | Launch 5 searches at 16 workers: CAP-P s1, CAP-P s2, K1.65 s0, s1, s3 (about 80 workers). GATE-NAIVE s1 is still running until about 03:00 (48 workers), so launch the last two searches after it ends if the gateway shows 429s. |
| 03:00 | Launch the 6th/7th searches if the gateway is healthy: CAP-T (tools-only) s1 and k=1 only if hcstock is not comparable. Smoke E5a (AppWorld) and the E4 model smoke (20 rollouts). |
| 03:00-12:00 Oct 29 | E5a AppWorld test_challenge window at 24-32 workers (5,000 cells, about 15 h; ends about 18:00 Oct 29). If the gateway is saturated, run E5a at 16 workers and accept a later end. |
| about 06:00 | After the NAIVE s1 final and E3a, score E1 plus E6 in one window (about 11,000 rollouts, about 5 h at 48 workers; split in two windows of 24 workers if searches are throttled). E4 follows (2,200 rollouts, 1-3 h). All three finish by about 16:00 Oct 29. |
| 15:00-21:00 Oct 29 | Searches end (13-18 h from launch). Stop rule: any search still running at Oct 30 02:00 is killed and its incumbent scored, reported as truncated with R used. |
| about 21:00 Oct 29-02:00 Oct 30 | Score the 5-7 new champions at 30 trials (3,000-4,200 rollouts, about 1.5-2 h) in one window; add them to the E2/E3 contrasts. |
| Oct 30 02:00-12:00 | Analysis, figures, paper edits. Everything after 12:00 is paper polishing only. |

Concurrency summary. Peak searches: 5-7 at 16 workers each, plus one scoring window and the AppWorld window. If 429s exceed a few percent on the gpt-oss route, drop E2b/E3c first, then reduce AppWorld workers.

Total new spend: about $250 (E2) + $360 (E3b) + optional $250 (E2b) = $610-860, plus scoring (about 20,000 airline rollouts, about $150-250 at gpt-oss rates) and AppWorld (a few hundred dollars at most; check).

## 5. Risks and caveats to carry into the paper

- Replicate searches share split seed 42, so replicate variation is optimizer-only (this is already true of K2 s0/s1/s3). Say it.
- The s2 search was excluded because of optimizer 80-turn truncation; new searches should log the truncation rate and the exclusion rule must be written before launch, not after (see E2 pre-registration: no exclusion).
- All airline test-20 scoring reuses a test set already seen many times. E1/E4/E6 are exploratory/diagnostic, not fresh held-out. Only E5a is genuinely unseen. E2/E3b champions are new artifacts on a reused test set; pre-registration fixes the test and procedure but this is not a new-task result.
- Intermediate-incumbent scoring (E1/E6) does not feed back into any selection; state that.
- Cost definition: step events omit target cost; use one explicit formula (optimizer usd from step events plus 0.0223 per counted rollout from s0's `cost_summary.json`), apply it to all searches, or compute each search's own from its `cost_summary.json` if available (s1/s3 summaries are in `/tmp/audit_x_abl` or `/tmp/cost_audit`).
