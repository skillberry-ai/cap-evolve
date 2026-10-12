# Agent-optimize (AO): diagnosis from the campaign runs, and a design that works

Author: read-only research pass (nothing running was touched, no code edited, nothing committed).
Date of the data: runs as of 2026-10-12 ~19:30 UTC.

Abbreviations. `ao/` = `skills/algorithms/agent-optimize/scripts/`; `ce/` = `core/cap_evolve/`; `A/` = `/home/dev/projects2/campaign-scratch/runs/E10/agent-optimize`; `B/` = `.../runs/E10B/ao`; `C/` = `.../runs/E10C/ao`.
Per-run files: `<seed>/.capevolve/run_*/{events.jsonl,state.json,host/transcript.jsonl,host/driver_prompt.md}` and `<seed>/logs/{host.out,optimizer_tokens.json}` (Suite A); `<seed>/.capevolve/run_main/...` (B, C).
Marks: **[V]** verified in a file or by a command I ran; **[M]** modeled/derived by me (assumptions given); **[U]** unverified.

---------------------------------------------------------------------------------------------------

## 0. Executive summary

1. Every AO seed returned the seed, but not because the proposer was bad. In all three Suite A seeds the first and only candidate (`cand_1`, a reply-format contract plus an inspect/write/verify/finish procedure) already cleared screening (s1: full-val 0.556 vs seed 0.447, P(beat parent) 0.988; s0/s2 half-val screens 0.80/0.65 and 0.80/0.85) **[V: A/s1 events.jsonl, host/transcript.jsonl line 278; s0, s2 events]**. No AO seed in any suite ever got a rule-P verdict, so no promotion was possible. The failure is the machinery around the proposer: serial blocking verbs, a 240-rollout confirmation, an LLM that has to sit and wait, and a prose-based stop rule.
2. The LLM is used as a scheduler and a poller. In Suite A, **75-91% of the guard-counted optimizer tokens (non-cache-read) were spent on waiting/polling turns** (53 of 74 turns for s0: 3.58M of 3.94M tokens; s1 0.84M of 0.98M; s2 1.20M of 1.59M) **[V: my usage tally over `host/transcript.jsonl`, deduped by message id]**. Each poll sleeps 9-10 min, longer than the 5 min prompt-cache TTL, so every poll re-creates the whole 40-90k context as `cache_creation` tokens (`cache_creation.ephemeral_5m_input_tokens` = all of it in the final result record). The real propose/diagnose work was 0.14-0.39M tokens per seed.
3. The three "early stops" have different causes: (A) the headless `claude -p` session ends its turn after killing/abandoning a 2 h background job (s1, s2); (B/C) the agent decides to stop with 60-80% of the budget unspent, quoting a stop_condition that literally says "or after 10 candidates"; (A s0) the token watchdog's soft stage only edits `max_metric_calls`, which an agent that is polling inside a running verb never sees.
4. `dag_parallel`, `active_eval` and `smart_merge` are implemented as **verbs and a data model, not as a scheduler**. Subset evaluation (`probe --auto`, `sched.pick`), a candidate graph (`graph.jsonl`, `CandidateGraph`), cell claims for concurrent probes (`act.py:286`) and n-way merge (`merge_n.plan`) exist. Nothing runs them in parallel, nothing implements successive halving live (`sched.halve`, `sched.STAGES` are only called from `ao/ablate.py`), and nothing survives the agent's session ending. "E32-ao" is the *same* engine and the *same* "10 candidates" stop_condition on a different benchmark (airline), launched by a shell script; it has not been launched yet (`runs/E32/ao` does not exist) and it contains none of the fixes **[V: `scripts/E30/launch_e32_ao.sh`, `ls runs/E32`]**.
5. Proposed design: **a code-driven conductor** (a Python process that owns the candidate graph, the evaluation pool, the budgets and the stopping rule) that calls the LLM only for bounded, stateless jobs: *propose an edit*, *diagnose*, *resolve a merge conflict*. Promotion is rule P in code. The conductor is crash-safe and resumable because all state is in `graph.jsonl` / `eval_index.jsonl` / a new `conductor.json`, and a supervisor re-launches it until it exits 0. Section 4 gives the interfaces; Section 5 the argument for being strictly better than hill-climb.

---------------------------------------------------------------------------------------------------

## 1. What each AO run actually did

### 1.0 Common machinery (what the agent was given)

