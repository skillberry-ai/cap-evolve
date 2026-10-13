# Capped-token forecast to 06:00 UTC (2026-10-13)

Prepared 2026-10-12 11:30 UTC from `logs/gateway_calls.jsonl`. "Capped" = upstream not `rits:` and not `azoai:`, counted with the gateway's own
formula (`usage.total_tokens` if present, else input + output + cache_creation). The log sums to 85.84M at 11:25:19 (counter 85.6M).
Burn: **6.92M in the last hour, 15.45M in the last two** (7.7M/h). 18.6 h remain to 06:00. Projections below are estimates with the assumptions
stated; ranges are low / central / high.

## 1. Capped tokens by arm, last two hours (M tokens)

| arm (all seeds) | last 1 h | previous 1 h | last 2 h | cumulative |
|---|---|---|---|---|
| E10B-harnesslens | 1.55 | 3.27 | 4.82 | 13.50 |
| E10B-hlext (s0) | 0.85 | 0.73 | 1.58 | 1.58 |
| E10-skillopt | 0.43 | 0.65 | 1.08 | 13.11 |
| E10-agent-optimize | 0.52 | 0.43 | 0.95 | 6.29 |
| E10-ace | 0.46 | 0.43 | 0.89 | 6.28 |
| E20-T / E20-PT / E20-P / E20-CTL / E20-GEPA | 0.31 / 0.26 / 0.27 / 0.00 / 0.07 | 0.29 / 0.33 / 0.28 / 0.33 / 0.00 | 0.60 / 0.59 / 0.55 / 0.33 / 0.07 | same (new) |
| E21-ruleP / E21-1S | 0.16 / 0.27 | 0.34 / 0.00 | 0.50 / 0.27 | same (new) |
| E10-wikiskill | 0.00 | 0.43 | 0.43 | 0.94 |
| E10B-hc / E10B-ao / E10B-gepa | 0.17 / 0.17 / 0.14 | 0.20 / 0.12 / 0.12 | 0.37 / 0.29 / 0.26 | 4.22 / 4.87 / 2.87 |
| E10-evoskill / E10-gepa | 0.19 / 0.10 | 0.08 / 0.11 | 0.27 / 0.21 | 1.82 / 1.39 |
| E12A / E12C / E12B hcstock | 0.16 / 0.08 / 0.10 | 0.10 / 0.10 / 0.01 | 0.26 / 0.18 / 0.11 | 1.19 / 1.85 / 0.11 |
| E10E-hl-trial, E26test-NOHIST, others | 0.23 + 0.16 + ~0.2 | ~0.1 | ~0.7 | small |

Where it is going: HarnessLens and hlext are 2.4M of the last hour (35 percent); Suite D (E20, E21) is 1.7M and rising; Suite A baselines (skillopt, ACE,
agent-optimize) 1.4M.

## 2. Remaining spend to 06:00, per still-running family (M tokens)