- Launch: Suite A `_tools/run_ao.sh` (baseline via `phases/baseline/scripts/run.py`, then `ao/host.py --agent claude-code --model aws/claude-sonnet-5-5 --budget 2000`, token watchdog beside it); Suites B/C `cap-evolve run --agent-driver claude-code` (`ce/cli.py:934-942`) via `driver.sh`, resumed several times (`--resume`) **[V]**.
- `host.py` runs **one** `claude -p` subprocess (`ao/host.py:1292`, `subprocess.run(cmd, ...)`), then seals test and exits. The only re-launch is for `terminal_reason == api_error` (`_RETRYABLE_TERMINAL_REASONS`, `host.py:108`, used at `host.py:1385`). An `end_turn` is final.
- The agent reads `SKILL.md` and a 35 kB `driver_prompt.md` whose body is the legacy-round briefing with the `_NEW_LOOP` paragraph spliced in (`host.py:532-558`). The briefing still says "concurrency 8" for "every gate" (`host.py:318`, `driver_prompt.md:44`) but no `act.py` verb accepts a concurrency flag (`probe` only forwards `CAPEVOLVE_WORKERS` if the spec has `gateway_max_concurrency`, `act.py:361-363`). `ce/harness.py:54,108-125`: `DEFAULT_WORKERS = 1`.
- Rule P in E10 (spec): `promotion_rule: P, k_se 1.0, n_conf 3, dmin 0.0, z_conf 1.282, min_coverage 0.95, confirm_fresh_only` **[V: A/s1/project/capevolve.yaml]**. One confirmation = candidate 3 trials x 40 tasks + incumbent 3 x 40 = **240 rollouts** (`act.py:476-481`: `_eval_fresh` for both `tag` and `ref` at a fresh offset every promote; the incumbent's block is never reused across candidates).
- Ablation vector actually in force (A): `dag_parallel, active_eval, smart_merge, cost_gating, failure_clustering, pregate, context_digest` all true (`A/s1/manifest/ablation_effective.json`; `run_ao.sh` wrote `active_eval: false` and it was corrected before the first iteration). B/C: `{dag_parallel: true, active_eval: true}` plus defaults (`B/s1/manifest.json`, `agent_optimize_engine`). So `optimizer_config.new_engine()` was true everywhere (`ce/optimizer_config.py:101-104`).
- Evaluation throughput is slot-bound, not worker-bound. Gemma rollouts average ~1300 s (decisions.md line 77) and the eval daemon ran 4 slots (`run_ao.sh`: `E10_CONC=4`) => ~11-25 rollouts/h per search. s0 switched to `CAPEVOLVE_WORKERS=8` and a 20-rollout screen still took 1.0 h (`events.jsonl` +12.64h -> +13.67h) vs s1's 40-rollout screen at workers=1 in 3131 s. So "workers=1" cost little; the wall clock is dominated by the pool, and the wasted resource is *pool idle time while the agent thinks or the verb is serial*. [V for the two durations; the 4-slot figure is from the launcher, the effective rate is derived.]
- Baseline phase before the agent starts: seed on val-40 (3.7-4.1 h) **and on train-80 (5.6-7.5 h; 20,241 s for s1)** => the agent only began at +9.3 h / +9.3 h / +11.7 h of ~20 h. AO never reads train (audit §3), so the 80 train rollouts (13% of the 600 budget, ~30% of wall time) bought nothing for AO **[V: events.jsonl timestamps]**.

### 1.1 Suite A (SpreadsheetBench, val-40, budget 600 rollouts, Gemma target)

| seed | what it evaluated, in order | decisions | end |
|---|---|---|---|
| **s0** (`A/s0`) | baseline val-40 (0.462) + train-80. `propose cand_1` (h_cand_1, clusters Cadb036+Cfbbc70). Probes of cand_1: 20 tasks (workers 1, aborted/restarted at 8 workers) = 0.80; the other 20 = 0.65; then `promote` (3-trial rule-P confirm, 120+120) started 05:49 -> first call hit the 2 h limit; restarted 07:56, again polled 2 h; third call `probe --auto --n 3 --budget 17` (34 rollouts) at 10:03 | 1 propose, 2 screens, 0 verdicts | token guard: soft at 3,511,335 non-cache tokens (+20.34 h), hard SIGTERM at 3,958,447 (`A/s0/logs/optimizer_tokens.json`); 262 rollouts |
| **s1** (`A/s1`) | baseline val-40 (0.447) + train-80. `propose cand_1` (reply-format contract, 2 files). Full-val probe: first attempt moved to background at the 600 s tool timeout and then killed, rerun (40 rollouts, 3131 s) = **0.556 vs 0.447, P(beat parent) 0.988** (transcript line 278: "Promoting it"). `promote cand_1`: 120+120 at "~12 rollouts/h"; first attempt killed after 10 min of the tool's own limit, second after exactly 2 h (04:26:33 -> 06:27); agent ran `finalize --n-confirm 1`, which started a fresh 80-rollout **train** re-eval of the seed, stopped it (`TaskStop`) and wrote its final message | 1 propose, 1 screen, 0 verdicts | `end_turn` after 48 turns, `rounds_booked 0 of 50`, `eval_abandoned` (events.jsonl last line); 404 rollouts counted, of which ~160 were the host's post-agent seal step re-evaluating the seed on train (decisions.md, "E10 agent-optimize s1 ended") |
| **s2** (`A/s2`) | baseline val-40 (0.684) + train-80. `propose cand_1` (same format-contract idea). Two 20-task screens 0.80 / 0.85. `promote` 04:44; polled with `sleep 30 x19` loops for ~2 h; agent says "20 of its 120 rollouts done, about 12 rollouts an hour", finalize timed out | 1 propose, 2 screens, 0 verdicts | `end_turn` after 51 turns, `eval_abandoned` on cand_1; 380 rollouts |

Token split (my tally over each `transcript.jsonl`; poll turn = the turn's tool call contains `sleep`, `pgrep` or `tasks/`):

| seed | turns | poll turns | `cache_creation` in poll turns | in all other turns | guard-counted total |
|---|---|---|---|---|---|
| s0 | 74 | 53 | 3,583,547 (91%) | 355,488 | 3,958,447 |
| s1 | 39 | 18 | 836,953 (86%) | 138,910 | 990,763 |
| s2 | 50 | 24 | 1,198,124 (75%) | 388,040 | 1,602,367 |

(Hill-climb on the same suite: 87,560-649,254 non-cache tokens for 2-14 candidates, i.e. ~45-52k per candidate; `analysis/out/searchtime/runs.csv`. AO's non-poll cost per candidate was 3-8x that, because it reads SKILL.md, the 35 kB briefing, the digest and raw traces; but the dominant AO cost is polling.)

### 1.2 Suite B (tau2 retail, opt-49, budget 550 rollouts, 10 "candidates")

All three seeds began on the legacy round loop (3 parallel siblings screened on 12 tasks each: `cand_1..3__screen1`, +1.5 h), were archived to `legacy_attempt*/`, then restarted on the new engine at ~+4 h **[V: events.jsonl, manifest `agent_optimize_engine`]**. The new-engine part:

| seed | candidates | evaluations | end |
|---|---|---|---|
| **s0** | cand_4 (abandoned eval, 20 tasks), cand_5 (policy checklist + item-swap + address guards; fixed 6 broke 4), cand_6 (**byte-identical repeat of cand_5**) | cand_5 full val 0.633 vs seed 0.604 -> promote "indecisive" -> killed as "within-noise +0.04"; cand_6 full val 0.6875 then a 1-task probe and a 2-trial seed probe; agent's own summary: 0.582 vs 0.604 | `end_turn` after 12 turns; **198 of 550 rollouts** counted (148 search); final message: "I read the stop condition's '10 candidates' as a cap, not a target, and stopped early" |
| **s1** | cand_10 (abandoned, 20 tasks), cand_a (checklist + `list_user_orders` tool), cand_b (pre-auth transfer guard) | cand_a full val 0.653 raw vs 0.612 -> indecisive, later 0.580; cand_b 0.592 -> pruned | `end_turn` after 19 turns; "booked 1 of 10 rounds"; 172-197 of 550 rollouts; "Optimizer spend is $5.10 of $40 and 172 of 550 rollouts, so I stopped well short of the budget" |
| **s2** | cand_a, cand_x (both abandoned), cand_1 (0.592), cand_4 (**0.755 screen**, +0.143) | cand_4 `promote` (3-trial confirm, 147+147): first attempt timed out at one worker, restarted at 8 workers; confirm of cand_4 = **0.660** vs seed 0.612 (screen 0.755 -> confirm 0.660: the winner's-curse shrinkage rule P exists to remove); seed re-measure of 147 rollouts in flight | still running (319 rollouts at the analysis snapshot); the only AO seed with a pending verdict |

Two timeline facts: B s1 spent +5.4 h -> +9.1 h (3.7 h) between the cand_a screen and its promote decision, and +9.96 -> +13.67 h on one 49-rollout full-val screen of cand_b; B s2 spent 4.5 h on one 49-rollout screen (+13.0 -> +17.5 h). I.e. one serial full-val eval per ~3-4 h.

### 1.3 Suite C (tau2 airline, opt-20, budget 550)

| seed | candidates and evals | end |
|---|---|---|
| s0 | cand_1 (guards + two read tools + 8-rule checklist): 20-task screens 0.60, 0.60; cand_2: 2 trials = 0.575. Agent: "Each probe costs hours, so I'm finalizing" | `end_turn` after 27 turns, 100 search rollouts of 550 |
| s1 | cand_1 0.65, cand_2 0.70 -> 3 then 2 trials = 0.625; promote "indecisive" (+0.10 vs SE 0.114); "Unspent budget: far from exhausted, 110 rollouts used. The digest's last suggestion was to finalize" | `end_turn` after 8 turns (this session), 100 search rollouts |
| s2 | cand_1 0.526 -> 0.45 on repeat; "ignored the '10 candidates' stop wording because spend.py flagged it as unparseable" | `end_turn` after 23 turns, 61 rollouts |

Hill-climb on C, same budget class: 280-400 rollouts, two of three seeds improved (+0.15, +0.134) **[V: summary.md]**.

---------------------------------------------------------------------------------------------------

## 2. Root causes (design flaw vs configuration vs prompt)

| # | Symptom | Root cause | Class | Evidence |
|---|---|---|---|---|
| R1 | Token blow-up (A: 1-4M, 5-45x HC; guard hit in s0) | The LLM **is the scheduler**: it holds a conversation open while rollouts run, and a poll turn after a >5 min sleep re-bills the entire context as `cache_creation`. 75-91% of guard-counted tokens are poll turns (table 1.1). The guard counts `input+output+cache_creation` (`_tools/token_watchdog.py` accumulation line), so the idle loop is exactly what it counts. | **Design** | transcripts; `token_watchdog.py` |
| R2 | Abandoned evals / early stop in A (s1, s2) | (a) Every eval verb is a **blocking subprocess** run from the agent's Bash tool (`act.py:sh()`, `probe` at `act.py:329-380`, `promote` `act.py:512`); anything > the tool's limit is backgrounded and then killed at ~2 h (observed 04:26:33 -> 06:27 in s1 and the same in s0/s2) **[the 2 h limit's origin is [U]; only its observed effect is verified]**; the driver prompt promises a 4 h foreground (`host.py:278`) but the agent had already switched to backgrounding after a 600 s timeout. (b) A rule-P confirmation is a single un-chunked 240-rollout verb (`judge_p`, `act.py:463-503`): at 10-45 rollouts/h it needs 5-24 h. (c) When the agent runs out of patience it ends its turn; `host.py` has no loop around the agent (`host.py:1292`, retry only for `api_error`, `host.py:1385`), so the process exits, orphaning the eval (`_dangling_eval` -> `eval_abandoned`, `host.py:876,917`). | **Design** (a,b,c) | host.out `dangling_eval`; s1 transcript lines 303-338, 633; s2 final message |
| R3 | "rounds_booked 0 of 50", "stopped with rounds to spend" | `host.py` judges completion with `rd.spent.iterations` vs `budget.max_iterations` (`host.py:1376-1377,1431`), a counter that `commit.py` bumps per **legacy round**. The new engine never books rounds (`act.py:prune` even *undoes* the reject count), so every new-engine run reads as "incomplete"; the diagnostic is noise and hides the real cause. | **Design** (stale host logic) | host.err; B s1 "1 of 10 rounds" |
| R4 | No promotion in any seed | Not the proposer (see 0.1). Promotion needs rule P's confirmation, 240 rollouts for a 40-task val, = 40% of the 600 budget and 8-24 wall hours at the observed rate, on a budget where the baseline (val-40 + train-80) already took 120. A single candidate that passes the screen consumes the whole run. The incumbent's fresh block is re-measured for every candidate (`act.py:476-481`). In B/C the agent additionally treated "indecisive" as final: under rule P a screen reject with positive mean is mapped to verdict `indecisive` (`act.py:494-495`), `p_beat_champion` is hard-coded 0.0 on that path (`act.py:502`), and the agent then pruned (B s0 cand_5/cand_6, B s1 cand_b, C s2 cand_1) — a prune on an inconclusive verdict that the SKILL table forbids (row "gate verdict inconclusive": "not a reject... never `prune` on it"). Several of these screens were 1 trial on a noisy split (C: SE 0.11-0.114 on 20 tasks; minimum detectable effect 0.14-0.2 per the agents' own digests), so "indecisive" was the right statistical reading but the wrong action. | **Design** (cost of P) + **prompt** (indecisive treated as final) | `act.py:463-553`; B s0/C s2 `kill` decisions with reason "within noise" |
| R5 | "10 candidates" read as a cap (B/C), "40 rollouts" read as a ceiling (A) | `stop_condition` is free prose parsed by regex at runtime (`ao/spend.py:173` -> `ce/constraints.parse_constraints`). On the Suite A string, `parse_constraints` returns a predicate `max_metric_calls <= 40` (from the definitional sentence "one full-val evaluation is 40 rollouts", `constraints.py:192`) and `ambiguous` for the real 600 **[V: I ran it]**; on the B/C string it returns *no* predicate and `ambiguous` "'10' has no recognized unit" **[V]**. The agent resolves the ambiguity itself (briefing: "pick the most conservative reading", `driver_prompt.md` "Unattended"), and the conservative reading of "stop ... after 10 candidates" with a 2-candidate history is "I may stop". Spec also has `max_iterations: 10` (`B/s1/project/capevolve.yaml:35`) and the host reports it as "rounds budget". | **Design** (prose as control) + **config** (the string) | constraints run above; B s0/C s0 final messages |
| R6 | Soft guard ignored (A s0) | Soft stage = `RunDir.update_budget(max_metric_calls := spent)` (`token_watchdog.py`), "the method finalizes by its own rules". The only enforcement is `check_budget()` at the **start** of a verb (`act.py:120-131`); s0's agent was inside an already-running `probe`/`promote` and a `sleep` loop, never calling a spending verb, so it never observed the freeze (digest not re-read). The hard kill 49 min later was the only effective control. | **Design** (advisory budget on an agent that is blocked) | `events.jsonl` +20.34 h `token_guard_soft`; s0 transcript tail |
| R7 | Read denied, SKILL.md read through Bash | `Read` outside cwd is not allowed in the sandbox (`permission_denials` in host.out); harmless but it shows the briefing/skill path assumes tools the sandbox does not grant. | **Config** | host.out `permission_denials` |
| R8 | Repeated candidates (B s0 cand_6 = cand_5) | The only memory is files the agent chooses to read (`JOURNAL.md`...). No structured "this diff hash was already evaluated" check at `propose`. (`eval_index.cap_hash` exists and the ledger would let `propose` refuse a byte-identical capability.) | **Design** (missing guard) | B s0 summary |
| R9 | Agent ignores the digest | `followed_digest: False` on most B/C decisions (events.jsonl). Digest suggestions are advisory text; the agent's parent/prune choices are unconstrained. | **Design** | B/C events |
| R10 | Wall time | Baseline train-80 for an algorithm that never uses train (1.0); one serial verb at a time; session restarts between 4 h gaps in B (events `host_context`). | **Config + design** | §1 |

What is *not* the problem: the gate (rule P was never even reached), the proposer's edit quality (first candidates beat the seed on screen in 3/3 Suite A seeds, and cand_a/cand_4 in B), pregate, the digest content.

---------------------------------------------------------------------------------------------------

## 3. What already exists, and what is missing

| Feature | Implemented? | Where | Gives you |
|---|---|---|---|
| `dag_parallel` (default on) | Yes, as `--parent` freedom on `propose` | `act.py:183-244`, `optimizer_config.py:33-34`; off => parent = best_id (`act.py:189`) | A candidate DAG with multi-parent nodes. **Not** concurrency: nothing launches two branches at once. |
| Candidate graph | Yes | `ce/graph.py`, `ce/candidate_graph.py` (query layer over `graph.jsonl`), `ce/schema_v2.py` | Persistent, append-only, last-record-wins nodes; tips, ancestry. |
| `active_eval` (default **off**) | Yes, allocator only | `act.py:256-270` (`probe_ids`), `ce/sched.pick`, `ce/posterior.py` | Subset evaluation by variance-reduction: posterior `Pair` (Beta per task), `pick` chooses (arm, task) cells. Without it `probe --auto` runs full val (`act.py:267-269`). |
| Successive halving across siblings | **Not wired.** `sched.halve`, `sched.next_budget`, `STAGES=(40,100,270,450)` are called only from `ao/ablate.py:162,362` (a replay simulator). Live use is one line of digest text (`PROBE_AT = 0.3`, `digest.py:46,395`). | `ce/sched.py:81-91` | The algorithm is written and simulated; no live caller. |
| Concurrent evaluation | Partially: cell claims make concurrent `probe`s of the same (cap_hash, task) cell safe (`claim_cells`, `act.py:286`), which only matters if the agent backgrounds two probes; the briefing caps background Bash calls at 2 (`host.py:145`, `driver_prompt.md` "Cap concurrent background Bash calls at 2"), and the agent in practice ran 0-1. | `act.py:286-326` | Safety for parallelism that nothing creates. |
| `smart_merge` | Yes | `act.py:583-618`, `ao/merge_n.py` (`plan`, `wins_from_run`), `ao/merge_verify.py`, digest `merge_opps` (`COMPLEMENTARY=0.5`, `digest.py:47,250`) | N-way function-level merge plus an interaction check, with a verification the promote verb demands (`act.py:518-531`). Never exercised in any AO campaign run (zero `merge` decisions in A/B/C events). |
| Promotion | Rule P shared with hill-climb (`ce/promotion.py`, `act.py:463`); stock gate = `reward_gated` (Bonferroni z 2.734, SE floor 0.031; audit §3) | | Same decision function as HC; only the cost differs. |
| Budget enforcement | `RunDir.budget_exhausted` (`ce/rundir.py:368-383`) checked at verb start | | Refusal at the start of spends only. No reservation for in-flight jobs. |
| Resume | `cap-evolve run --resume` for the baseline; evidence ledger lets a re-run skip cells | | No resume of *agent control*: conversation state is lost with the process. |
| Headless guarantees | Detection after the fact (`eval_abandoned`, `incomplete` text, `background_mass_kills`, watchdog) | `host.py:117-278, 876-927, 1431-1500` | Warnings; no prevention, no recovery. |

**E32-ao.** `scripts/E30/launch_e32_ao.sh` builds the E30-PT airline project, sets `algorithm_skill: agent-optimize`, `orchestration_mode: agent`, `optimizer_max_turns: 300`, `max_optimizer_usd: 40`, `optimizer.ablation: {dag_parallel: true, active_eval: true}` and the identical `stop_condition: "stop when the rollout budget (max_metric_calls) is exhausted or after 10 candidates"`, with the **stock gate** (no `promotion_*`), 300 counted rollouts, 4M token guard, launched by `cap-evolve run --agent-driver claude-code` **[V]**. It is not a new engine; it is the B/C engine on airline with the same stop wording and the stricter gate (`reward_gated` z 2.734). Not started: `runs/E32/` contains only `_sbx_bin` **[V]**. Expect the Suite B/C failure modes again (R4, R5, R2) unless the changes in Section 4 land first, and expect the stock gate to be even harder to pass than rule P. Tested: the engine was unit-tested (`core/tests/test_digest_and_act_verbs.py` etc.) and replayed in `ao/ablate.py` (simulation); its first end-to-end live runs are the campaign runs analysed here.

What is missing, in one list: (1) a scheduler/driver that is not an LLM conversation; (2) evaluation jobs that are asynchronous, chunked and durable; (3) live successive halving; (4) concurrent branches with budget *reservation*; (5) stop and budget rules in code, not prose; (6) a recovery path for an interrupted run (open evals, interrupted finalize); (7) a duplicate-candidate guard; (8) incumbent confirmation reuse (cost); (9) a merge trigger.

---------------------------------------------------------------------------------------------------

## 4. Design: AO-2 = "conductor" (code) + bounded LLM jobs

Principle: **the LLM proposes and judges content; code decides everything that involves time, money or statistics.** No component waits inside an LLM conversation.

### 4.1 Control loop and split of responsibilities

```
supervisor (shell, 10 lines)  ->  conductor.py run --run-dir R --project P      # exits 0 only when DONE
     until conductor exits 0: sleep 5; conductor.py run --resume                 # crash/kill/OOM safe
conductor tick (pure function of files, ~every 5 s or on job completion):
  1. reap     finished eval jobs / proposer jobs -> ledger rows, graph nodes, conductor.json
  2. promote  for each node with full-val coverage and screen pass and no confirm job: queue rule-P confirm
  3. merge    if digest.merge_opps has a pair A,B not yet merged: build merge node (merge_n.plan), queue its probe
  4. rungs    for each node: next rung via successive halving (4.4); keep the eval pool full
  5. propose  if proposer slots free AND budget allows AND (#alive nodes below target): start a proposer job
  6. stop?    stopping rule (4.8) -> drain, finalize, exit 0
```

| Owner | Does |
|---|---|
| **Code (conductor)** | parent choice, which cells to evaluate and when, parallelism, rung promotion, rule-P promotion, merge triggering and rebase, budget reservation, token/USD/wall limits, stopping, finalize, recovery, duplicate-candidate refusal |
| **LLM job: propose** | given parent dir + hypothesis (cluster, tasks, exemplar trace ids) + last `digest` + siblings' per-task win/loss: edit `work/TAG`, write `hypothesis.json` and a 5-line journal entry. Bounded: `--max-turns 40`, token cap per job, no waiting. One-shot process via `skills/optimizers/run-optimizer/scripts/run.py` (the same call HC makes). |
| **LLM job: diagnose** | `phases/diagnose --cluster v2` already exists; run by code once per champion change, not by the agent. |
| **LLM job: merge-resolve** | only when `merge_n.plan` reports conflicts: "reconcile these two hunks", bounded. |
| **LLM job: judge (optional, off by default)** | structured JSON "which of these 3 hypotheses to try / which branch to continue", given the posterior table. Advisory: the conductor clamps it to the allowed set. |

Why this fixes R1/R2/R6/R9: there is no polling turn (tokens drop to the work turns, 0.14-0.39M per seed in A => ~150k per proposal); the host cannot "end its turn" because there is no long-lived agent turn; the budget is enforced by the only spender.

### 4.2 Graph data structure

Reuse `graph.jsonl` (`ce/graph.py`, append-only, last-record-wins) and `CandidateGraph`; add fields (schema is additive, no migration):

```
node: id, parents[1..k], edit_kind {edit|merge|rebase}, hypothesis_id, branch_id,
      cap_hash, status {proposed|rung0|rung1|rung2|full|confirming|champion|pruned|superseded},
      rung {r, cum_rollouts, tasks_seen}, post {mean, se, p_beat_parent, p_beat_champion},
      wins {task->delta sign} (for merge), cost_ledger {...}, created_by {job_id}
```

`branch_id` = lineage root (first non-champion ancestor); a merge node lists both parents and gets the lower `branch_id`. `conductor.json` (new, `ce/conductor_state.py`, atomic write via tmp+rename under `rundir._file_lock`): `jobs{job_id: kind, tag, cells, pid, state, started, reserved_rollouts, reserved_tokens}`, `budget{rollouts_committed, rollouts_reserved, tokens_committed, tokens_reserved, usd...}`, `epoch` (champion changes), `proposals_since_improve`.

### 4.3 Parallel candidate scheduling

- Pools: `S_eval` evaluation slots (= spec `gateway_max_concurrency`, the real shared resource) and `K_prop` proposer slots (default 2; each proposer job is an independent process in its own `work/TAG`; proposers are token-bound, not slot-bound).
- Eval jobs are **chunked**: a job = (tag, list of cells, trial index) of at most `chunk = 20` rollouts (= `sched.ROUND`), run as a subprocess `evaluate/run.py --topup-to` with `CAPEVOLVE_WORKERS = share`. Chunks are short (≤ ~1-2 h at 10 rollouts/h; 20 rollouts), so no job exceeds any tool or session limit, a kill loses ≤ 1 chunk, and the ledger is the checkpoint. A rule-P confirmation is just 6 chunk-sets, scheduled like any other.
- Priority queue of chunks: (1) the confirmation chunks of the node closest to promotion, (2) rung-k chunks ordered by posterior `p_beat_parent` (Thompson draw), (3) rung-0 chunks of new nodes. Fill slots greedily so the pool never idles (in A the pool was idle while the agent ran 24-31 min of 'thinking and editing' per candidate and between sessions in B).
- Budget reservation: before launching a chunk, `reserved += chunk`; a launch is refused if `committed + reserved + finalize_reserve > max_metric_calls`. This is what lets *parallel* jobs respect the budget (today `check_budget` only checks at verb start).
- Shared cells: reuse `claim_cells` (`act.py:286`) unchanged.

### 4.4 Minibatch / successive-halving evaluation policy

Rungs use already-written code: `sched.pick` for *which* cells, `sched.halve`/`STAGES` for *who survives*.

- Rung 0 (screen): 10-20 rollouts, 1 trial: all hypothesis tasks (from the cluster, the digest already knows them, ≥2 tasks) + canary tasks (parent-stable, `posterior.CANARY_MIN`) padded with `sched.pick` allocator cells. The parent's cells come free from the ledger (baseline = 1 trial of every val task), so a rung-0 chunk costs only candidate rollouts.
- Rung r+1: cumulative `sched.STAGES = (40, 100, 270, 450)` rollouts (candidate+parent arms interleaved by `sched.pick`). After each rung, among *alive siblings at the same rung* keep `halve()` = top half by `p_beat` above the futility bar `P_REJ` (0.10; 0.25 after 100 rollouts). A solo candidate is pruned only at the posterior's own prune rule (`posterior.MIN_USED = 40` rollouts) — **never by one 10-task minibatch**; below that the minibatch can only *rank* siblings, not kill (statistics in 5.3).
- Full-val coverage (`promotion_min_coverage 0.95`) is reached by the rungs themselves (the ledger accumulates); a node reaches `full` only if it survived to rung 2; this is where the 40-task screen of the present AO (40 rollouts per candidate regardless of merit) is replaced by ~10 + 10 + 20 on average.
- Output of rung evaluation is **screen-grade only**: it is never passed to a gate as a result (SKILL.md invariant "never hand a subset result to gate_check").

### 4.5 Promotion rule

Rule P unchanged (`ce/promotion.py`, same `PromotionParams` from the spec; HC-parity is a recorded decision, decisions.md 2026-10-11 10:25). Invoked by code on a node with full-val coverage and screen pass (`promotion.screen`: mean Δ > k_se·SE over paired full-val deltas). Cost-only changes, decision unchanged:

1. **Chunked** confirm (above) so it is interruptible; decision computed once all `2·n_conf·T` fresh cells are in.
2. **Fixed-seed pairing** exactly as `judge_p` (one offset k0, `fixed_seeds`), so replays are deterministic.
3. *Optional, flag `promotion_reuse_ref_block` (default off for paper runs)*: reuse the incumbent's fresh block for up to 2 consecutive candidates against the same incumbent. Saves 120 of 240 rollouts on the second attempt. It does not bias each decision (the reference block is independent of that candidate's selection) but correlates decisions across candidates; must be validated with `ablate.py`-style replay before enabling.

For the stock-gate arms (E12/E32) nothing changes: `judge()` (`act.py:388`) stays a selectable gate.

### 4.6 Branch merge operator

- Trigger (code): two alive nodes A, B, each at rung ≥ 1 with `p_beat_parent ≥ 0.5`, with `complementarity(wins_A, wins_B) > 0.5` (`digest.complementarity`, `digest.COMPLEMENTARY`), neither an ancestor of the other, and the pair not already merged. Also **rebase**: when the champion changes, every alive tip whose parent is the old champion is queued for `merge(tip, new_champion)` (same operator, so stale branches continue instead of dying).
- Build: `merge_n.plan(tags, dir_of, graph, touched_tasks, wins, all_tasks, out_dir, run_dir)` (fold + interaction + probe price). On conflicts, a bounded LLM merge-resolve job. `pregate` runs on the result.
- Verify: `merge_verify` is already required before `promote` (`act.py:518-531`); keep it as a blocking chunk-set (it needs P, A, B, M arms; the cost is in `merge_verify.py`).
- Evaluate: the merge node goes through the same rungs, but rung 0 = union of A's and B's win tasks + canaries (`eval_request` from `merge_n.node_record`), then the same rule P vs the champion.
- Budget cap on merging: at most `max(1, 20%)` of proposals are merges until one merge has been promoted or pruned (avoid a merge loop).

### 4.7 Branch continuation (parent selection)

Thompson sampling over *eligible* nodes (alive, not pruned, rung ≥ 0): sample the node's mean from the posterior (`posterior.Pair.draw`), weight by `p_beat_champion`. Constraints that guarantee the reduction to hill-climb: slot 0 of every proposal batch is always "child of the champion" (exploit); slot 1.. are children of the best non-champion alive tip with `p_beat_champion > 0.2`, or of a merge. A tip that produced `STUCK_ATTEMPTS = 3` failed children is dropped (`digest.STUCK_ATTEMPTS`). Duplicate guard: `propose` refuses if `eval_index.cap_hash(work/TAG)` equals any evaluated node's hash (fixes R8).

### 4.8 Stopping rule (code-only; prose `stop_condition` is informational)

Stop proposing when any of: (a) `rollouts_committed + reserved + (one rung-0 chunk) + finalize_reserve > max_metric_calls`; (b) `tokens_committed + proposer_cap > token_budget - finalize_tokens`; (c) wall deadline (`deadline_utc` spec key; E10 has a 2026-10-13 06:00Z cutoff, which today's runs only discover when they are killed); (d) `stop_at_reward`; (e) plateau: no champion change and no alive node with `p_beat_champion > 0.2` for the last `N_plateau = max(6, 0.4·budget_proposals)` proposals **and** at least 40% of the rollout budget spent. Never stop on candidate count unless a numeric `max_candidates` key is set. Then: drain (finish in-flight chunks of the node nearest promotion, cancel the rest), `finalize`, exit 0. Replace `spend.py`'s regex pass by structured keys only (`ao/spend.py:173`): if `max_metric_calls` exists in the spec, the prose is not parsed; fix `ce/constraints.py:192` to ignore definitional sentences ("is 40 rollouts" after "evaluation").

### 4.9 Token-budget control

- The conductor is the only spender of optimizer tokens: each proposer/merge/judge job has `--max-turns` and a token cap (default 150k non-cache; A's non-poll cost per candidate was 139-388k, so the cap is below the present cost and forces a smaller briefing: digest ≤ 1.5k tokens, parent diff, hypothesis, no SKILL.md reading, the 35 kB briefing replaced by a ≤ 3 kB proposer prompt).
- Accounting at job boundaries from the CLI's own result record (`usage.cache_creation_input_tokens + input + output`, the same quantity the watchdog counts) plus the gateway-log watchdog as an independent backstop (existing `token_watchdog.py`, unchanged; its hard kill should never fire).
- Soft stage = the conductor stops *starting* proposer jobs (in-process check, no reliance on an agent noticing). Hard overshoot bound: one job cap (150k), versus the 197k overshoot HarnessLens showed when parallel sessions were reserved at once (decisions.md) and the 49 minutes of un-stopped token use in A s0.

### 4.10 Headless robustness (no reliance on an agent ending its turn correctly)

1. No long-lived agent turn exists. Proposer jobs are one-shot; if one exits without a candidate, the job is "failed", counted, and the conductor continues (budgeted retries ≤ 2 with a stricter prompt).
2. Every eval chunk is a conductor-owned subprocess with a pid file; `reap()` handles exit codes; a chunk that exceeds `chunk_timeout` (≥ 3x expected) is killed and re-queued (cells already in the ledger are kept).
3. The supervisor loop re-launches the conductor on any non-zero exit; `conductor.lock` (flock) prevents two instances.
4. `host.py --engine conductor` replaces the agent-session driver for the new engine; the old behaviour stays as `--engine agent` for ablation (A/B vs the old AO is an E17 arm).

### 4.11 Resumability

`recover()` at start: (i) jobs in `conductor.json` with state `running` and dead pid -> `lost`, refund the reservation, re-queue (the ledger decides what is still missing); (ii) every `eval_start` without `evaluate` in `events.jsonl` -> `eval_abandoned` immediately (today detected only after the host exits, `host.py:1396-1409`) and re-queued; (iii) a `finalize.intent` file written before the test attempt: if test rollouts exist and `final.json` does not, **complete the finalize from the existing test rollouts** instead of failing — today a half-run finalize forces `CAPEVOLVE_ALLOW_TEST_RESCORE=1` (B s0 and B s1 both had this: `rundir.py:176,441`, final messages). Test is still scored at most once.

### 4.12 Files to change / create

| File | Change |
|---|---|
| `ao/conductor.py` (new) | tick loop, recover(), supervisor entry, stop rule. |
| `ao/policy.py` (new) | pure `next_actions(state, graph, ledger, budget, rng) -> [Action]`: rung promotion (calls `sched.halve`), Thompson parent choice, merge trigger, proposal slot logic. Unit-testable without a clock. |
| `ao/proposer.py` (new) | build the ≤3 kB proposer prompt, call `run-optimizer`, validate output (pregate, duplicate hash), return a node. |
| `ce/conductor_state.py` (new) | `conductor.json` schema, atomic save, reservation arithmetic. |
| `ao/host.py` | `--engine {conductor,agent}`; conductor default when `optimizer_config.new_engine`; drop the `rounds_done`/`rounds_budget` "incomplete" text for the conductor path (`host.py:1431-1500` stays for `agent`); briefing replaced by `proposer.py`. |
| `ao/act.py` | factor `judge_p` into `promotion_confirm_cells()` (list of cells) + `promotion_decide()`; add `probe --workers N`; `propose` rejects duplicate `cap_hash`; keep the six verbs for manual/interactive use. |
| `ce/sched.py` | no algorithm change; add `rung_cells(P, rung)`; make `halve` take the per-rung bar. |
| `ao/spend.py`, `ce/constraints.py:192` | structured budget first; ignore the definitional-sentence pattern; "N candidates" -> `max_candidates` only when explicit. |
| `ce/optimizer_config.py` | new switches `conductor` (default on in new_engine), `rungs` (off => full-val screen), `parallel_branches` (K), so each part is ablatable. |
| `ao/measure.py` / `act.py finalize` | complete-from-existing path; `finalize.intent`. |
| `skills/algorithms/agent-optimize/SKILL.md` | rewrite: it describes the proposer's job (edit rules, forms) and the conductor; the "loop you own" section goes. |
| Campaign: `_tools/run_ao.sh`, `scripts/E30/launch_e32_ao.sh` | baseline val-only for AO (skip train-80), `stop_condition` string removed or numeric, supervisor loop, `deadline_utc`. |

### 4.13 Tests to write

1. `test_conductor_resume_equals_uninterrupted`: fake evaluator (deterministic per (hash, task, trial)), stub proposer; run to completion, and again with a SIGKILL at a random tick; final graph, ledger and champion identical.
2. `test_no_early_stop_on_prose`: stop_condition containing "after 10 candidates" and "one full-val evaluation is 40 rollouts" must not set `max_candidates` or a 40-call ceiling; run ends only on budget/token/wall/reward/plateau-with-floor.
3. `test_reduces_to_hill_climb`: K=1, rungs off, merge off, champion-only parent, deterministic proposer; same sequence of accept/reject as `harness.run_step` on a recorded E10 hc ledger (`decisions` equal).
4. `test_budget_reservation_property`: random job interleavings never exceed `max_metric_calls` (Hypothesis-style loop, 1000 seeds).
5. `test_token_cap_enforced`: no proposer job starts when `remaining < cap + finalize_tokens`; overshoot ≤ 1 job cap; soft stage observed by the conductor.
6. `test_halving_policy_power`: simulate (via `ao/ablate.py` generators) true +0.10..+0.20 candidates through the rung ladder; assert the kill rate of a true +0.15 candidate ≤ 5% and that null candidates reach confirmation ≤ 25% of the time (sets the ladder's constants before the campaign uses it).
7. `test_merge_trigger_and_rebase`: two complementary tips -> one merge node; champion change -> rebase merge queued; no merge loop.
8. `test_finalize_complete_from_existing`: kill between the last test rollout and `final.json`; resume completes without a second test evaluation and without `CAPEVOLVE_ALLOW_TEST_RESCORE`.
9. `test_eval_abandoned_requeued`: an open `eval_start` after crash is re-queued and its cached cells not re-run.
10. `test_duplicate_candidate_refused`: byte-identical `cap_hash` -> `propose` refuses (B s0 regression).
11. `test_constraints_definitional_sentence`: the Suite A string yields no `max_metric_calls <= 40`; the B/C string yields no predicate and no recommendation `stop`.
12. `test_supervisor_restarts_until_done`.

### 4.14 Expected effect, quantified from the runs

| Metric | Now (measured) | AO-2 (target / model) |
|---|---|---|
| Guard-counted optimizer tokens, A | 0.99M, 1.60M, 3.96M | poll turns 0 => ≤ 0.4M of the 3 current seeds' non-poll work; at ≤150k per proposal, 8-12 proposals ≈ 1.2-1.8M **[M]**; cap 3.5M soft |
| Candidates fully screened per search (A) | 1, 1, 1 | ~8 **[M]**: budget 600 - 40 (val-only baseline) = 560; per candidate: 10 (rung 0) + 0.5·10 + 0.25·20 = 20, plus pass-rate q ≈ 0.2 x confirm 240 (no ref reuse) = 48 => ~68 per candidate => ~8. q taken from HC's screened-to-promoted ratio on A (2 of 16, `searchtime/runs.csv`); with ref reuse (4.5.3) the confirm is 120 => ~44 per candidate => ~12 |
| Rollouts unused at stop (B/C) | 350-380 of 550 (B), 440-490 of 550 (C) | 0 (budget-exhausted or plateau-with-floor only) |
| Search wall time in A that is baseline | 9.3-11.7 h of ~20 h | -5.6 to -7.5 h by skipping train-80 (s1: 20,241 s) |
| Eval pool idle / agent-blocked | all of the agent's edit time and all gaps between sessions | pipelined: proposals overlap evals; target pool utilization ≥ 90% **[M]** |
| Abandoned evals | A: `eval_abandoned` in s1 and s2 (s0 was killed mid-eval by the guard); B: at least one per seed (cand_4/cand_10/cand_a, seed re-measure); C: s0 (seed re-measure) | 0 by construction; a lost chunk costs ≤ 20 rollouts |
| Promotion events | 0 of 9 seeds | measured by the 2x2 below; with ~8 screened candidates per search and HC's observed promotion rate (2/3 seeds in A and C when the search is allowed to finish) |

---------------------------------------------------------------------------------------------------

## 5. Making AO strictly better than hill-climb (not merely equal)

### 5.1 The honest baseline claim

On the same suites, hill-climb currently *dominates* AO (A: 2 of 3 seeds improved, +0.17 and +0.10; C: 2 of 3, +0.15 and +0.134; AO 0 of 6; `searchtime/summary.md`), at 5-45x lower optimizer tokens. The first fix is to remove the machinery loss so AO-2 **reduces to hill-climb exactly** when its extras are switched off (test 3). Only then can the extras be a pre-registered improvement rather than an excuse.

### 5.2 Where agentic control adds value, ordered by evidence

1. **Multi-branch reasoning over per-task win/loss vectors (merge/rebase).** HC discards every rejected candidate. B s0's cand_5 "fixed 104, 21, 24, 43, 96, 99 and broke 37, 87, 92, 95", the exact case where a trimmed or merged variant could win; the agent tried to hand-build one (B s0 first turn). The conductor gives it for free: wins are in the ledger (`merge_n.wins_from_run`), complementarity is computed (`digest.complementarity`), and `merge_verify` guards interaction. Expected gain exists only when ≥ 2 alive branches have complementary wins — measure it, don't assume it.
2. **Targeted diagnosis from raw traces.** The format-contract fix (9 of 21 zero-reward tasks failing on reply format; A s1 final message) came from reading full traces, and it screened +0.11 at the first attempt in all three A seeds. HC's prompt contains failure indices but not the agent-style trace reading; keep the proposer's access to raw val traces (already allowed), never test.
3. **Cheaper screening than HC** (HC screens candidates at full val, 1 trial). The ladder buys ~2x more candidates per rollout [M]; a gain only if extra candidates carry independent chances (E13 DAG vs single lineage is the existing experiment for it).
4. **Structured memory against repeats** (duplicate hash guard; `hypotheses.jsonl` status) — removes a measured waste (B s0 cand_6).
5. **Adaptive noise handling**: buy replicate cells for the champion when `sd_est` is stale (the digest has this; the conductor automates it).

Where agentic control adds nothing: the accept decision. It stays rule P in code.

### 5.3 Risks that make it worse than HC if ignored (and the guard for each)

- **Minibatch false kills.** A 10-task rung has paired-delta SE ≈ 0.12-0.15, so it cannot kill an edit whose gain sits outside the batch. Guard: rung 0 contains the hypothesis tasks; rung 0/1 *rank* siblings but do not kill a solo candidate; absolute kills only through `posterior`'s rule at ≥ 40 rollouts; test 6 fixes the constants by simulation before the campaign.
- **Winner's curse across many branches.** More candidates screened => more false positives reach the confirm stage; rule P's fresh confirmation is the protection, and its cost is the budget. Log `confirm_reject` rate (B s2: screen 0.755 -> confirm 0.660).
- **Merge fabricates a combination that is not evaluated.** Required: `merge_verify` pass + rule P vs the champion; no merge bypasses P.
- **Parallelism changes the measurement.** The briefing records that concurrency moves outcomes ~0.03-0.08 (`driver_prompt.md` "concurrency is a measurement parameter"). Guard: one pool concurrency for all arms (`gateway_max_concurrency`), fixed per run, logged.

### 5.4 Experiment to claim "strictly better"

At equal counted rollouts and equal gate (rule P), arms from one code path: (1) HC; (2) AO-2 with K=1, rungs off, merge off (must equal HC within noise = the regression test in the paper's terms); (3) +rungs; (4) +K=3 parallel branches; (5) +merge/rebase; (6) old agent-session AO (the current numbers). Pre-registered metrics: champion's val gain at fixed rollouts (anytime curve), candidates screened per 100 rollouts, optimizer tokens, and promotion count; success = (5) ≥ (1) on gain at equal rollouts with a paired-seeds bootstrap CI excluding 0, and (3) shows ≥ 1.5x candidates per rollout. If (5) ≈ (2), report that the agentic extras add nothing on this benchmark — the design already leaves that outcome open.

---------------------------------------------------------------------------------------------------

## 6. Unverified or caveated items

- **[U]** Where the observed ~2 h background-task limit comes from (CLI vs wrapper vs environment); observed only as 04:26:33 -> kill ~06:27 (A s1) and "2-hour background limit" in s0's/s2's messages. The briefing says 4 h foreground (`host.py:278`, `BASH_DEFAULT_TIMEOUT_MS=14400000` in host.out `agent_env`).
- **[U]** Whether killed evals lose finished rollouts: s0/s2 say the confirmation "resumes from cached cells" ("20 of 120 done"), s1's final message says "killed runs lost their rollouts". The ledger design (`eval_index`, `claim_cells`) supports caching; check per-rollout write timing before relying on it (it determines chunk size).
- **[U]** Effective evaluation concurrency for B/C (events show `workers: 1`; manifest says 6 per search). I did not tally B/C token turns by cause; the poll-share result is Suite A only.
- **[U]** Whether anything besides the two known-good wait patterns kept the Suite B s2 session alive across 30 h (its transcript is only the last session).
- **[M]** All "expected effect" numbers in 4.14 (candidates per search, pass rates, pool utilization) are from the stated model, not measurement. Hill-climb screen pass rate is estimated from `gen/scr/prom` columns (2 promoted of 16 screened on A) and is low-confidence.
- **[V but narrow]** The poll/non-poll split uses a string heuristic on the tool call; reasonable (poll turns are by construction `sleep`/`pgrep`/`tasks/` reads) but not a labelled dataset.
- E32-ao has not run; everything said about its expected behaviour is a prediction from identical configuration.

---------------------------------------------------------------------------------------------------

## 7. Addendum: the propose job codifies recurring procedures into deterministic helpers

Goal: make the *target* agent less stochastic by moving procedures it executes unreliably (and repeatedly) out of prose and into executable code, so more failures are fixed per edit. Applies only where the editable surface allows executable files (tools, scripts and snippets in a skill package, `tools/` of a project; `capabilities` including `tools` or `skill-package`). For prose-only surfaces (`system-prompt`, e.g. Suite A) the job falls back to ordinary policy edits and this section is inert.

Evidence this is worth doing [V]: Suite A's dominant fix was a format failure the target repeated in 7-9 of the seed's 21 zero-reward val tasks (A s1/s2 final messages), and the A s1 digest labeled "inspect, write, verify, finish" as a procedure the target skipped (loops of ~62 messages without verifying). Both are recurrences of one procedure across traces, which prose only suggests to a stochastic reader.

### 7.1 Trigger (code decides, LLM may only act on it)

The conductor computes `recurring_procedures` before each propose job and puts them in the proposer prompt; the proposer may not create a helper without one:
- A *procedure* = a normalized sequence of target tool calls/steps (e.g. read-sheet -> compute -> write-cells -> verify) or an error signature (same tool error text after normalizing ids), extracted from the val failure traces the digest already clusters (`diagnose --cluster v2`; digest "same tool-error signature across tasks" row already exists in SKILL.md).
- Fire when the procedure **fails or is skipped in >= 2 distinct traces (distinct tasks)**, or recurs (is executed by hand, with variation, in >= 2 traces, including passing ones, where the variations differ in outcome). One trace never triggers.
- Data source is val traces only (never test), same as today. Task ids and gold stay out of the helper (7.3).

### 7.2 Smoke check before any evaluation (extends pregate)

`ao/pregate.py` already provides compile/static checks, hidden-write detection (`hidden_writes`, line 259), `tool_smoke` with fixtures (301) and `replay` against recorded calls (332). Add a `helper_smoke` stage, run by `propose` (second call) before the node is recorded and before any rollout is charged:
1. Import/compile in a subprocess with a hard timeout (e.g. 10 s), network disabled (reuse the optimizer sandbox's no-egress mode) and the gold/evaluator tree unreadable.
2. Run the helper on **fixtures built from recorded val traces' inputs** (the tool-call arguments and workspace snapshots of the triggering traces), not from gold: assert it returns without exception, is deterministic (two runs, identical output), writes only inside the declared output path, and produces output of the declared schema. Where the trace holds the *failing* case, assert the helper does not reproduce the failure signature that triggered it.
3. Reject if it needs a package or file not in the target environment (checked against the adapter's declared environment) [U: the check depends on the adapter exposing its dependency list; if absent, fall back to import test in the target venv].
A failed smoke leaves the node `proposed` with the pregate text (same behaviour as today's pregate failure, `act.py` propose) and costs 0 rollouts. Retry budget: 2 per proposal.

### 7.3 Lint against task-specific answers

Deterministic lint, in `pregate`, on every added or changed helper and snippet, blocking:
- no val/train task ids or their numeric/string tokens appearing as literals (match against the split ids and against distinctive literals from the triggering traces' expected values);
- no literal answers or cell values copied from traces or from the task statement (n-gram overlap of string/number literals with trace and gold-adjacent text above a threshold; the existing policy-growth check, `pregate` `_policy_bytes` at line 106, bounds size);
- no branching on task identity (`if task_id ==`, filename checks matching split ids, hard-coded paths of task workspaces);
- no reads of evaluator, golden, split or dataset paths (the sandbox already denies these, `manifest/negtest.txt`; the lint refuses the string too);
- no network calls, no subprocess spawning of the evaluator.
The proposer prompt states the rule ("general procedure only, parameterized by inputs"), consistent with the existing SKILL.md rule "General rules only, never a task id or answer". A lint hit is a pregate failure (free, retry). The lint is a necessary filter, not proof of generality; held-out behavior is what the rule-P confirmation measures.

### 7.4 A crash caused by the candidate's own code is a candidate failure

Rule: if a rollout errors because a *helper the candidate added or changed* raised, timed out or returned malformed output, the trial counts as **failed (reward 0 for that cell), not as missing/infra**. This is exactly the existing tagging used in Suite B: `errored_trial_policy: fail` with "candidate tools fault -> error_kind=candidate (score 0); provider/sim/judge -> infra" (`B/s1/manifest.json`, `gate`/`error_tagging`; policy plumbing at `ce/cli.py:757-761`, `ce/harness.py:306`). Implementation for helpers: wrap helper entry points with a decorator/shim that raises a typed `CandidateHelperError` (recorded in rollout metadata with `error_kind=candidate`); the conductor's coverage accounting treats those cells as scored 0, so a flaky helper cannot hide behind missing cells and a candidate cannot improve its mean by crashing out of hard tasks (dropped cells would otherwise inflate the paired mean or shrink coverage). Infra errors (gateway, sim, judge) remain missing and are re-queued. Add a rung rule: a helper with >= 2 candidate-fault cells in rung 0 is pruned without further rungs (cheap, deterministic).

### 7.5 Each new script is its own graph node (mergeable across branches)

- Granularity: one helper file (or one named function in a shared module) = one *edit unit*. The propose job emits, in `hypothesis.json`, `units: [{path, symbol, kind: helper|snippet|policy, triggering_procedure_id, trace_ids}]`. The conductor records one `graph.jsonl` node **per unit change** when units are independent (disjoint files/symbols), each with `edit_kind: helper`, parent = the base, `hypothesis_id`, and `cap_hash` of the node's bytes; the candidate evaluated on rungs is the base + that single unit. If a single hypothesis needs a helper and its call site in policy text, they stay one node (a unit with `requires: [paths]`).
- Why: per-unit nodes make attribution clean (which helper moved which tasks, `wins` vectors per unit), let cheap rung-0 evaluation reject bad helpers individually, and give the merge operator exactly what it handles best. `merge_n.plan` and `ao/funcmerge.py` already merge at function/block level (`blocks`, `union_insertions`, `merge3`); two branches that each add a *different file* merge trivially (pure insertion), and the interaction check (`merge_verify`) covers call-site conflicts.
- Merge policy additions: (a) two helpers solving the same procedure in different branches are *competing*, not complementary: keep the one with higher `p_beat_parent` and record the other as `superseded`; (b) a helper node that passed rule P becomes part of the champion; later proposals receive the helper catalog (path, docstring, signature, triggering procedure) in the digest so the proposer calls it instead of re-implementing; (c) a policy edit that mentions a helper is rejected by lint if the helper is not in the candidate (dangling reference).
- Regression guard: when a helper is added to the champion, its triggering traces' tasks plus canaries are in the next probe's cell set (`posterior.CANARY_MIN`), because deterministic code that is wrong fails every time.

### 7.6 Interfaces and files

| File | Change |
|---|---|
| `ao/procedures.py` (new) | mine `recurring_procedures` from val traces/clusters (7.1); output goes to `digest` json and to `proposer.py`. |
| `ao/pregate.py` | add `helper_smoke` (7.2) and `helper_lint` (7.3) to `run()` (line 419) beside `tool_smoke`/`replay`; both strict by default for tool/skill-package surfaces. |
| `ao/proposer.py` (new, section 4.12) | prompt block "procedures that recur: encode as a helper, or explain why not"; accept `units` in `hypothesis.json`. |
| `ao/conductor.py` / `ao/act.py propose` | split independent units into nodes (7.5); duplicate-hash check per unit. |
| `ce/harness.py` rollout metadata | `error_kind=candidate` for `CandidateHelperError` (7.4); coverage accounting counts them as 0. |
| target-side shim (adapter template, `templates/adapters/...`) | decorator that types helper exceptions. [U] Adapter-specific: requires a per-adapter hook; each of `examples/tau2_*`, `spreadsheetbench` adapters needs it. |

### 7.7 Tests

1. `test_trigger_requires_two_traces`: one trace -> no helper allowed; two distinct tasks with the same error signature -> allowed.
2. `test_helper_smoke_offline_no_gold`: smoke runs with network and evaluator paths blocked; helper that opens a socket or a golden path fails smoke.
3. `test_lint_blocks_task_specific`: literal task id, copied expected value, `if task_id ==`, evaluator path each fail; a parameterized helper passes.
4. `test_candidate_crash_counts_as_failure`: helper raising scores the cell 0 (error_kind=candidate); gateway error stays missing; mean cannot rise by crashing.
5. `test_unit_nodes_and_merge`: two branches each adding a different helper -> `merge_n.plan` builds a union without conflict; two competing helpers -> one superseded.
6. `test_prose_surface_is_inert`: Suite A (system-prompt only) never receives the helper instructions.

### 7.8 Expected effect and risks

[M, not measured] Value is concentrated where failures are procedural and repeated (format contracts, argument normalization, precondition checks such as "view the reservation before cancelling": C s0's cand_2 guard, which did not move val, shows a guard in tool code is a different thing from the same rule in prose, but also that a single unevaluated rule need not help). Risks: (i) overfitting disguised as a general helper — lint plus rule-P confirmation are the defences, and the ablation arm should report the share of accepted helpers whose triggering tasks account for the whole gain; (ii) a helper that is correct on val traces but wrong elsewhere fails deterministically, hence the canary rule above; (iii) added environment dependency — covered by the smoke check's environment test. Ablation: `helpers on/off` as one more switch in `optimizer_config` (default on only for tool/skill surfaces), compared at equal rollouts in the 5.4 matrix.

### 7.9 v2 surface expansion (correction to the scope sentence in section 7's opening)

Section 7's opening says Suite A is prose-only. That is true of **v1** (`capabilities: [system-prompt]`, `seed_capability/{prompt.md, task_template.md}`, `A/s1/project/capevolve.yaml`) and stays so for v1 results. In **v2** the surface is widened, so this section applies to Suite A as well. **v2 is a new registered arm: its cells are not comparable with v1 cell-for-cell** (different editable surface, different seed capability bytes, different pregate/lint, different cost per candidate). Register it as its own experiment id with its own seed score; never pool v1 and v2 rows in the ledger (`env_fp`/cap_hash differ, but the registry entry must say so explicitly).

**Suite A, v2 capability set `[system-prompt, skill]`.**
```
seed_capability/
  prompt.md  task_template.md                  # unchanged contract (placeholders validated, adapter.py:1086-1126)
  skills/<name>/SKILL.md                       # frontmatter (name, description) + body, one-level references
  skills/<name>/scripts/*.py                   # deterministic helpers, stdlib + packages already in the executor image
```
Validity rules come from the existing `skills/capabilities/skill-package` skill (valid frontmatter, progressive disclosure, scripts that compile and self-check).

**How the scripts reach the target's python, read-only, without gold (what the current code allows).** [V from reading; not run]
- The adapter in the run dir (`E10/hill-climb/s1/project/adapters/adapter.py:1-51`) is only a unix-socket client: `live()` yields the candidate dir (line 36-38), `run_target` sends `cand_dir` to the daemon (line 40-42). It holds no sandbox logic. The daemon (`_tools/eval_daemon.py:20-29, 117-122`) loads the real adapter `templates/adapters/spreadsheetbench/adapter.py` and calls `adapter.live(cand)` / `run_target(task, ctx)`.
- In the real adapter the target's code runs in a docker "codeact-executor" container (uid 1000, `adapter.py:735-740`; 8 GB / 2 CPU, `third_party/spreadsheetbench/code_exec_docker/jupyter.py:246-251`). The **only** host path the container sees is the agent view bind-mounted at `/mnt/data` (`jupyter.py:294,303`, `adapter.py:191`). Today the candidate dir is read on the host only: `prompt.md` (`adapter.py:1129-1143`) and `task_template.md` (`adapter.py:1066-1083`). **Nothing from the candidate is mounted**, so a skill's scripts would be invisible to the executed code. This is the gap v2 must close.
- Mechanism (adapter change, small): in `run_target`, before the first executor call, stage `Path(ctx)/"skills"` into the agent view at `<view>/skills/<cap_hash12>/` (copy once per hash under a lock, like `_agent_view` does under `_VIEW_LOCK`, `adapter.py:358-372`), then tell the model the path. Reasons for this placement:
  - It is outside `<view>/spreadsheet/`, the only subtree `_check_mount_is_gold_free` inspects (`adapter.py:386-432`), and it never touches gold: the view is built from allowlisted input files only (`_build_agent_view`, `adapter.py:310-355`); the staged tree must additionally pass the same allowlist rules (regular files, no symlinks, size/extension limits `*.py|*.md|*.json|*.txt`).
  - Read-only is enforced by permissions, not by the docker flag: the bind is `'mode': 'rw'` (`jupyter.py:303`) but the tree is host-owned and widened only a+rX ("deliberately NOT a+w", `adapter.py:781-790`), with the single writable exception `outputs/` (`_make_container_writable`, `adapter.py:732-750`; view build sets `outputs` 0777, `adapter.py:350-352`). The staging code must `chmod a-w` and never add write bits. [U: this relies on the host uid differing from the executor's uid 1000; if they match, the container owns the files and can write. Add an assertion in the staging step that `os.stat(...).st_uid != 1000`, or mount `skills/` as a second bind with `mode: 'ro'`, which requires changing `jupyter.py:303` to a two-volume dict and is the stronger option.]
  - Per-hash directories keep concurrent branches (AO-2, parallel candidates) from overwriting each other, but all staged hashes are visible to any rollout under `/mnt/data/skills/`. A target could read another branch's scripts. For paper-grade isolation either use one executor per candidate hash (the sandbox singleton `_get_sandbox`, `adapter.py:710`, would need a per-hash key) or accept and disclose it; the leakage is of candidate code, not of gold.
  - Discoverability: `prompt.md` gets a stable token `{skills_root}` substituted at run time with plain `str.replace` (not `.format`, so literal braces in prompt text stay safe, cf. `adapter.py:1105-1112`). The adapter appends the one-line `name: description` of each SKILL.md to the system message (progressive disclosure); the model reads a script with `open(...)` or imports it via `sys.path.insert(0, "{skills_root}/<name>/scripts")` inside its normal python tool call.
  - Network: the executor container is started with Docker defaults and no network restriction (`jupyter.py:296-306` passes none), so **"no network" is not enforced at runtime in Suite A**. It is enforced in two other places only: the pre-evaluation `helper_smoke` (7.2, offline) and the lint (7.3). State this limit in the paper.
  - Candidate-fault accounting: a script that raises inside the executor appears as an ordinary execution error in the trace; treat it as a candidate failure (the rollout is already scored from the produced workbook, so a crashed helper that leaves no output scores 0, consistent with 7.4). Adapter-side failures of the staging step itself (template-style errors) follow the existing `error_kind: "candidate"` path (`adapter.py:1499-1504`).
- Daemon/accounting impact: none on the rollout counter (`eval_daemon.py:105-116`); staging copies a few KB. Pregate runs outside the daemon and must not read the evaluator tree.

**Tau suites (B, C): same mechanism, different carrier.** [V from reading]
- The surface already includes executable code: `capabilities: ['system-prompt','tools']` (B host_context events) with `tools/tools.py`. The adapter execs the candidate file *fresh* in the harness process, `examples/tau2_airline/adapters/adapter.py:193-211` (`_load_candidate_tools_class`, unique module name per load) and instantiates the candidate `AirlineTools` class (`:215-256`), optionally removing tools via `REMOVE_TOOLS`. For retail the analogous adapter is the tau2_retail adapter (`wt-tau`, not read in this pass [U]). A "helper snippet" in tau is therefore a method or module-level function in `tools/tools.py` exposed as a tool or called inside an existing tool (precondition checks, normalization, the cancel/transfer guards the agents already wrote: `list_user_orders`, `list_user_reservations`, `get_baggage_allowance`, pre-auth transfer guard). No new mount is needed.
- Differences that change the guards: (i) the candidate code runs **inside the evaluator/harness process**, not in a container, so a lint-bypassing helper could in principle read task or db files: the lint (7.3) and the smoke sandbox (7.2) are the only barrier, and the B manifest already discloses that opt/sel gold stays readable (`E10B/ao/s1/manifest.json`, `optimizer_isolation.data_overlay`); (ii) `error_kind=candidate` tagging already exists for tool faults (`manifest.json` `error_tagging`), so 7.4 needs no new code in tau beyond the typed wrapper; (iii) skill-package scripts are not applicable (the tau target does not execute python itself), so the unit of helper is "tool or tool-internal function", and the node granularity in 7.5 is a method name in `tools.py` (merge by `funcmerge.blocks`, which splits at function level).
- Policy text may reference a helper only by tool name; the lint rejects dangling references (7.5c).

**Consequences for the design.**
1. `optimizer_config`/spec gets `capabilities: [system-prompt, skill]` for Suite A v2, and the registry entry must list the adapter diff (staging code) with its sha256 before launch.
2. New tests: `test_skill_staging_is_gold_free` (staged tree passes `_check_mount_is_gold_free` semantics; no symlinks; no file outside the allowlist), `test_skill_staging_readonly` (container uid cannot write; assert the mode bits and, in the docker integration test, a failed write), `test_skill_path_substitution` (braces in prompt.md survive), `test_concurrent_hashes_do_not_overwrite`.
3. Cost model in 4.14 changes: v2 candidates carry code, so smoke+lint add per-proposal wall time (seconds, 0 rollouts) but the proposal token cap should rise (150k -> 200k) for the first helper-creating proposals [M].
4. Claims in the paper: v2 vs v1 is a surface ablation on its own seed, not a pairwise improvement test.