Method: remaining = min(rate x hours, distance to the arm's own guard or native end). Native ends use rollouts left x tokens per rollout so far.
Guards: CapEvolve 3.9M optimizer tokens per seed, HarnessLens 4M per seed (its own meter, ledger runs 1.1 to 1.4x higher), hlext 16M, baselines 4M
optimizer per seed (assumed).

| family | state now | ceiling or native end | low | central | high |
|---|---|---|---|---|---|
| HarnessLens s0, s2 | stopped at guard (4.56M, 5.66M) | done | 0 | 0 | 0 |
| HarnessLens s1 | 3.73M, 0.6M/h | guard 4M on its meter (about 1.0M left, about 1.25M in ledger) | 0.6 | 1.3 | 2.0 |
| **hlext s0** | 1.58M, 0.85M/h while active, idle 40 min | 16M cap: 14.4M left; 18.6 h x 0.85 = 15.8M | 5 | **11** | 14.4 |
| E10E-hl-trial-s9 | 0.23M | trial | 0.2 | 0.2 | 0.3 |
| E10 agent-optimize (3.70, 0.99, 1.60 now) | 257, 404, 380 of 600 rollouts | s0 hits 3.9M guard (+0.2); s1, s2 one or two more cycles | 1.0 | 2.2 | 5.4 |
| E10 hill-climb (0.15, 0.09, 0.23) | 340, 567, 275 of 600 | about 0.07M per candidate | 0.4 | 0.75 | 1.5 |
| E12A hcstock | 400, 515, 493 of 600 | near end | 0.2 | 0.25 | 0.5 |
| E10 ACE (2.38, 2.56, 1.33) | 200, 107, 89 of 600; rates 0.235, 0.135, 0.07 M/h | 4M per seed gives +1.6, +1.4, +2.7; rate gives 4.4, 2.5, 1.3 | 2.5 | 4.3 | 8.2 |
| E10 SkillOpt | s1 done; s0 506, s2 566 of 600 | 0.2 to 0.6M per seed | 0.5 | 0.8 | 1.5 |
| E10 WikiSkill / EvoSkill / GEPA / MIPRO | 244 to 296; 332 to 448; one seed at 499; 164 to 190 | tokens per rollout 1.2 to 1.7k | 1.6 | 2.2 | 3.5 |
| B hc, B ao | final evals and one ao seed live | | 0.5 | 0.8 | 1.3 |
| B GEPA (3 seeds) | 258 to 280 rollouts, 0.13M/h | 3.4k tokens per rollout (reflection + judge) | 1.5 | 2.4 | 3.4 |
| **E12B hcstock (3 seeds)** | judge only so far (0.12M), no optimizer calls yet | like E10B hc: about 1.5M per seed incl. judge | 2.5 | **4.3** | 6 |
| C gepa, hc, ao | 101 to 126 rollouts; hc live | | 1.0 | 1.7 | 4.3 |
| E12C hcstock, bestofk | 240 to 320; scoring done | | 0.35 | 0.55 | 1.0 |
| **Suite D (E20 T/P/PT/CTL/GEPA, E21 ruleP and 1S: 21 cells)** | 0.02 to 0.26M each now, still early; 1.7M/h combined | hc-type cell about 1.0M (like E10B hc 0.8M optimizer), CTL about 0.35M, GEPA about 0.5M | 9 | **14.5** | 22 |
| misc (smokes, E26test, dev probes) | | | 0.3 | 0.5 | 1.0 |
| **Total remaining** | | | **27.3** | **47.9** | **76.3** |

## 3. Total against 152M

| | low | central | high |
|---|---|---|---|
| capped now | 85.8 | 85.8 | 85.8 |
| running arms to 06:00 | +27.3 | +47.9 | +76.3 |
| = searches at 06:00 | 113.1 | 133.7 | 162.1 |
| planned Suite E | +16 | +17 | +18 |
| E26 | +1.2 | +1.6 | +2.0 |
| final-eval reserve | +18 | +18 | +18 |
| **total** | **148.3** | **170.3** | **200.1** |

**Verdict: no.** At the central estimate the total is about 170M, 18M above 152M. Only the low case (148M) stays under, and it assumes hlext stops at
about 5M and Suite D comes in at 9M. Even without the 18M reserve the central case (152M) sits on the line. The high case (200M) is 48M over.
The naive straight-line check (6.9M/h x 18.6 h) gives 214M, but that over-counts because HarnessLens finishes at its guards.

## 4. What to stop first (to close the 18M central gap)

| order | arm | saves (central) | when | why |
|---|---|---|---|---|
| 1 | **hlext s0** (exploratory extended arm, 16M cap, 0.85M/h) | 11M if stopped now; 7 to 8M if capped at about 4M total (reached around 14:00 to 16:00 UTC) | decide by 14:00 | largest single uncertain item, exploratory, and 1.58M used so far |
| 2 | **E12B hcstock** (stock-gate ablation on Suite B, not started on the optimizer) | 4.3M | before its first optimizer call, i.e. now | exploratory; E12A and E12C already cover the ablation |
| 3 | **E21 1S** (3 cells) | 2.7M | now to before 15:00 | secondary cell family; 0.28M used |
| 4 | E21 ruleP (3 cells) | 2.5M | before 15:00 | secondary |
| 5 | ACE s1, s2 (guard-limited baselines) | up to 2M | at their 4M guard | only if still short |

Stopping 1 (capped at 4M) + 2 + 3 recovers about 14 to 15M, taking the central case to about 155M; adding 4 brings it to about 152M. If hlext is stopped
outright, items 1 and 2 alone (15.3M) get to about 155M, and item 3 closes the rest. Keep Suite E at the low end (16M) and E26 at 1.2M.
Re-forecast at 15:00 UTC when Suite D cells have finished their first iteration, because Suite D is the least certain term (9 to 22M).

## 5. Assumptions and uncertainty

- Rates are the last 1 to 2 hours; arms in long evaluation waits (idle for an hour or more) are treated as continuing at their average rate.
- The guards are on the optimizer role; judge and reflection tokens (Suite B) are counted in the capped total but not in the guards. The per-seed
  4M guard for baselines is an assumption (ACE, WikiSkill, EvoSkill, SkillOpt).
- Suite D cost per cell is extrapolated from E10B hc (0.8M optimizer) and E10C hc (0.3 to 0.4M); azoai judge/target tokens are in the Azure bucket and
  do not count.
- The ledger and the HarnessLens meter differ (1.1 to 1.4x), so the HL numbers are approximate in both directions.

## Re-forecast 2026-10-12 15:09 UTC (ladder: 170M exploratory, 178M secondary, 182M all searches, 18M reserve, cap 200M)

Capped counted from the log: **109.8M** at 15:09 (11:25: 85.8M), burn **6.96M/h last hour, 6.6M/h over 3 h**. The 11:30 forecast under-predicted: 24M was spent in 3.7 h
(the central case implied about 10M). Causes: HarnessLens resumed on all three seeds after the bubblewrap fix and the refunded iterations (s0 5.47M, s1 6.14M,
s2 7.93M in the ledger; the 4M guard is on HL's own meter, so refunds let the ledger run past it), hlext at 5.42M and 1.2M/h, **ACE far above the earlier estimate**
(s0 4.43M at 350 of 600 rollouts, already past the assumed 4M guard, so no such guard applies; 12.7 to 19.6k tokens per rollout, 1.1M/h), and E26 NOHIST at 1.87M in 3 h.

| family | now | basis to 06:00 (14.85 h) | low | central | high |
|---|---|---|---|---|---|
| HarnessLens s0, s1, s2 (all active) | 5.47 / 6.14 / 7.93 | 2.1M/h now, guard on meter with refunds | 2 | 4.5 | 8 |
| hlext | 5.42 | 1.0 to 1.2M/h to its 16M cap (cap reached about 00:00 to 01:00) | 8 | 10.6 | 10.6 |
| **ACE (unguarded)** | 4.43 / 3.09 / 1.98; 350 / 158 / 149 of 600 | rollouts left x tokens per rollout = 3.2 / 8.7 / 6.0 = 17.9M; rate 1.1M/h x 14.85 = 16.6M | 9 | **14** | 18 |
| Suite D (E20 P/PT/T/CTL/GEPA, E21 1S/ruleP) | about 0.2 to 0.6 per cell, 1.3M/h combined | cells finishing at about 1 to 1.5M | 6 | 9 | 14 |
| E26 NOHIST | 1.87 (plan 1.2 to 2) | 0.55M/h | 1 | 1.5 | 4 |
| other baselines and B/C/E12 (WikiSkill, SkillOpt, EvoSkill, GEPA, ao, hc) | | mostly near native end | 4 | 6 | 8 |
| **running total** | 109.8 | | +30 | **+45.6** | +62.6 |
| Suite E (not yet admitted) | | 16 to 18 | +16 | +17 | +18 |
| **searches at 06:00** | | | **155.8** | **172.4** | **190.4** |
| + 18M reserve | | | 173.8 | 190.4 | 208.4 |

**Verdict against the ladder (searches, reserve separate):**
- 170M exploratory stop: **crossed in the central case** (172.4M), likely between **02:00 and 05:00 UTC** once Suite E is running (the pre-Suite-E burn reaches about 155M at 06:00; Suite E adds about 17M over 9 to 11 h from 19:00 to 21:30). Not crossed in the low case (155.8M).
- 178M secondary stop: not crossed centrally; crossed in the high case (190M), around 00:00 to 03:00.
- 182M all searches: not crossed centrally; crossed in the high case. The 200M cap holds in the low and central cases (173.8M and 190.4M with the reserve), not in the high case (208M).

**Arms to stop first if the 170M rung is hit:** (1) hlext (exploratory, 10.6M still to go, stop or cap at about 10M total and save about 6M); (2) ACE s1 and s2, the new largest grower and the biggest correction to the last forecast: cap each seed near 5M (s0 is already 4.4M) and save about 8M of the 14M; (3) E26 at its planned 2M (saves 0 to 2M). Decide on ACE and hlext now rather than at the rung, because their burn is front-loaded.

## Guard audit and post-ACE-stop re-forecast (2026-10-12 15:20 UTC)

Shared definition: optimizer-role tokens on the gateway ledger = `usage.total_tokens` if present, else input + output + cache_creation (cache reads excluded),
roles other than target/user/judge/probe/usersim, capped upstream. Totals per exp-arm-seed at 15:11:44.

**Over 4M on the ledger:** HarnessLens s0 5.47M, s1 6.14M, s2 7.93M; hlext 5.42M (cap now 10M); **SkillOpt s1 4.78M, s2 5.10M** (s0 3.57M); **ACE s0 4.43M**.
Near the limit: E10 agent-optimize s0 3.96M (its watchdog fired: `optimizer_tokens.json.killed`).

| arm | guard in the launcher | limit and meter | status |
|---|---|---|---|
| E10 hill-climb, agent-optimize, E12A hcstock | `token_watchdog.py` on tag `$E10_TAG:optimizer`, kills the process group | 3.9M non-cache (soft 3.5M); ledger definition | uniform enough; AO s0 killed at 3.96M |
| E10B, E10C, E12B, E12C CapEvolve and GEPA | `cost_summary.py --guard` | **3.9M**, max over roles optimizer or reflection (not their sum), polled every 60 s, strict `>` | ledger definition, 3.9M not 4.0M |
| E20, E21, E26, E30/E32 (Suite D and E) | `cost_summary.py --guard` | **4.0M**, same role rule | ledger definition |
| ACE | in-process `--max-opt-tokens` (`ace_run.py`, `ace_batch_run.py`) | 3.9M of its own meter = in + out only | **present but a different meter**: s0 own meter 3.9025M = ledger 4.43M (13 percent higher); s1 own 1.43M vs ledger 3.09M, s2 own 1.31M vs ledger 1.98M because the ledger also holds the restarted attempts. The guard fired late in ledger terms and will fire at about 5.9M (s1) and 5.0M (s2) on the ledger if left alone |
| HarnessLens | `HL_MAX_OPT_TOKENS` 4M on HL's own meter (refunds failed iterations) | not the ledger | ledger 5.5 to 7.9M; refunds explain the overshoot |
| hlext | `hl_ext_cap_watch.sh` TOKCAP 10M | ledger | 5.42M used |
| WikiSkill | in-process `--opt-token-cap` 4M | non-cache | 0.8M used |
| Meta-Harness | `--proposer-token-cap` 4M | in + out + cache_creation | 0.2M used |
| **SkillOpt** | **none** (only a rollout cap) | | **s1 and s2 over 4M** |
| **GEPA (Suite A), MIPROv2, EvoSkill, Trace2Skill** | **none** found in the launchers | | 0.2 to 2.2M used, all under 4M; Trace2Skill finished |

Findings: (1) SkillOpt has no optimizer-token guard and is over 4M on two seeds, but it is at 600 and 566 of 600 rollouts, so almost no further spend.
(2) ACE did have a guard, but on its own in+out meter, which understates the ledger by 13 percent on the current attempt and by up to 2x where restarts spent tokens under
the same tag. To enforce the 4M rule on the ledger for s1 and s2, stop them from outside (e.g. a `cost_summary.py --guard` on `E10-ace-s1:` and `s2`) instead of relying on the 3.9M own-meter guard.
(3) Limits differ (3.9M vs 4.0M) and are checked per role, not summed; minor. (4) GEPA A, MIPRO and EvoSkill have no guard but are far from 4M.

**Re-forecast with ACE and hlext capped (ledger-definition 4M for ACE s1 and s2, hlext 10M):** ACE remaining drops from +14M to +2.9M (s0 0, s1 +0.9, s2 +2.0) and hlext from
+10.6M to +4.5M. Running total +28.4M (was +45.6M), searches 138.2M at 06:00, plus Suite E 17M = **155M**, below the 170M rung; with the 18M reserve 173M, under the 200M cap. High case about
165M. If ACE s1 and s2 are left on their own meter, add about 6M (161M central, no rung crossed). Next pass 21:11 UTC.

## Re-forecast 2026-10-12 21:11 UTC (Suite E admitted; ladder 170M / 178M / 182M, 18M reserve, cap 200M)

Capped now **141.81M** (15:09: 109.8M; +32M in 6 h, 5.3M/h average). Last hour 7.69M, of which hlext 3.58M; last 3 h 19.1M. Suite E started about 18:50 and has used **7.24M** so far
(E30-PT 2.04, E30-P 1.64, E31-ruleP 1.52, E30-T 1.41, E36-nohist 0.63; E32 AO and the E30 GEPA/CTL cells have not started), 2.4M/h.

Suite E remaining: Suite D's final cost is a good analogue (E20 7.41M, E21 2.45M, E26 2.98M, together 12.84M for the same cell types; E30 7.4 + E31 about 2.0 + E36 about 3.0 + E32 AO about 5 = about 17.4M, matching the 16 to 18M plan), so about 10M more
(8 to 12M). At its current pace (2.4M/h x 8.8 h) the cells would reach 21M if none finished early, which is the high case.

| item | now | remaining to 06:00 | low | central | high |
|---|---|---|---|---|---|
| **hlext** | 13.74M ledger, **3.58M in the last hour**, process alive | its own 16M guard (about 2.3M) or the 10M watch | 0.5 | 2.0 | 3.5 |
| **ACE** | s0 4.43 (stopped), **s1 4.70M, still running**, s2 2.30M, running | s1 near its own-meter guard; s2 to 4M on the ledger if stopped externally | 1.7 | 2.5 | 4.5 |
| Suite E (E30, E31, E36, E32 AO, GEPA, CTL) | 7.24M | 16 to 18M plan; pace-based high 21M | 8 | 10 | 16 |
| E12B hcstock | optimizer 0.77M, judge 1.0M | like E10B hc | 0.8 | 1.2 | 2.5 |
| other baselines, B/C GEPA, final evals | | WikiSkill 484 to 523 of 600, EvoSkill, GEPA, hc/ao finals | 1.2 | 2.1 | 3 |
| **total remaining** | | | **12.2** | **17.8** | **29.5** |
| **searches at 06:00** | 141.8 | | **154.0** | **159.6** | **171.3** |
| + 18M reserve | | | 172.0 | 177.6 | 189.3 |

**Verdict:** the 170M exploratory rung is not crossed in the low or central case (154M, 160M) and is crossed only marginally in the high case (171M), around 05:00 to 06:00 UTC, if Suite E runs at its current pace to 21M. 178M and 182M are not
crossed in any case. With the reserve the total stays under the 200M cap in all three cases (172M, 178M, 189M). The earlier central forecast (155M) was close; the miss was hlext and ACE running past their caps.

**Arms to stop or check:**
1. **hlext**: the gateway ledger shows 13.74M against the 10M cap you set, and 3.6M/h in the last hour. `hl_ext_cap_watch.sh` measures `creation_budget.json` usage (input + output + cache_write of HL jobs), not the gateway ledger, so it has not fired. Stop it now (or move the watch to the ledger) to save 2 to 3.5M.
2. **ACE s1** is at 4.70M on the ledger, over 4M, with a live process (own-meter guard 3.9M, which understates the ledger); stop it externally. **ACE s2** at 2.30M also needs an external ledger guard at 4M, otherwise it may reach about 5M.
3. Suite E: watch the 2.4M/h pace; if it is still above 2M/h at 02:00 UTC, trim the lowest-priority Suite E cell family so the high case stays under 170M.

## Guard actions on the current-attempt basis, and the v2 line (2026-10-12 21:30 UTC)

Basis: ledger non-cache-read tokens (input + output + cache_creation) of the CURRENT attempt, excluding attempts superseded by an infrastructure restart (erratum 12). Gross = whole tag history. No process was stopped by this audit, because no search is at 4M or 10M on this basis.

| item | gross (gateway, all attempts) | current attempt | limit | action |
|---|---|---|---|---|
| hlext s0 | 13.74M | **8.72M** (`creation_budget.json` jobs, 140 sessions, after the clean cut; 4.51M at 15:22) | 10M own cut | **not at 10M: no stop.** `hl_ext_cap_watch.sh` (pid 1270864) already measures exactly this ledger (input + output + cache_write of jobs), so no repointing is needed; it fires at 10M, about 1.3M away |
| ACE s0 | 4.43M | 3.90M (since 00:59:27) | 4M | native stop, under the cap |
| ACE s1 | 4.79M | **3.15M** | 4M | not at 4M: keep running. `ace_token_guard.py 1 <pid> --limit 4000000 --since 2026-10-12T00:59:27Z` is already running (pid 1469390) on this basis and will SIGTERM at 4M; the ACE owner then takes the last epoch checkpoint at or under 4M and runs validation |
| ACE s2 | 2.34M | **1.70M** | 4M | guard already running (pid 1469391), same definition; nothing to add |

So all three of the requested actions are already satisfied or not yet triggered: the gross figures I quoted at 21:11 (hlext 13.74M, ACE s1 4.70M) overstated the over-cap position, because they include superseded or refunded attempts.

### v2 line: HC-2 and AO-2 reruns after 06:00

Assumptions: HC-2 and AO-2, 3 suites x 3 seeds each = 9 + 9 searches, Sonnet 5.5 optimizer, 4M per-search cap. Per-search optimizer cost from v1: HC 0.1 to 0.7M (central 0.4M), AO with bounded jobs 0.3 to 1.5M (central 0.9M).
Suite B also bills its LLM judge to the capped total (about 0.9M per HC search and 0.45M per AO search in v1): +2.7M (HC-2, 3 seeds) and +1.4M (AO-2).

| | low | central | high |
|---|---|---|---|
| HC-2 (9 searches) | 0.9 | 3.6 | 6.3 |
| AO-2 (9 searches) | 2.7 | 8.1 | 13.5 |
| Suite B judge on v2 | 2.5 | 4.1 | 5.0 |
| **v2 total** | **6.1** | **15.8** | **24.8** |

Headroom under the all-searches stop (200M cap minus 18M reserve = 182M) after the v1 searches, using the 21:11 projection (154 / 160 / 171M): **28M / 22M / 11M**.
What fits: v2 central (15.8M) fits with v1 low or central (leaving 6 to 12M); v2 high (24.8M) fits only with v1 low; with v1 high (171M) only about 11M is available, enough for HC-2 plus a part of AO-2.
Recommendation: run HC-2 first (3.6M central, 6.3M high, 3 suites), enforce a 1.5M per-search soft cap on AO-2, and start AO-2 only when the v1 actual at 06:00 leaves at least 16M under 182M. If the v1 actual is 171M, run AO-2 on one suite (about 2.7M central) or defer.
The 170M exploratory and 178M secondary rungs apply to v2 as well, so treat v2 as secondary: stop it first at 178M.

## Re-forecast 2026-10-13 00:50 UTC and ladder application

Capped **158.76M** (00:48:51). Pace: 4.11M last hour, 7.18M last 2 h (3.6M/h). 5.2 h to 06:00.
Active consumers and projection to 06:00 (M tokens): E32-ace (3 seeds, launched 00:06, 1.30M in its first hour, 4M guard per seed not binding before 06:00) +6.8; E32-gepafull +3.3 (0.63M/h);
E32-ao +2.0 (0.10M so far, idle 35 min, ramping; 1.0M per seed over about 10 h); E30-GEPA +1.5 (2.28M so far, 0.6M/h); E10 ace s1 and s2 +1.5 (guards at 4M current attempt); E12B hcstock +1.5 (3.07M so far);
B/C GEPA, ao, hc finals +1.0. **Total +17.6M (low 14, high 22): 176.4M at 06:00 (172.8 / 180.8).** hlext is finished (stopped at 22:44 by the 10M cut, 10.05M on its own ledger); E31-1S, E36-nohist, E30-P/PT/T, E31-ruleP are done or idle.
Registered W4 (competitors) already launched at 00:06: ace/s0-s2, gepafull/s0-s2, ao/s0-s2 (mipro/s0-s2 at 22:17, idle since 23:44); the queue holds only `hl` (seed 0).

Time to rungs at the status quo: **170M at about 03:50 UTC (+-1 h)**, 178M at about 06:30, 182M at about 07:30. Suite E searches may run past 06:00 (10I) with guards of 4M per seed (W4 alone up to 36M), so the ladder, not the guards, is what binds after 06:00.

### Ladder as registered (decisions 2026-10-12 11:29Z; cut order 10K)
- **170M, exploratory arms, HL-extended first.** (1) hlext: already stopped (nothing to stop). (2) E12B hcstock s0-s2 stock-gate cells: the only exploratory family still running (E12A, E12C ended); note decisions.md calls E12B exploratory (lines 179, 336) and, in the older 10:01Z ladder, secondary; lead to confirm. Remaining E12B spend about 1.5M, so this rung saves little.
- **178M, secondary arms:** ACE (E10 s1, s2; E32-ace s0-s2), MIPROv2 (E32-mipro, idle), Trace2Skill (finished). By 10K the Suite E "competitors" (W4: ace, mipro, gepafull, ao, hl) are the first Suite E cut; the rest follows the fixed order E30-GEPA, E31-1S, E30-CTL, seeds 3 to 2, E36-nohist, E31-ruleP; E30-P, E30-PT, E30-T are never cut. Cuts are decided by the clock and capacity only, never by a score.
- **182M, all searches** (budget stop, non-binding for N*). 18M stays reserved for the final evaluation.

### Options for W4 (capped total at 06:00, and headroom under 182M for v2)
| option | what runs | 06:00 total | headroom to 182M | crosses 170M | v2 (central 15.8M) |
|---|---|---|---|---|---|
| A. launch the queued `hl` as well | as now + hl seed 0 (+2.5M, 1.5 to 4) | **178.9M** | 3.1M | about 03:20 | does not fit |
| status quo (hold `hl`, nothing else changes) | W4 as launched | **176.4M** | 5.6M | about 03:50 | does not fit |
| C. primary-comparison cells only: keep E32-ao and E32-gepafull, stop E32-ace (-6.8M), hold `hl`; optionally also stop E10 ace s1/s2 (-1.5M) | ao, gepafull, E30-GEPA, E12B | **169.6M** (168.1M with E10 ace) | **12.4M** (13.9M) | about 06:00 (not before) | HC-2 (3.6M) plus part of AO-2, not the full 15.8M |
| B. hold W4 entirely: stop E32-ace, gepafull, ao now (-12.1M of the remaining spend; 2.0M already sunk), hold `hl` | E30-GEPA, E12B, E10 ace | **164.3M** | **17.7M** | not before 06:00 | fits (15.8M) |

Primary-comparison cells are my assumption (CapEvolve-AO and GEPA appear in every earlier suite; ACE, MIPROv2 and HL are the secondary or competitor arms in the registered order): confirm which W4 families the paper needs before cutting.
