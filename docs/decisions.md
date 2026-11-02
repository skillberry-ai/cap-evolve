# exp895 decisions log (issue skillberry-ai/cap-evolve#895)

Every entry: date, decision, who decided, evidence. No credentials here.

## 2026-10-20 — Code pin
- cap-evolve `main` @ `520ecbe8b9963588eb8d53e3ae29a4ccc1f8436c` (the SHA the issue requires), worktree `sbv400-main`, branch `exp/sbv400-895`.

## 2026-10-20 — Data
- verified_400 from HF `KAKA22/SpreadsheetBench` @ `ab0b742b0fc95b946f212d80ac7771b5531272e4`, sha256 `10ef893dd29cb13ab97143ea787e68cdc9574a13873ab9a54e50b31dc03fc949`; byte-identical to the GitHub `main` copy that `fetch_data.sh` uses.
- 400 tasks; official split 80/40/280 matches `split_source.json` sorted-id sha256 digests; split covers the dataset exactly, no overlap.
- Seed v2 tree sha256: prompt.md efa493dd…3c72, task_template.md 841967…5f84295, SKILL.md 6679c3…3dae1f, scripts/.gitkeep (empty).

## 2026-10-20 — Agent (Gemma) route — DECIDED by Boaz
- **Route B, RITS `google/gemma-4-31B-it`** (instruction-tuned), deployment `google-gemma-4-31b-it-a100`, header `RITS_API_KEY`.
- **Deviation from issue §2.1**: the issue names `google/gemma-4-31B` (no `-it`). Reason:
  - route A (ete `rits/google/gemma-4-31B` -> `hosted_vllm/google/gemma-4-31B`) returns 404 on every call (probed 2026-10-20 on login5 and login4);
  - repo `ci/benchmarks/model_catalog.txt` records that id as the BASE model;
  - RITS base `google-gemma-4-31b-a100` rejects chat/completions (400: no chat template);
  - RITS `-it` answered 200 (single trivial call took ~125 s — latency to be characterised in P1 throughput probes).
  - Matches the checkpoint our previous SpreadsheetBench results used.
- Used for every arm and the final window; no mixing.

## 2026-10-20 — Optimizer (GLM) route
- Curve Bender LiteLLM serves the model as **`rits/zai-org/glm-5-3`** (issue §2.2 spells `hosted_vllm/zai-org/GLM-5.3`). Same model; we use the served id. Both `/v1/chat/completions` and `/v1/messages` (thinking disabled) answered 200 in ~1 s.

## 2026-10-20 — Compute policy — DECIDED by Boaz
- All builds, smoke runs and searches run on **dedicated LSF hosts** (never a login node). Image artifacts live in the workarea, never /tmp.

## 2026-10-20 — Scorer
- LibreOffice 25.8.7.3 (rootless RPM extract) at `exp895/tools/libreoffice/root/opt/libreoffice25.8/program/soffice`.

## 2026-10-21 — Container start reliability (approved by Boaz)
- Cause of the P1 smoke `sandbox exec failed: 500`: rootless podman start failures, not agent faults —
  (a) `rootlessport ... bind: address already in use` (vendored harness frees its port before publishing it, a race);
  (b) `pasta ... netlink: Unexpected sequence number`. Seen in runs/p1_smoke/1853801/sandbox_*.log.
- Fixes, branch `exp/sbv400-895` only: adapter patches its STAGED copy of jupyter.py to retry a failed start up to 5x with a
  fresh port (`CAPEVOLVE_CONTAINER_START_RETRY` log line; nothing charged, no LLM call made); rootless network cmd set to
  slirp4netns via per-job `CONTAINERS_CONF_OVERRIDE` (tools/containers/containers.conf). third_party/ unchanged.
- Evidence: runs/p1_churn/1892511/churn.jsonl — 40/40 starts at concurrency 8, 0 failures, 0 retries, rootlessNetworkCmd=slirp4netns,
  start p50 3.9 s, max 4.9 s.

## 2026-10-21 — P1 throughput probes (runs/p1_probe/1892653/probe_{gemma,glm}.jsonl, calls_*.jsonl)
One wave of N parallel requests per level, through the gateway, no gateway cap.
Gemma-4-31B-it (RITS), ~7.6k in / 1k out, temperature 0:
| N | ok | p50 s | p95 s | req/min | out tok/s |
|---|---|---|---|---|---|
| 4 | 4/4 | 30.8 | 30.9 | 7.8 | 129 |
| 8 | 8/8 | 28.7 | 28.7 | 16.7 | 279 |
| 16 | 16/16 | 29.9 | 30.0 | 32.0 | 533 |
| 32 | 32/32 | 39.5 | 39.7 | 48.3 | 805 |
| 48 | 48/48 | 40.4 | 40.6 | 70.8 | 1,181 |
| 64 | 64/64 | 46.7 | 47.1 | 81.4 | 1,356 |
| 96 | 96/96 | 49.4 | 49.8 | 115.2 | 1,920 |
- 268 calls, all 200, 0 upstream retries. No saturation up to N=96 (latency +60% from N=16 to 96, throughput still rising).

GLM-5.3 (Curve Bender), ~28.2k in / ~2k out, reasoning_effort=low:
| N | ok | p50 s | p95 s | req/min | out tok/s |
|---|---|---|---|---|---|
| 4 | 4/4 | 89.3 | 89.9 | 2.7 | 89 |
| 8 | 8/8 | 59.2 | 60.1 | 8.0 | 263 |
| 16 | 16/16 | 59.7 | 63.8 | 14.9 | 495 |
| 32 | 32/32 | 61.5 | 67.8 | 26.0 | 856 |
| 48 | 48/48 | 84.7 | 123.7 | 22.5 | 735 |
| 64 | 64/64 | 93.0 | 164.4 | 22.7 | 748 |
| 96 | 96/96 | 125.1 | 238.4 | 23.8 | 779 |
- 268 calls, all 200 after retry; 10 upstream ReadTimeouts (180 s gateway timeout), all in one burst (t≈679 s, during the N=64 wave), all recovered.
- **GLM saturates at N≈32**: throughput flat ~23 req/min beyond it while p95 latency climbs 68 s -> 238 s. Matches the issue's
  earlier "GLM peaked around 53 concurrent" only loosely — our ceiling is lower with 28k-token prompts.

## 2026-10-21 — P1 episode probe (runs/p1_episodes/1897272/episodes_joined.jsonl, calls_gemma.jsonl)
10 train tasks x 1 trial, concurrency 10, v2 seed, helpers ON, host cccxc577 (dedicated, span[hosts=1]).
- 10/10 scored, 0 infra; pass 8/10. 91 Gemma calls; 9.1 calls/episode mean, 4 median.
- Tokens/episode: prompt median 9,340, **mean 117,451** (heavy tail: 2 episodes hit the 30-turn cap at 351k and 751k);
  completion mean 5,619. RITS reports cached_tokens = 0, so no cache discount is assumed.
- Wall/episode as logged: median 400 s, max 1,170 s. **Every episode's FIRST call stalled ~300 s** (10 ReadTimeouts at the
  gateway's 300 s Gemma timeout, all at t+300 s, all retried and answered in 17-50 s). Non-retried call p50 = 21 s, so the
  steady-state episode wall is ~100 s median; the 300 s is a cold-burst stall to tune (gateway Gemma timeout -> ~90 s).
- Machine (cccxc577): max 10 containers, load 82.7 (host shared with others), /tmp free >= 774 GB.
- Estimate (Gemma list price proxy 0.13/0.38 $/M): ~$0.017 per episode at the mean -> ~$38 agent cost per R=2,160 search,
  ~$1.1k for 30 searches, ~$0.5k for the 27,720-episode final window. GLM optimizer cost NOT yet measured (needs P2 smoke).

## 2026-10-21 — Gateway Gemma read timeout 300 s -> 90 s
- Every P1 episode's first call stalled to the 300 s timeout, then answered in 17-50 s on retry (runs/p1_episodes/1897272).
  Steady-state call p50 21 s, p99 of non-stalled calls < 60 s. 90 s retries a stalled call ~3x sooner. Same value for every arm.

## 2026-10-21 — Spec-key audit of cap-evolve @ 520ecbe8b (+ #903) and the decisions it forced
Audited every §6 spec key against the code (survey + spot checks). Findings that change the design:
- `actions`, `dataset_source` (run tags only) and the V4 keys `cost_lambda/cost_accept/cost_metric/hc_compress_every`
  are not read: unknown top-level keys are silently dropped (specfile.read_yaml has no schema). The V4 keys are confirmed gone.
- `target_model` does NOT pick the agent model. The adapter takes `MODEL` from env. We set both and check they agree.
- `max_metric_calls` counts task x trial rollouts, seed included. **By default it is only checked between iterations**,
  so it can overshoot R by one full eval. **Decision: `budget_reserve: true`**, which reserves before dispatch and raises
  BudgetExhausted before an eval that would overshoot (harness.py:385-399, rundir.py:357). This is the hard counter §5 requires.
- `finalize` default is true and env `CAPEVOLVE_FINALIZE` overrides it. We set `finalize: false` and unset the env in the job.
- **Paired gate:** footprint gating is on by default (val tasks outside an edit's footprint get Δ=0, plus an SE floor).
  The issue's gate is "mean paired Δ > 0.5·SE". **Decision: `gate_footprint: false`**, so the gate is exactly the stock paired gate
  on the raw per-task vector. Recorded as the reading of "stock paired gate".
- **Helper lint/smoke never run under hill-climb** (only agent-optimize's pregate calls lint_candidate/run_smoke).
  **Decision (Boaz): a common gate in the shared rollout layer, identical for EVERY arm.** It runs before any rollout; a
  failing candidate scores 0 with no Gemma calls, and its full eval (tasks x k) is still debited from R.
- **The claude-code optimizer is unsandboxed** (full os.environ, Bash allowed, no CLAUDE_CONFIG_DIR). It would see
  ~/secrets, the gold data and the scorer. **Decision (Boaz): a bwrap shim** named `claude`, first on PATH: read-only system,
  only the work dir writable, a private HOME/CLAUDE_CONFIG_DIR, gold/scorer/secrets not mounted, network only to the gateway.
  Reused for every Claude-Code-driven arm (CapEvolve, EvoSkill, Meta-Harness).

## 2026-10-21 — Optimizer sandbox verified (runs/sandbox_test/1900403, logs/sbxtest.1900403.out)
- Shim `tools/sandbox/claude` runs the pinned Claude Code 2.1.304 (sha256 ea0f1357…) inside bubblewrap 0.6.3.
  Compute nodes have no bwrap, so a copy from a login node is kept at tools/bwrap/bwrap. It fails closed if absent.
- Network: --unshare-net. The only egress is a unix socket bridged to the GLM gateway (tools/sandbox/sandbox_bridge.py).
  The socket lives in a short node-local /tmp dir because AF_UNIX paths are capped at 108 bytes.
- Probes are counted only if a marker printed INSIDE the sandbox appears, and a CONTROL probe must show visible.
  - CONTROL (own cwd): visible.
  - BLOCKED: ~/secrets, ~/.claude, gold dir, a gold workbook the host can read (1_10452_golden.xlsx: cat fails),
    a filesystem-wide find for *_answer*.xlsx, the adapter's /tmp agent-view copies, the pristine dataset.json,
    the vendored scorer, other runs, the internet, the gateway port directly.
  - ALLOWED: write to own cwd; the gateway via the bridge; one real `claude -p` call -> "SANDBOX_OK" (ledger: messages 200).
- Two earlier test runs were INVALID and are not evidence: 1900196 (bwrap missing, so the probe read a launch failure as success)
  and 1900367 (`ls X | head` takes head's exit status). Fixed in the test harness.

## 2026-10-21 — Common helper gate implemented (branch exp/sbv400-895)
- adapter._helper_gate_error: cap-evolve's own lint_candidate and run_smoke, once per distinct helper tree
  (content hash, cached), before any LLM call. It is active only when CAPEVOLVE_HELPERS_SPEC names the run's
  capevolve.yaml; the launcher sets it identically for every arm. A failure returns error_kind=candidate,
  helper_gate=failed, which scores 0 and is debited (Boaz). Tests: core/tests/test_spreadsheetbench_helper_gate.py, 7 pass.
- Pre-existing test failure, NOT ours: test_spreadsheetbench_verify_turns.py::test_a_correction_supersedes_the_earlier_answer
  fails on this host at pristine 520ecbe8b too. It writes two 6-byte files microseconds apart, which get an identical
  (mtime_ns, size) stamp. Real episodes write seconds apart with different sizes, so the adapter is unaffected.
  The full SpreadsheetBench suite on the branch: 303 passed, 1 failed (this one), 5 skipped.

## 2026-10-21 — CapEvolve P2 smoke (runs/capevolve/smoke_s0, job 1903524, cccxc576)
2 train tasks (10452, 105-24) x k=3, R=60, max_iterations=1, concurrency 6. RC=0, wall 13.6 min.
WORKED (evidence in run_main/):
- k=3: 6 rollouts per eval, trial_rewards per task [1,1,1]; rollouts/val has 12 files (2 tasks x 3 trials x {seed, cand_0001}).
- R counter: spent.metric_calls=12 of 60, under budget_reserve. Iterations 1/1. Seed not re-evaluated on train (train==val note).
- Optimizer: sandboxed Claude Code on GLM produced cand_0001: prompt.md + SKILL.md edited, new skills/.../scripts/cell_ops.py
  (206 lines). The common helper gate PASSED it ("helper gate passed for tree 131156adfed8").
- SKILL.md reached the agent: the cand_0001 rollout system prompt (4,135 chars) contains the skill name and `cell_ops`.
- Gate: paired Δ=0, SE=0 -> STRICT fallback -> rejected; champion = seed. Correct, and expected on 2 already-solved tasks.
PROBLEMS FOUND (fix before any real search):
1. **GLM spend was not metered**: 34/35 optimizer calls are STREAMED /v1/messages and the gateway only parsed usage on
   non-stream replies, so the ledger has 0 tokens. cap-evolve's own estimate: optimizer_tokens=1,606,606, optimizer_usd=4.17
   (its internal price). FIX: gateway now parses SSE usage (message_start + message_delta; OpenAI final chunk) and adds
   prompt_total = cache-inclusive input tokens. Unit-checked on both shapes. Needs re-verification in the next smoke.
2. **No optimizer transcript kept**, so the §4.1 isolation scan had nothing to read. FIX: CAPEVOLVE_OPTIMIZER_TRANSCRIPT
   now points at runs/.../optimizer_transcript.jsonl (run-optimizer switches to stream-json and redacts secrets).
3. **Gemma ReadTimeouts**: 18 retries, in 3 bursts of 6 at t+90, 182 and 275 s. Each burst = the 6 parallel episodes'
   first calls. Same cold-start stall as P1, now with the 90 s timeout, and it took 3 rounds to clear. The episodes
   still finished (0 infra errors) but lost ~4.5 min. Next: probe whether the stall is per-episode-first-call or RITS cold
   start, before choosing between a longer first-call timeout and a pre-warm call.
4. Claude Code logs `unrecognized_model rits/zai-org/glm-5-3` (it doesn't know the id). Harmless: all 35 calls were 200.
   The capability validator warned that SKILL.md lacks "Use when…" and cell_ops.py lacks --self-check. These are
   advisory, did not block, and are fed back to the optimizer.
- Saturation: the 2 smoke tasks pass 3/3 at seed (headroom 0). Memory rule: a SATURATED baseline is not a real search.
  The real searches use all 120 tasks, where P1 measured 8/10 on train, so there is headroom.

## 2026-10-21 — Launch CapEvolve before the competitors are ported (Boaz)
- Decision: launch the 3 CapEvolve searches now (seeds 0,1,2; R=2,160; 120-task train=val; k=3). Competitor arms are ported
  in parallel and launched as each passes its smoke. **Deviation from §11**, which smokes every arm before P3.
  The searches are independent: same seed bytes, same R, same scorer, same gateway settings. The final window (§9) still
  runs only after ALL 30 searches are frozen, so test-time comparability is unchanged.
- Spend is not a constraint (Boaz: internal models are free). $ is still computed for the report.
- Smoke evidence before launch (runs/capevolve/smoke_s0b):
  - GLM metered from streams (13 calls, all with usage; 328,638 prompt-total tokens so far).
  - Optimizer transcript kept (517 kB, 1,821 lines). Isolation scan: 0 gold-dir, 0 golden/answer files, 0 scorer, 0 secrets,
    0 ~/.claude, 0 TEST ids. Positive control: the train id 118-50 appears 100 times, so the scan can see ids.
  - Warm-up absorbed the cold-start stall (6 warm-up calls at 295 s; 1 of 88 agent calls retried, at t+25 min).
  - Seed val 0.5 (10452 pass, 118-50 fail 0/3).

## 2026-10-21 — After the VPN outage (18:20Z): state, and the Gemma-timeout decision (Boaz: keep 90 s, no restart)
- The 3 CapEvolve searches (jobs 1913879/80/81) survived the outage and are ~2.8 h in, still in their seed evaluation (360 rollouts each).
- Gemma 90 s timeout, measured over the 3 searches' ledgers (6,800 calls): 34 calls failed after all 8 attempts (0.5%); 27 of them in the
  first 30 min (cold start), 7 after. Of 244 calls that were retried then answered, 95% of their final attempt took < 85 s, i.e. the retry
  rescues upstream hangs rather than cutting healthy calls. Clean-call latency p50/p90/p99 = 27/64/84 s (max 90). Failed cells are
  infra-missing (never scored 0, §0.3) and cap-evolve re-runs missing cells up to 2x when one could flip a gate decision.
  Decision: keep 90 s for every arm; no restart.
- Competitor workflow wf_14f851c7-15b was cut by the outage: several agents were stopped by denied file reads and returned 'blocked'
  without doing work. Results kept: gepa and gepa_full smokes PASSED (R counter, k=3, isolation 0, candidate evaluated); gepa_full job
  1917195 finished (champion = seed, 6/18 rollouts error_kind=candidate - to be explained by review) and was killed by exact id;
  trace2skill smoke job 1917534 still running. Relaunched as wf_a241c299-377 for the 7 unfinished arms + review of gepa and gepa_full.
- Common layer, backwards-compatible additions (asked for by the ports): TaskResult.infra (still-infra trial; its 0.0 is a placeholder),
  TaskResult.traces (every trial's transcript), evaluate(split=...) so rollouts.jsonl rows carry the right split.

## 2026-10-21 (Opus re-verification, ~19:30Z) — two correctness fixes in arms/common/rollout.py
Re-checked every Sonnet-era change before Boaz went offline. The 3 CapEvolve searches are correct: spec per seed, 120-id split ==
official train∪val with 0 test overlap, gated adapter (sha c035c75e…), budget_reserve active (360 reserved for val/seed).
Two bugs found in the COMMON rollout (affect competitor arms only; CapEvolve uses cap-evolve's own harness):
1. **Infra-missing trials were averaged in as 0.0**, which violates §0.3. `TaskResult.mean` now averages MEASURED trials only. A task
   with no measured trial is `.missing` and `EvalResult.mean` drops it. Unit-tested with a fake adapter: infra trial excluded,
   all-infra task dropped, candidate error = real 0, refund correct.
2. **Trial seeds collided.** The issue's 10_000*seed + 100*call + trial wraps into the next seed once an arm makes >= 100 evaluation
   calls (GEPA minibatches do), and the +1000*attempt retry term collided too: 23,070 collisions over the reachable space (seed<=2, call<720, attempt<=3, trial<3).
   **Deviation from §5, recorded:** trial_seed = 1_000_000*seed + 1000*eval_call + 100*attempt + trial, which gives 0 collisions
   for seed<=2, call<720 (R=2160 / 3), attempt<=3, trial<3. CapEvolve's own harness seeds trials as base_seed + k (its native
   convention), so "one convention for every arm" holds only across the competitor arms. Reported, not hidden.
- gepa / gepa_full smokes ran on the OLD rollout.py (before both fixes). Their smokes had 0 infra trials, so fix 1 did not change their
  numbers. Their seeds came from the old formula, which is fine for a 3-call smoke. Every real search runs on the fixed file.
- **Known shared limitation, NOT fixed (so every arm stays identical):** adapter.score() labels EVERY errored rollout "Infrastructure
  error ... do not optimize against it", including candidate-caused ones (helper gate, template contract, helper crash). Scoring is
  right: these count as 0 under errored_trial_policy=fail and in CommonRollout. Only the feedback TEXT shown to optimizers is
  misleading. A fix was written and reverted: the 3 live CapEvolve searches load a frozen adapter copy (sha c035c75e…), so a fix
  would give competitors different feedback from CapEvolve (§0.4). Same handicap for all arms. To be fixed for all arms at once if
  searches are ever restarted.

## 2026-10-22 ~05:30Z — Competitor searches launched (Boaz: "launch the competitor searches; we discuss the gate after")
- 24 searches: {gepa, gepa_full, skillopt, evoskill, trace2skill, meta_harness, wikiskill, ace} x seeds {0,1,2}, R=2160, k=3,
  CONC=10, same common rollout, same helper gate (lint+smoke, debited) as the running CapEvolve searches, so all arms share
  one gate regime. Submitted via tools/submit_competitor_searches.sh. One dedicated host per job: -m lists only non-reserved
  hosts with no exp895 job of ours, span[hosts=1], and tools/lsf_exclusive_wrapper.sh re-checks at start (exit 99, requeue -Q 99).
- MIPROv2 NOT launched yet: its first real smoke (1927517) never measured anything (DSPy-before-litellm import order, as the
  reviewer predicted). Fixed (litellm imported first, verified). Smoke re-run as 1952281; its search follows once it passes.
- Fixes applied before launch (reviewer findings that would invalidate results):
  - gateway GLM read timeout 180 -> 900 s for EVERY arm. Non-streamed 16k-token replies (GEPA, SkillOpt, ACE, ...) were capped
    at 180 s, and skillopt smoke_s0c had 18 ReadTimeouts on 1,588 s calls. The CapEvolve optimizer streams (its 9-11 non-stream
    calls are all < 0.2 s), so the change does not affect it.
  - §5 20M optimizer-token guard: implemented in the gateway, LOG-ONLY ("opt_token_guard_crossed" event), identical for all
    arms. CapEvolve was launched without an enforcing guard, so enforcing it on competitors alone would be unequal.
  - meta_harness: authoritative selection state moved OUT of the proposer's writable sandbox cwd (run/selection/), and the
    proposer sees only a mirror. Ties now compare raw vs raw (the old code compared raw vs rounded). Unit-checked: an exact tie
    keeps the incumbent, and an edit to the mirror is ignored.
- Reviewer findings NOT fixed (minor, or affect only failure-path reporting); listed so the result can be read with them:
  - skillopt: at R=2160 the slow update / meta-skill never run with content (epoch 2 does not fit). This is a budget consequence.
  - trace2skill: the evolver's exit code is not checked, and analyst parse errors pass silently.
  - wikiskill/evoskill: their own token cap was missing; now covered by the shared gateway guard (log-only).
  - gepa: a task infra on every trial after retries raises RuntimeError and ends the search with no run_summary (§0.3 is respected).
  - common: CommonRollout._tasks holds all 400 tasks, so test ids are blocked by each launcher's guard, not by the rollout itself.
  - ace: D3 says the newest [script] bullet wins per file; in fact the last one in playbook line order wins.
- **Host-sharing incident at launch (06:39-06:44Z), fixed.** The first exclusive-host check queried bjobs, and jobs dispatched within
  the same second each missed the other: 4 hosts got 2-3 of our jobs (gepa s1+s2 on cccxc586, gepa_full s0+s1+s2 on cccxc588,
  skillopt s2 + evoskill s0 on cccxc560, evoskill s2 + trace2skill s0 on cccxc559; trace2skill s0 correctly requeued itself).
  Within ~5 min of each start, killed by exact id the LATER-started job of each pair: 1952284 gepa_s1, 1952288 gepa_full_s1,
  1952289 gepa_full_s2, 1952295 evoskill_s0. Their partial run dirs were moved to *.killed_shared_host (not used, not deleted).
  The survivor of each pair ran alone afterwards. Its first ~5 min shared the host (warm-up + image load only, no counted rollout
  had finished), so its results are kept. Resubmitted as 1952678 (gepa s1), 1952679 (gepa_full s1), 1952680 (gepa_full s2),
  1952681 (evoskill s0).
  New wrapper: an atomic per-host mkdir lock in host-local /tmp that holds the owner job id, waits out the owner-write window, and
  reclaims a stale lock whose owner is no longer RUN there. Tested with 4 concurrent fake jobs: exactly 1 ran, 3 exited 99, and
  a stale lock was taken over.
- 07:00Z: a 5th collision (cccxc577: meta_harness s2 dispatched next to trace2skill s0). Jobs started before the lock fix hold no
  lock, so a newer job found none. meta_harness s2 (1952307) was killed before its launcher ran any rollout (dir moved to
  *.killed_shared_host) and resubmitted. The wrapper now ALSO refuses when bjobs shows another running exp895 job on the host:
  the lock covers simultaneous dispatch, bjobs covers older unlocked jobs.

## 2026-10-22 ~17:30Z — GLM auth outage (14:03Z) killed 7 competitor searches; gateway fixed; relaunched
- At 14:03Z Curve Bender returned 401 ("Authentication Error ... Canceling statement due to conflict with recovery", an upstream DB
  failover). The gateway (§8: a key that returns 401/403 is dead for 10 min) then failed EVERY optimizer call for 600 s. Arms that
  call the optimizer without retrying ended: wikiskill s0/s1/s2 (stop engine_error, 0 iterations), trace2skill s1 (completed with
  both candidates unevaluated, champion = seed by default), ace s2 / evoskill s0 / evoskill s2 (crashed: AuthenticationError /
  "Event loop is closed", idle 3-4.5 h). Probes 4 h later: 5/5 GLM calls 200.
- Killed by exact id (1952318, 1952681, 1952297); all 7 run dirs moved to *.glm_auth_outage (kept, not used).
  Relaunched: 1981023-25 wikiskill s0-2, 1981026 trace2skill s1, 1981027 ace s2, 1981033/34 evoskill s0/s2.
- Gateway fix (all arms): an auth error now opens a 60 s cool-off, and calls WAIT it out and retry (up to 8 attempts) instead of
  failing. An auth blip is infra, never a result. CapEvolve was not affected (its optimizer calls ended before 14:03Z) and
  keeps running on its original gateway process.

## 2026-10-22 ~18:00Z — Test scoring per search, with an in-window seed anchor (Boaz; DEVIATION from §0.2/§9)
- §9 says one registered, interleaved window after ALL 30 searches are frozen. Boaz chose: test each champion as soon as ITS
  search ends, with the seed agent interleaved in the same window as a drift anchor.
- tools/test_window.py, per (arm, seed):
  - Freeze: copy only the agent surfaces (prompt.md, task_template.md, skills/), and record the sha256 of every file plus the
    shuffled order.jsonl sha256 in registry.json BEFORE the first episode.
  - Cells: champion x3 + seed x3 on the 280 official test tasks (1,680 episodes), interleaved with a fixed shuffle seed.
  - Same adapter / scorer / LibreOffice recalc / helper gate as search.
  - Infra: up to 3 retries with a fresh seed, otherwise missing (never 0).
  - Trial seeds 900_000_000 + ..., disjoint from every search.
  - Headline: mean paired per-task delta (champion - same-window seed), CR1 SE by task, 95% t interval on 279 df.
- Consequence to report: each arm's champion is compared with ITS OWN window's seed, not one common window. Cross-arm differences
  are differences of deltas measured at different times. The seed anchor exists to absorb that drift; the anchors' spread across
  windows will be reported as the drift estimate (§9.5).
- tools/auto_test_launcher.py (run every 5 min by a Monitor) launches a window the moment a search writes its end record.
  Searches that END IN ERROR are not tested; they are reported for relaunch. Launched so far: capevolve s1 (1982624),
  capevolve s2 (1982625), trace2skill s0 (1982628; champion = seed, labelled inert).
- Offline check of freeze/order: 1,680 episodes = 840 champion + 840 seed, 280 distinct tasks, all TEST ids, interleaved.

## 2026-10-22 ~19:00Z — MIPROv2 searches launched (Boaz: yes)
- Smoke evidence (runs/miprov2/smoke_s0, job 1952281): 30 measured rollouts (9 infra LLM timeouts, retried, not scored), R honoured
  (30/30, BudgetStop before overshoot), 4 candidates evaluated, 0 prompt-LM errors, champion = seed (ties keep seed).
  The first smoke (smoke_s0.failed_import_order) never measured anything: DSPy-before-litellm import order, fixed.
- Launched 1986368, 1986369, 1986371 (seeds 0,1,2), R=2160, k=3, same gate and host-exclusivity as the other arms.
- All 27 competitor searches + 3 CapEvolve searches are now submitted or running.

## 2026-10-22 ~19:15Z — Slot count (-n) for search jobs: review only, NO change tonight (Boaz: if in doubt, change nothing)
- Every exp895 search/test job was submitted with -n 8. Boaz asked whether one slot is enough.
- KB (docs/how-to/ccc/CCC_PODMAN_SETUP.md §"-n 1 for --max-iterations 0 runs"): -n 1 for single-eval runs; -n 4 "only for full
  multi-iteration optimizer runs". Memory feedback_bsub_cpu_slots: -n 4 for a baseline wastes 3 slots.
- Measured (LSF CPU time / run time): the job's own processes use 0.21-0.36 cores on average (capevolve_s0 0.36, gepa_s2 0.21,
  skillopt_s1 0.21, meta_harness_s1 0.22). They are mostly waiting on Gemma.
- BUT that number excludes the agent containers. Each search runs up to CONC=10 executor containers, and the vendored harness caps
  each at nano_cpus=2 (jupyter.py:246). They run under the job's podman service, outside LSF's job accounting. Host-level: cccxc550
  shows r15m load 99 on 128 slots, shared with other users, so the container CPU cannot be attributed from LSF numbers alone.
- Assessment: -n 1 would under-reserve if the 10 containers are busy (Python kernels, LibreOffice recalc), and LSF could then pack
  other users' jobs onto a host our containers are loading. -n 8 over-reserves if they are mostly idle. This is a judgement on a
  fact not yet measured (container CPU per search), so per Boaz's instruction nothing changes tonight: running jobs keep -n 8, and
  queued jobs keep their submitted -n 8.
- To decide in the morning: measure per-search container CPU (podman stats on one host, inside an LSF job). Then the choice is
  -n 1 (KB default, if containers are near idle) vs a value sized to measured container use (e.g. -n 2-4). Applies to NEW
  submissions only.

## 2026-10-23 ~05:40Z — Morning housekeeping (Boaz approved)
- Killed 9 finished-but-hung jobs by exact id. Each one's log shows *_SEARCH_DONE and its run dir has run_summary.json or
  CAPEVOLVE_RC=0: 1913879 capevolve_s0, 1967842 trace2skill_s0, 1952302 trace2skill_s2, 1981026 trace2skill_s1, 1981033 evoskill_s0.
  Plus 4 stale duplicates from the 14:03Z auth outage (1953658 / 1952313 / 1952314 wikiskill s0-2 and 1952300 trace2skill s1),
  whose run dirs had already been moved to *.glm_auth_outage. Their reruns are separate jobs and kept running.
- The auto-test watcher was NOT running overnight: the Monitor died with the previous session. So 4 searches finished without a
  test window. Launched by hand this morning: 44424 capevolve s0, 44425 evoskill s0, 44426 trace2skill s1, 44427 trace2skill s2.

## 2026-10-23 — Slot count: -n 2 for NEW submissions (Boaz: "2 should be more than enough, check first")
- Measured on cccxc586 (gepa s2, job 1967734, via lsrun, read-only), all of this user's processes there:
  - LSF CPU accounting: 9,287 CPU-s over 62,429 s = 0.15 cores average.
  - The arm's own python processes: 508 + 438 + 199 + 123 CPU-s over 17.3 h. podman service: 216 CPU-s.
  - One live agent container (jupyter kernelgateway + ipykernel): 11 CPU-s over 3,672 s of life (0.003 cores), 0 CPU-s in a 30 s
    window while its episode waited on Gemma.
  - Earlier LSF numbers for other searches: 0.21-0.36 cores (capevolve_s0, gepa_s2, skillopt_s1, meta_harness_s1).
- Conclusion: a search is LLM-bound. Containers spend nearly all their time waiting, and the job uses well under 1 core.
  -n 2 leaves headroom for bursts (LibreOffice recalc, a busy kernel). -n 1 would also fit the average, but bursts with up to
  10 containers make 2 the safer choice.
- Applied to NEW submissions only (tools/submit_competitor_searches.sh SLOTS=2; tools/auto_test_launcher.py -n 2). No job was
  pending at the time, so bmod changed nothing. The 30 running jobs keep -n 8 (not touched, per Boaz).
- Host exclusivity is unchanged and independent of -n (span[hosts=1] + the per-host lock wrapper): fewer slots does not mean
  sharing a host with another of our podman jobs.

## 2026-10-23 ~08:20Z — Helper gate: LEAVE AS IS (Boaz: option 1)
- No change to the gate for any arm. All running and finished searches stay comparable under one gate regime.
- Report the gate's refusal rate per arm as a measured limitation, with the verified false-positive examples, and track the
  fix in a GitHub issue (not in this experiment).
- Refusal rates computed (runs/gate_refusals.json) and posted on #895. Lint false positives filed as #912 with a minimal repro
  (`sheet_name is None`, `answer_position` in a message; controls behave correctly). The budget evidence was added to #877.
  CapEvolve: 6 of 8 refusals come only from the two misfiring rules; 2 are real defects.

## 2026-10-23 ~22:10Z — GEPA s1 search ENDED IN ERROR (not tested; awaiting Boaz)
- runs/gepa/search_s1 (job 1952678): GEPA_RC=1 at 1,711/2,160 rollouts, 57 eval calls, 23 iterations; no run_summary.json and no champion/.
- Cause: in a minibatch eval (eval_call 56), train task 22-47 stayed infra on all 3 trials after every retry (LLM Timeout: the RITS
  Gemma degradation of 15:00-22:00Z, 6-31% failed calls). gepa_arm.py:189 then raises RuntimeError by design. That is the reviewer's
  known gap ("a task infra on every trial after retries ends the search with no champion and no run_summary"). §0.3 is respected
  (nothing was scored 0), but the search lost its result.
- State on disk: gepa/gepa_state.bin (93 kB, GEPA's own checkpoint) and gepa_events.jsonl show a best full-val candidate at
  iteration 23 (idx 10) with val avg 0.842 vs seed 0.700. GEPA's state is resumable (GEPAResult.from_state was verified on the smoke).
- The job had finished (GEPA_SEARCH_DONE) but stayed RUN, so it was killed by exact id (standing rule). Nothing else changed.
- Options for Boaz (not acted on): (a) recover the champion from gepa_state.bin and test it, recording that the search ended early at
  1,711/2,160; (b) rerun gepa s1 from scratch; (c) report it as a failed search.

## 2026-10-23 ~23:40Z — RITS Gemma OUTAGE (not acted on; Boaz asleep, instruction: do not change/kill running tasks)
- From ~23:08Z: 0 successful Gemma calls per 5 min (all ReadTimeout). A direct probe of the RITS -it endpoint, bypassing our
  gateway, also times out (2/2 at 60 s), so it is the endpoint, not our setup.
- Effect: every search and test window is stalled on agent calls. The gateway retries each call up to 8x (~13 min), then the
  rollout fails as infra (never scored 0, §0.3). Arms re-run infra trials up to 3x with fresh seeds; after that the trial is
  missing. A long outage risks:
  (a) arms that raise when a task is infra on every trial (gepa — the gepa s1 failure tonight was exactly this) ending their search;
  (b) test windows marking trials missing.
- Not acted on: no kill, no pause, no restart, per Boaz's instruction. To assess in the morning: which searches ended in error
  during the outage (the watcher flags NEW_NONZERO_RC), and how many test trials went missing.
- 00:02Z: Gemma back (123 ok / 147 failed in 10 min); the outage lasted ~55 min (23:08-00:02Z). Damage check:
  - No search or test ended in error during the outage (0 new non-zero RCs, 0 new tracebacks). 28 RUN, 1 PEND.
  - Test windows hold 12-23 trials each that are FINAL infra (missing after all 4 attempts): capevolve s0 16 / s1 14 / s2 23,
    evoskill s0 12, meta_harness s1 13, skillopt s0 16, trace2skill s0 14 / s1 13 / s2 12. These count as missing, never 0
    (registered analysis). For CapEvolve s2, 23 of ~1,629 trials is 1.4%. A task stays in the paired estimate whenever any of its
    trials was measured.
- 00:22Z: Gemma DOWN again (11 ok / 136 failed in 10 min), ~20 min after the 00:02Z recovery. Same policy: no action.
- 00:52Z: Gemma back (207 ok in 10 min); the second outage lasted ~30 min (00:22-00:52Z).
- ~02:40Z: **GEPA s0 ENDED IN ERROR, the same mode as gepa s1.** GEPA_RC=1 at 1,057/2,160 rollouts (34 eval calls). Train task 6239
  stayed infra on every trial after all retries (the 23:08-00:52Z RITS outages), so gepa_arm.py:189 raised RuntimeError. There is
  no run_summary and no champion, so no test window. Checkpoint gepa/gepa_state.bin (54.6 kB) is on disk; its best full-val
  candidate had avg 0.858 at iteration 14 (7 full-val evals). Job 1952283 printed GEPA_SEARCH_DONE but stayed RUN, so it was
  killed by exact id (standing rule).
  => GEPA has now lost 2 of its 3 searches to infra this way. Same options as s1 (recover from the checkpoint / rerun / report
  failed), plus the cause: the gepa port treats "a task infra on every trial" as fatal, while the other arms drop it as missing.
  Awaiting Boaz.
- ~03:10Z: **WikiSkill s2 stopped with stop_reason=engine_error** at 834/2,160 rollouts, iteration 4. The WikiSkill engine raised
  "6 tasks need attention. Resolve infrastructure and resume; completed tasks are retained" (infra-missing tasks from the night's RITS
  outages; GLM was fine: last 20 calls 200). Unlike gepa it DID write run_summary.json with a champion: it003_ba9d0a98eca4,
  val 0.85 (seed 0.717), 3 candidates evaluated, 2 accepted. auto_test_launcher treats engine_error as FAILED, so no test window was
  launched. Job 1981025 printed WIKISKILL_SEARCH_DONE but stayed RUN, so it was killed by exact id (standing rule).
  => Awaiting Boaz: (a) test its champion as-is (search ended early at 834/2,160), (b) rerun, or (c) report as failed.

## 2026-10-24 06:50Z - recovery of GEPA s0, GEPA s1, WikiSkill s2 (Boaz: "recover and continue the errored arms")
- Cause: RITS Gemma outage/degradation overnight (23:08-00:52Z plus a long tail of ~1800 s litellm timeouts). GEPA s0/s1 died at
  gepa_arm.py evaluate() ("task X stayed infra-errored on every trial after retries"; GEPA needs one score per item). WikiSkill s2
  ended stop=engine_error after 3 resumes of iteration 4 ("6 tasks need attention"). All three were infra stops, not results.
- GEPA fix (gepa_arm.py): after 2 immediate re-evaluations, wait-and-retry 300/600/900 s (as MIPROv2 does) before raising. Applies to
  GEPA s2 only if it restarts; the running s2 keeps the old code (its sha is in its run_meta.txt).
- Resume: new RESUME=1 mode in lsf_gepa_search.sh and lsf_wikiskill_search.sh (keeps ids/spec, appends arm.log/run_meta).
  GEPA reloads gepa/gepa_state.bin (api.py run_dir resume; the seed val eval is re-run by the engine but its result is discarded
  when a state exists, so a small extra spend on the 40 val tasks x3 is NOT counted against the saved budget_state... it IS counted:
  CommonRollout reloads spent, then the seed re-eval adds ~120 to spent). Recorded as a deviation: resumed GEPA arms spend ~120 extra
  rollouts of R on the seed re-score. The iteration in flight at the crash is also redone.
  WikiSkill: engine resumes from manifest/outcomes (completed rows kept); old run_summary/champion moved to *.engine_error_20261024.
- Jobs: gepa s0 184553, gepa s1 184554, wikiskill s2 184555 (resume), -n 2, exclusive wrapper, no -W.
- Known chronic tasks (infra-heavy even outside the outage): 6239, 22-47, 34033, 398-14, 37456, 56786, 51090, 194-19. Not excluded (equal for all arms).
- GEPA-full s0 job 1967755 PEND since 10-22: it requests -m cccxc586 only (stale host list). To be re-submitted with a fresh host list.
- 07:35Z WikiSkill s0 also ended engine_error (iteration 4, 3 tasks needing attention after 3 resumes, 957/2160, champion it002 val 0.792).
  Same infra cause as s2. Job 1981023 (stuck in post-run steps) killed by exact ID; old summary/champion moved to *.engine_error_20261024;
  resumed with RESUME=1 as exp895_wikiskill_s0_resume.
- 08:40Z WikiSkill s1 also engine_error (iteration 4, 629/2160, champion it002_69d6...). Its job 1981024 sat in post-run steps for 4 h after the arm ended
  (04:29Z); killed by exact ID, summary/champion moved to *.engine_error_20261024, resumed with RESUME=1 (exp895_wikiskill_s1_resume).
  Observation: s2's resume (184555) has made no progress since 04:30Z (924 spent): rollouts are all infra; s0 resume progressing slowly.
- 2026-10-24 ~20:50Z WikiSkill s0 second engine_error (iteration 4: train 90/90 done; val 117/120, the 3 missing cases are task 7902 timing
  out on infra 8x each; task 7902 has 457 clean runs elsewhere). Job 187881 (arm finished, WIKISKILL_RC=0) killed by exact ID;
  summary/champion moved to *.engine_error2_20261024; plain resume (RESUME=1) as exp895_wikiskill_s0_resume2. No policy change.
- 2026-10-25 02:00Z WikiSkill s2 second engine_error at iteration 4: train 85/90, missing 398-14 x2 and 6239 x3 (all infra timeouts). Job 184555 killed by exact ID
  (arm done, WIKISKILL_RC=0). Run state left as is (summary = engine_error, champion it003 val 0.85, 910/2160); NOT resumed yet, pending Boaz's decision.
  Finding: tasks 6239 and 398-14 are chronically infra-heavy for every arm: 6239 = 568 infra / 106 clean (clean median wall 1623 s, p90 3749 s,
  i.e. at or over the ~1800 s agent-call timeout); 398-14 = 343 infra / 90 clean (median 1787 s, p90 6461 s). WikiSkill's engine needs every case of its
  train subset, so s2 (has both) and s1 (has 6239) can keep failing; s0 (has neither) failed only on val task 7902.
- 2026-10-25 ~03:00Z GEPA s1 resume (184554) ended GEPA_RC=1 again: task 22-47 stayed all-infra even after the new 300/600/900 s waits
  (iteration after 1831/2160). Job killed by exact ID. gepa_state.bin from the earlier checkpoint is kept; no summary/champion. NOT relaunched,
  pending Boaz's decision (same chronic-task issue as WikiSkill s2: 22-47 had 251 infra / 103 clean across arms).
- 2026-10-25 ~05:10Z GEPA s0 resume (184553) ended GEPA_RC=1: task 6239 stayed all-infra after the 300/600/900 s waits (spent 1176/2160, eval_call 42).
  Job killed by exact ID. gepa_state.bin kept; no summary/champion. NOT relaunched, pending Boaz's decision on the chronic-task failures
  (6239: 568 infra / 106 clean across arms). Parked together with GEPA s1 (22-47) and WikiSkill s2 (6239, 398-14).
- 2026-10-25 ~07:40Z WikiSkill s1 resume (192427) ended engine_error again at iteration 3: train 89/90, missing only 57113__t0 (infra). Job killed
  by exact ID (arm done, WIKISKILL_RC=0). Run left as is (summary engine_error, champion it002 val 0.767, 695/2160). NOT resumed; parked with
  GEPA s0/s1 and WikiSkill s2 pending Boaz's decision on the chronic infra-timeout tasks.

## 2026-10-25 — Preparing capevolve_v2 (main + PR #914, k_se 0.2) for a NEW dedicated session (Boaz / Osher)
- Osher: re-run CapEvolve ONLY on latest main (PR #914 merged 75b3bcdd0: optimizer INSTRUCTIONS "Improvement 2", default gate_k_se 0.2),
  fresh intake. Answers: (1) cherry-pick #903, do not merge; (2) gate_footprint = the main default (key absent = masking on);
  (3)+(4) more RITS keys from Boaz for load balancing.
- Prepared: worktree sbv400-k02 / branch exp/sbv400-895-k02 = origin/main 75b3bcdd0 + cherry-picks 777e111b3 (#903) and 0d791eeb7
  (common helper gate); venv_k02 (job 331040, editable sbv400-k02/core verified); tools/node_env_k02.sh, tools/lsf_build_venv_k02.sh,
  tools/lsf_capevolve_v2_search.sh (runs/capevolve_v2, tag exp895-capevolve_v2-s*, KEY_SLOT); empty arms/capevolve_v2/.
  adapter.py sha256 c035c75e... and seed_capability_v2 unchanged vs the capevolve arm. Old exp895 INSTRUCTIONS block extracted to
  arms/capevolve/INSTRUCTIONS.exp895_addendum.md (lines 81-157, inserted after {{BENCH_REPO}}).
- RITS keys: 6 extra keys copied to ~/secrets/rits_keys.env (600) as RITS_API_KEY_1..6; source rits_keys.txt chmod 600. Key check
  (job 330550): current + slots 1,2,3,5,6 OK; slot 4 = 403 Authentication failed (do not use). Load probe (job 331105, 16-burst):
  current 168 s, slot 2 133 s, 8+8 split 155 s, 32 over 2 keys 121 s all 200 -> a second key adds capacity without harm (small noisy test).
- Shared-tool changes (backward compatible; running jobs unaffected): gateway.py GW_RITS_KEY_SLOT (unset = rits.env key; /healthz reports
  key_slot); lsf_test_window.sh optional KEY_SLOT; auto_test_launcher.py knows capevolve_v2 (same finished() rule as capevolve).
- Handoff: exp895/HANDOFF_capevolve_v2.md. Ownership: the v2 session acts only on exp895_capevolve_v2* jobs; this session on the rest.

## 2026-10-25 — [v2-session] capevolve_v2 intake, template, check, first smoke
- [v2-session] Fresh intake on sbv400-k02 (main 75b3bcdd0 + #903 + helper gate). Template at arms/capevolve_v2/template/.capevolve/project (PROJECT.md has the full diff vs capevolve).
  gate_k_se 0.2 (default, not overridden), gate_footprint absent (Osher). INSTRUCTIONS.md = new template + 77-line exp895 block after {{BENCH_REPO}}: 274 lines, sha256 e668bb8d1b2d5b06e2e40cb2b3dbd2a196da714b35a71d47a709b822069cff24.
- [v2-session] Osher: metric = SpreadsheetBench score. Reward was already the hard score (SCORING=hard, recalc=1, as capevolve); spec now declares metric_primary hard_restriction, metrics_display [hard, soft]. Reward/gate unchanged.
- [v2-session] cap-evolve check green (jobs 338316, 338570 on the final spec; ok:true, scorer deterministic). Hung-in-RUN check jobs killed by exact ID.
- [v2-session] First smoke (job 338877, runs/capevolve_v2/smoke_k02_failed_sandbox_venv): search ended RC=0 but the optimizer never ran: tools/sandbox/claude binds only exp895/venv, and v2's python is venv_k02 (bwrap execvp ENOENT). Result "seed champion" is void.
- [v2-session] SHARED-TOOL CHANGE (backward compatible): tools/sandbox/claude now binds ${EXP895_VENV:-$EXP/venv}; unset = old behaviour. Written atomically (backup claude.pre_v2.bak). Only node_env_k02.sh sets EXP895_VENV=$EXP/venv_k02.
- [v2-session] Smoke OK (job 340628, runs/capevolve_v2/_aside/smoke_k02_ok_340628): code_sha 0d791eeb7, key_slot=2, run-copy spec gate_k_se 0.2 with no gate_footprint key
  (step event has delta_masked = engine default masking), optimizer in the bwrap shim (28 GLM calls, all 200, 918k tokens), cand_0001 produced, refused by the
  helper gate (lint: branches on task identity) -> 0 -> rejected. Seed 1.0 on the 2 smoke tasks. R counter 12/24. Hung-in-RUN job killed by exact ID.
- [v2-session] Correction (Opus review): INSTRUCTIONS.md rebuilt with the EXACT splice used for the capevolve arm (verified by rebuilding the old arm's
  file from sbv400-main's template: one blank line before the block, none after). First build had one extra blank line after it. New: 273 lines,
  sha256 c047435b418b8f1eb9da50f37a64fb50fcdd128601d24c8f26f6c88c322cb6c3 (placeholders unchanged). build_template.py now also sets the metric keys.
- [v2-session] Note: in verified_400 each task has exactly ONE test case (395 x 1_*_golden, 5 x golden.xlsx), so hard_restriction == soft_restriction per trial.

## 2026-10-25 ~13:30Z — Relaunch of the 4 parked searches with fixes + dedicated RITS keys (Boaz: "fix ... run with a dedicated Rits key")
- GEPA (arms/gepa/gepa_arm.py): a minibatch task still all-infra after the 2 immediate re-evals + 300/600/900 s waits now raises
  IterationSkip (a RuntimeError) and GEPA runs with raise_on_exception=False, so it logs it and skips THAT ITERATION instead of ending the
  search. Nothing is scored 0; the minibatch's counted rollouts stay debited. A BudgetStop swallowed the same way is caught by EventLog.on_error
  and a new stop callback (evlog.budget_stop) ends the loop; run_summary records iterations_skipped_infra. Verified offline with the real
  gepa.optimize and a fake rollout (LSF job, cccxc577): an all-infra task skipped 14 iterations and the search kept going to R=600;
  a 40-rollout budget stopped at 39 with budget_stop set. Deviation from upstream default raise_on_exception=True (recorded here).
- WikiSkill (arms/wikiskill/wikiskill_arm.py): RESUME_WAITS 300/900/1800 s before the 2nd/3rd/4th engine resume without progress (first
  resume still immediate); MAX_RESUMES unchanged (3).
- Keyed launcher copies (originals untouched: GEPA s2, WikiSkill s0 and MIPROv2 s0 are still running bash on them):
  arms/gepa/lsf_gepa_search_keyed.sh, arms/wikiskill/lsf_wikiskill_search_keyed.sh = originals + `export GW_RITS_KEY_SLOT=${KEY_SLOT:-}`.
  tools/lsf_test_window.sh restored to its original bytes (8 test windows run it); the KEY_SLOT variant is tools/lsf_test_window_keyed.sh.
- Keys: capevolve_v2 uses slots 2/3/5 (v2 session). Here: GEPA s0+s1 -> slot 6, WikiSkill s1+s2 -> slot 1. Everything else stays on rits.env.
- Jobs (RESUME=1, -n 2, exclusive wrapper, no -W): gepa s0 343227 (cccxc577), gepa s1 343228 (cccxc540), wikiskill s1 343229 (cccxc565),
  wikiskill s2 343230 (cccxc582). WikiSkill s1/s2 old summary/champion moved to *.engine_error3_20261025.
- MIPROv2 s0: NOT restarted. It was stuck on val task 37456 for ~6 h (13 infra in a row), but task 37456 has now scored (last row 'none',
  one eval took 10,004 s), and MIPROv2 has no resume path (its scorer cache and DSPy state live in memory; killing it loses the search).
  Left running on its original key, watched. If it stalls again, a restart would start from scratch.
- [v2-session] LAUNCHED capevolve_v2 (2026-10-25 ~13:15Z), R=2160, k=3, gate_k_se 0.2, gate_footprint absent (masking on), code 0d791eeb7, adapter c035c75e:
  s0 job 343031 cccxc513 key slot 2 | s1 job 343035 cccxc520 key slot 3 | s2 job 343063 cccxc530 key slot 5. Each gateway's /healthz reports its slot (run_meta.txt HEALTHZ_GEMMA).
  Per-seed spec differs only in split_seed and run paths. Launcher change: lsf_capevolve_v2_search.sh records /healthz in run_meta.txt.
- [v2-session] Main check: origin/main moved to 7fb091b7b (#936, docs/site only: no core/, skills/ or templates/ change), so the runs stay on 75b3bcdd0 (+#903, +helper gate).
  v2 INSTRUCTIONS minus the exp895 block == main's template byte for byte (PR #914 sections present; the smoke's rendered prompt contained them).
- [v2-session] Boaz: no need for every candidate to touch prompt.md; keep the current surface (prompt.md, task_template.md, skills/).
- [v2-session] NEW tools/lsf_test_window_v2.sh (ARM=capevolve_v2 only): = lsf_test_window_keyed.sh + node_env_k02.sh, v2 helper-gate spec, KEY_SLOT default 6,
  logs /healthz and code_sha. For the monitoring session: switch auto_test_launcher.py to this script for capevolve_v2 (not done by this session).
- 2026-10-25 ~14:00Z Boaz: leave MIPROv2 s0 running on the shared rits.env key for now (stuck on val task 37456, 696/2160, no resume path).
  Move it to its own key later, when a key frees up (it would have to restart from scratch). Early result of the dedicated keys: the
  4 relaunched searches ran 0-10% infra in their first 40 min vs 20-100% on the shared key.
- [v2-session] 2026-10-25 22:07Z: capevolve_v2 s1 (job 343035) seed eval done after 8.8 h (old arm: ~4 h; Gemma degraded). baseline val 0.697 +/- 0.042 on 115/120 tasks
  (331/360 trials; unscored: 194-19, 22-47, 398-14, 51090, 6239, mostly the known chronic slow tasks), baseline_incomplete flagged by cap-evolve. On the same 115 tasks the old
  capevolve seed scored 0.701 (s1), 0.699 (s0), 0.696 (s2): same seed, same agent, no drift. R spent 360/2160; optimizer (GLM) started. s0, s2 still in seed eval.

## 2026-10-25 ~22:20Z — SkillOpt s1/s2 test windows on key 6; Trace2Skill s2 test window resumed after a lost host (Boaz)
- SkillOpt s1 (2135/2160) and s2 (2143/2160) ended SKILLOPT_RC=0 (BudgetStop step guard). Hung search jobs 1952292, 1967841 killed by exact ID.
- Their auto-launched test jobs (386361/386362, still PEND, never started) were killed by exact ID and resubmitted on RITS key slot 6 via
  tools/lsf_test_window_keyed.sh: 386693 (s1), 386699 (s2). Load in the last hour: rits.env ~1,750 calls/h shared by 14 searches; slots 2/3/5
  (capevolve_v2) 2-5% failed; slots 1 and 6 show ~70-80% failed calls, but those are the chronic slow tasks (6239, 22-47, 398-14) of the
  4 resumed searches timing out, not a weak key: their other calls succeed.
- Trace2Skill s2 test (job 44427) lost host cccxc588 (unavail, job UNKWN, then ZOMBI after bkill) at 1,276 resolved episodes. Boaz chose
  option B: tools/test_window.py --resume (new flag; default behaviour unchanged). It verifies registry.json (champion tree sha256, seed
  tree sha256, order.jsonl sha256, arm/seed/k/anchor), never re-freezes, keeps every FINAL episode (a non-infra row, or an infra row at
  attempt 3) and re-runs the rest from their NEXT attempt, so trial seeds stay unique. Dry count: 1,310 final, 370 to run (3 mid-retry).
  Launcher tools/lsf_test_window_resume.sh (= keyed copy + --resume). Resumed as job 386884 on key slot 6.
- [v2-session] 22:13Z: capevolve_v2 s1 iteration 1: cand_0001 (GLM 434 s, 2.8M tokens) refused by the common helper gate (lint "names an evaluator/gold/split path"
  on an error message containing 'answer_position'; the #912 false positive). 360 trials scored 0, debited, rejected. R 720/2160. No change (Boaz 2026-10-23, option 1).
- [v2-session] 22:23Z: capevolve_v2 s1 iteration 2: cand_0002 refused by the same lint rule (#912: 'parse_answer_position', 'answer_position is None' in ranges.py).
  R 1080/2160 after 2 iterations, 0 agent rollouts run for any candidate. The gate feedback reads "Infrastructure error ... do not optimize against it" (the known
  shared-adapter limitation, decisions 2026-10-22), so the optimizer is not steered off the pattern. Flagged to Boaz; no change made.
- 22:45Z Host collision: LSF dispatched SkillOpt s1 (386693) and s2 (386699) test jobs to cccxc542 in the same second. Both passed the
  exclusive wrapper: the second saw the first's lock, bjobs did not yet show its owner as RUN, so it judged the lock stale and reclaimed it.
  s1's gateway then failed to bind :4113 ("address already in use"); it never registered a window (no runs/test/skillopt_s1). s2 runs fine.
  Fix: lsf_exclusive_wrapper.sh treats a lock younger than 300 s as never stale (exit 99 -> requeue). Swapped in atomically (new inode;
  backup .pre_fresh_lock.bak) so running jobs are unaffected. s1: 386693 killed by exact ID, its gateway dir moved to
  .gw_skillopt_s1.failed_colocated_386693, resubmitted as 388502 (key slot 6, cccxc542 excluded).
- 22:45Z Trace2Skill s2 test resume (386884) running on cccxc706.
- [v2-session] 22:30Z: capevolve_v2 s0 (job 343031) seed eval done after 9.3 h: baseline 0.700 +/- 0.041 on 116/120 tasks (334/360 trials; baseline_incomplete).
  Same tasks, old capevolve s0 seed: 0.687. Seed reproduces. R 360/2160; optimizer started.
- [v2-session] 22:38Z: capevolve_v2 s0 iteration 1: cand_0001 refused by BOTH #912 false positives: "branches on task identity" on `if sheet_name is None:` and
  "names an evaluator/gold/split path" on 'answer_position %r is empty'. R 720/2160. v2 so far: 3 of 3 candidates refused, 0 agent episodes run. Awaiting Boaz.
- [v2-session] 22:45Z: capevolve_v2 s0 iteration 2: cand_0002 refused (#912 'answer_position' in verify.py). Totals: 4 of 4 v2 candidates refused, 0 agent episodes on any
  candidate; s0 R 1080/2160, s1 R 1080/2160. Awaiting Boaz's decision (leave / fix gate feedback / fix #912 lint / pause).
- 23:30Z SkillOpt s2 test window (386699) is VOID, a consequence of the 22:45Z co-location on cccxc542. When the colocated s1 job (386693)
  exited, its cleanup (`exp895_stop_podman_daemons` on EXIT) killed the per-user podman service that s2 shared on that host. From then on
  every s2 episode failed in 0 s with "sandbox exec failed: 500" (6,709 rows). The window "finished" in 30 min with 2 measured episodes,
  champion 278/280 tasks missing, seed 280/280 missing, paired_delta NaN. Not a result. 386699 killed by exact ID; the dir and gateway dir moved
  to *.void_colocated_386699; resubmitted fresh as 390669 (key slot 6). The fresh-lock wrapper fix (22:45Z) prevents a repeat.
- [v2-session] 23:18Z: s2 (job 343063) seed eval done: baseline 0.709 +/- 0.041 on 115/120 (old capevolve s2 on the same tasks 0.687). Optimizer started.
- [v2-session] cand_0003 of s0 and of s1 PASSED the helper gate and are being evaluated on real agent episodes (s1 since ~22:25Z, s0 since ~22:49Z). First real v2 candidates.
- [v2-session] Correction: cand_0003 of s0 and s1 edits prompt.md only (skills/ and scripts identical to the seed), so the helper gate has nothing to lint and it
  runs on real episodes. After two refusals the optimizer moved to a prompt-only edit, so the "budget burns to zero on refusals" risk flagged at 22:45Z did not happen.
- [v2-session] 23:27Z: s2 iteration 1: cand_0001 refused (#912 'answer_position' in sheetkit.py). R 720/2160. v2 total: 5 refused of 7 candidates; 2 in real evaluation.
- [v2-session] 23:34Z: s2 iteration 2: cand_0002 refused by the helper gate (see feedback in rollouts). R 1080/2160. v2 total: 6 refused of 8; 2 in real evaluation (s0, s1 cand_0003).
- 2026-10-26 ~02:30Z WikiSkill s0 (job 270375, OLD arm code without RESUME_WAITS, shared key) ended engine_error at iteration 5: train 87/90,
  missing 194-19__t2, 52216__t0, 52216__t1 (infra); 1267/2160; best so far it002 val 0.792. Job killed by exact ID (WIKISKILL_RC=0);
  summary/champion moved to *.engine_error3_20261026. Relaunched with the fixed arm (resume waits) on key slot 1 (least loaded: ~33 calls/h)
  as exp895_wikiskill_s0_resume_k1.
- Test results in: SkillOpt s0 +0.098 [0.053,0.144] (273 tasks); Meta-Harness s1 +0.060 [0.025,0.096] (277 tasks).
- [v2-session] 2026-10-26 05:37Z status: s0/s1/s2 all evaluating cand_0003 (prompt-only edits from s0, s1; s2's cand_0003 also passed the gate), 6.0-7.2 h in,
  est. 68-100/360 episodes. RITS Gemma severely degraded for ALL exp895 jobs: last hour 84% retry rate over 27 active gateways (v2 on keys 2/3/5: 71-90%,
  same as competitors and test windows on the rits.env key) -> a per-key limit is not the bottleneck. No action (Boaz: do not change timeouts).
- 2026-10-26 ~07:00Z WikiSkill s1 (343229, fixed arm, key 1) engine_error again at iteration 3: train 89/90, missing only 57113__t0
  (57113 is a FAST task: clean median 194 s, but 84 infra / 10 clean in this run). The 300/900 s resume waits ran and did not help.
  Job killed by exact ID (WIKISKILL_RC=0); summary/champion -> *.engine_error4_20261026; resumed again on key 1 (completed rows kept).
- FINDING (needs Boaz's decision): the gateway's 90 s Gemma read timeout is now the main source of infra errors. Last 24 h, all searches:
  29,872 calls succeeded first try, with service time p50 49.9 s, p90 80.0 s, p99 88.9 s, max 90.1 s (the distribution is cut off at the
  timeout); there were 72,830 ReadTimeout retries (vs 50 http_503). On 2026-10-21 the 300 -> 90 s decision assumed p99 < 60 s; under today's
  load the median is 50 s. Calls needing > 90 s are killed and retried up to 8x, and a task whose calls are all long (6239, 22-47, 398-14,
  57113 here) ends infra-missing. NOT changed: it was Boaz's explicit decision, and changing it mid-experiment alters conditions across arms.
- 2026-10-26 ~07:20Z WikiSkill s2 (343230, fixed arm, key 1) engine_error again at iteration 4: train 86/90, missing 398-14 x2 and 6239 x2,
  the two chronic SLOW tasks (clean median 1,600-1,800 s). Job killed by exact ID (WIKISKILL_RC=0). NOT resumed: with the 90 s gateway
  timeout these tasks keep failing (see the timeout finding above); waiting on Boaz's decision before relaunching.
- [v2-session] 2026-10-26 10:50Z: capevolve_v2 s0 iteration 3: cand_0003 (prompt.md-only edit, reply-format rule) ACCEPTED, the first real v2 champion.
  val 0.820 vs seed 0.700 (paired on 101 tasks: seed 0.721 -> 0.820, delta +0.099, SE 0.034; 21 tasks better, 7 worse; fixed 7, broke 1). Eval took 12.0 h.
  Coverage caveat: only 101/120 tasks scored (joint_coverage 0.84; 101 errored trials stay missing = RITS timeouts), so the number excludes the slowest tasks. R 1440/2160.
- [v2-session] 2026-10-26 11:01Z: s0 iteration 4: cand_0004 refused by the helper gate (see rollouts feedback). R 1800/2160; champion stays cand_0003 (0.820). 360 rollouts left.

## 2026-10-26 ~09:30Z — Gemma gateway timeout 90 s -> 300 s for NEW gateways (Boaz: "You can raise the timeout to 300")
- tools/gateway.py default GW_GEMMA_TIMEOUT 90 -> 300. A gateway reads it once at startup, so every job already running keeps 90 s; relaunched
  searches and new/resumed test windows use 300 s. DEVIATION: arms ran under 90 s until now (all searches launched before this change, plus GEPA
  s0/s1, WikiSkill s0/s1, SkillOpt s0..s2 test windows and the Trace2Skill s2 resume). Rationale: 24 h of ledgers show first-try successful
  calls with service time p50 49.9 s / p99 88.9 s / max 90.1 s (cut off by the timeout) and 72,830 ReadTimeout retries.
- tools/auto_test_launcher.py: new test windows now go through lsf_test_window_keyed.sh with KEY_SLOT chosen from crc32(arm+seed) over the
  working keys [1,2,3,5,6] (slot 4 = 403). Existing windows unchanged.
- LSF suspend test (throwaway sleep job, not an experiment job): bstop -> USUSP, bresume -> RUN, both work for this user. Not yet tried on a real
  exp895 job.
- Waste measured over 24 h: 9,808 infra episodes vs 6,420 clean; ~2,090 worker-hours in failed episodes; 8 tasks (37456, 6239, 51090, 398-14,
  194-19, 52216, 51-12, 39046) account for 28% of it.
- [v2-session] 2026-10-26 12:14Z: capevolve_v2 s2 iteration 3: cand_0003 ACCEPTED. val 0.842 (paired on 99 tasks: delta +0.074, SE 0.036; 17 tasks better, 7 worse; fixed 8, broke 2).
  Eval 12.6 h; coverage 99-100/120 (joint_coverage 0.825, timeouts stay missing). R 1440/2160. Accepted v2 champions so far: s0 cand_0003 = prompt.md only; s2 cand_0003 = prompt.md + task_template.md (no helper scripts, so the helper gate had nothing to lint).
- [v2-session] 2026-10-26 12:29Z: s2 iteration 4: cand_0004 refused by the helper gate. R 1800/2160; champion stays cand_0003 (0.842). 360 rollouts left (one candidate).

## 2026-10-26 ~14:50Z — FREEZE (bstop, not kill) of low-priority searches to free Gemma capacity (Boaz)
- Suspended with bstop (state USUSP; resume with `bresume <id>`; state on disk and in memory is kept): GEPA-full s0 (184587, 564/2160),
  ACE s1 (1952317, 447/2160), ACE s2 (1981027, 594/2160). Constraint kept: every competitor still has >= 1 seed running (ACE s0 1952316 runs;
  GEPA-full s1/s2 run). The benchmark is NOT changed (no tasks skipped; Boaz: maybe later).
- Baseline before the freeze (last 2 h, saved in runs/.watch/freeze_baseline.json): 88 counted search rollouts, 127 resolved test episodes,
  Gemma 3,543 ok / 1,074 failed calls.
- Risk: a frozen job's gateway/client sockets time out while it sleeps; on resume it should see errors and retry. Watch for a wave of infra errors
  right after any bresume.
- [v2-session] 2026-10-26 15:10Z: capevolve_v2 s1 iteration 3: cand_0003 ACCEPTED. val 0.820 vs seed 0.697 (paired on 101 tasks: delta +0.094, SE 0.035; 17 better, 8 worse; fixed 8, broke 1).
  Eval 16.7 h; coverage 101/120 (joint_coverage 0.84). R 1440/2160. All three seeds now have a first accepted champion: s0 0.820, s1 0.820, s2 0.842 (seeds 0.700 / 0.697 / 0.709).
- [v2-session] 2026-10-26 15:41Z: s1 iteration 4: cand_0004 refused by the helper gate. R 1800/2160; champion stays cand_0003 (0.820). 360 rollouts left (one candidate).

## 2026-10-26 ~19:50Z — FREEZE round 2 (bstop) so each competitor keeps one search seed running (Boaz: "freeze those you suggested")
- Suspended: GEPA s0 (343227, 1,369), GEPA s2 (1967734, 1,118), GEPA-full s1 (1952679, 1,707), MIPROv2 s0 (1986368, 950), MIPROv2 s2 (1986371, 1,366),
  WikiSkill s1 (420040, 837). Together with round 1 (GEPA-full s0 184587, ACE s1 1952317, ACE s2 1981027): 9 frozen searches.
- Kept running (the most advanced seed of each competitor): GEPA s1 (search done, test window running), GEPA-full s2 (1,793), MIPROv2 s1 (1,522),
  Meta-Harness s2 (1,750), WikiSkill s0 (1,472), ACE s0 (889), EvoSkill s1 (search done), CapEvolve v2 s0/s1/s2 (1,800 each).
- CapEvolve (v1): searches done; its s0 TEST window (44424) is left running to completion (Boaz) so v1 has all three seeds.
- EvoSkill s1 search finished (12 iterations, EVOSKILL_RC=0); hung job 1952296 killed by exact ID; its test window handled by the auto launcher.
- WikiSkill s2 remains PARKED (no job). To bring a frozen search back: `bresume <id>`, one at a time, then watch the first minutes for an error burst.
- [v2-session] 2026-10-27 04:10Z: capevolve_v2 SEARCHES ENDED for s0 and s2 (the background watcher was terminated and missed both; found on the manual status check).
  s0 (job 343031): CAPEVOLVE_RC=0 at 2026-10-26 21:42Z, R 2160/2160. cand_0005 REJECTED (val 0.789 vs 0.820, paired delta -0.014, SE 0.024, n=98; broke 3, fixed 0). Champion = cand_0003 (val 0.820; seed 0.700).
  s2 (job 343063): CAPEVOLVE_RC=0 at 2026-10-26 23:27Z, R 2160/2160. cand_0005 ACCEPTED (paired delta +0.056, SE 0.028, n=92; fixed 4, broke 1; val 0.843, joint_coverage 0.77). Champion = cand_0005 (val 0.843; seed 0.709).
  Both jobs sat in RUN after their CAPEVOLVE_SEARCH_DONE marker; killed by exact ID (343031, 343063), now EXIT. s1 (343035) still on cand_0005, R 1800/2160.
  NO v2 test window has started (no runs/test/capevolve_v2_*, no exp895_test_capevolve_v2_* job): the test-window launcher (monitoring session) has not picked them up. Awaiting Boaz.
- 2026-10-27 ~04:30Z Boaz: finish test results for ALL arms (>= 1 seed each) before resuming any frozen search. Health check of running jobs: all
  progressing (ledgers). Finished-but-hung jobs killed by exact ID: Trace2Skill s2 resume window 386884 (TEST_WINDOW_DONE, +0.093 [0.049,0.137], n=277),
  Meta-Harness s2 search 1953646 (META_HARNESS_RC=0; 2108/2160, champion always_print_and_stop val 0.800 vs seed 0.717). Test windows launched by
  the auto launcher: Meta-Harness s2 (533559, key 6). CapEvolve v2 s0 and s2 searches finished (RC=0); their test windows (532687, 532697) are queued.
- [v2-session] 2026-10-27 04:24Z: Boaz asked to start the tests for the finished searches. The monitoring session's launcher had not started them; none existed or was queued (checked).
  Launched by exact script, one dedicated host each: exp895_test_capevolve_v2_s0 job 532687 (cccxc523, champion cand_0003, KEY_SLOT 6) and exp895_test_capevolve_v2_s2
  job 532697 (cccxc430, champion cand_0005, KEY_SLOT 5, free since its search ended), via lsf_exclusive_wrapper.sh + tools/lsf_test_window_v2.sh (node_env_k02, v2 helper spec, code 0d791eeb7).
  Verified at 04:27Z: /healthz key_slot 6 and 5, warm-up 10/10 x 200, REGISTERED 1680 episodes each (280 test tasks; champion x3 + seed anchor x3), inert_champion false.
  The watcher/launcher (monitoring session) should not start a second window for these seeds: runs/test/capevolve_v2_s0 and _s2 exist, so its dir-exists check skips them. s1 test window not started (search running).
- [v2-session] 2026-10-27 05:13Z: capevolve_v2 s1 (job 343035) search ENDED: CAPEVOLVE_RC=0, R 2160/2160. cand_0005 REJECTED (val 0.818 vs 0.820, paired delta +0.003, SE 0.022, n=98; fixed 1, broke 1).
  Champion = cand_0003 (val 0.820; seed 0.697). The job sat in RUN after CAPEVOLVE_SEARCH_DONE; killed by exact ID 343035 at ~10:10Z (the watcher did report it at 05:14Z but I only read the output at 10:10Z).
  Test window for s1 launched at 10:10Z per Boaz's standing "start tests for finished searches": job 580265, KEY_SLOT 3, champion cand_0003, lsf_test_window_v2.sh, dedicated host via the exclusive wrapper.
- 2026-10-27 ~17:30Z Finished-but-hung jobs killed by exact ID (all RC=0): test windows EvoSkill s2 (309899), GEPA s1 (448641), Meta-Harness s0 (296285);
  searches GEPA-full s2 (1952680, 2154/2160), MIPROv2 s1 (1952..1986369, 2107/2160), WikiSkill s0 (405506, 2102/2160). Test windows launched by the auto
  launcher for those three searches: GEPA-full s2 625412 (key 2), MIPROv2 s1 625413 (key 5), WikiSkill s0 625414 (key 3), all queued (cluster at slot limit).
- New test results: EvoSkill s2 +0.123, GEPA s1 +0.100, Meta-Harness s0 +0.041, Trace2Skill s2 +0.093 (summary re-read).

## 2026-10-27 ~18:30Z — Three queued test windows (GEPA-full s2, MIPROv2 s1, WikiSkill s0) resubmitted; speed-ups agreed with Boaz
- Waited 47 min PEND ("Job slot limit reached: 83 hosts"): every host on the jobs' host list was at its slot limit; the ~2,750 free slots of the 26
  `ok` hosts sit in other groups' reservations (infusion, NCU; brsvs -w), unusable for this user. Frozen (USUSP) jobs keep their slots, so the freeze
  freed no cluster slots.
- Killed the 3 PEND jobs (625412/625413/625414; nothing had run) and resubmitted with: -n 1 (was 2), CONC=16 (was 10), a fresh host list (ok or
  closed_Full, non-reserved, >= 1 free slot, no exp895 job running/frozen on it: 8 hosts), the same key slots (2/5/3), and the new launcher
  tools/lsf_test_window_v3.sh. New jobs: gepa_full s2 630947, miprov2 s1 630958, wikiskill s0 630968.
- tools/test_window.py --champion-first (opt-in; default order unchanged, backup .pre_champion_first.bak): all champion episodes run first and
  summary_champion_only.json is written (champion test score, no pairing) BEFORE the seed episodes; the paired summary.json follows if time allows.
  Boaz agreed that the seed cell may come last ("run the seed after the champion in case we have time"). registry.json records champion_first.
- tools/lsf_exclusive_wrapper.sh now treats a SUSPENDED (USUSP) job as occupying its host (lock owner check and the 'others' check), so a new job
  cannot land on a host that holds a frozen job's podman state. Replaced atomically; backup .pre_ususp.bak.
- tools/auto_test_launcher.py: new windows use -n 1, CONC=16, lsf_test_window_v3.sh (so ACE's window and any later ones get the same settings).
- ACE: Boaz: nothing to do for now; leave it running.
- Still PEND after the rebuild: all 8 hosts are `closed_Full` while MAX-NJOBS shows 5-40 free slots (e.g. cccxc515 88/128); LSF counts them full for
  reasons not visible to this user (blimits/badmin show nothing). The jobs start when any of those hosts opens.
- 2026-10-27 ~18:50Z Boaz: "Lets kill ACE s1 and s2". Killed by exact ID: ACE s1 (1952317, was USUSP at 447/2160, host cccxc552) and
  ACE s2 (1981027, was USUSP at 594/2160, host cccxc525); both now EXIT ("killed by owner"). Neither had a run_summary.json; their run dirs
  runs/ace/search_s1 and search_s2 are kept as they were (partial ledgers). ACE now has ONE seed: s0 (1,139/2,160, running). This is a decision
  to run ACE with a single seed; ACE s1/s2 will not appear in the final tables.
- 2026-10-27 ~19:10Z Rebuilt the host list for the 3 queued windows (Boaz: "yes rebuild it"): killed 630947/630958/630968 (all PEND, nothing run) and
  resubmitted as gepa_full s2 635481 (key 2), miprov2 s1 635485 (key 5), wikiskill s0 635486 (key 3); -n 1, CONC=16, v3 launcher, new list (8 hosts:
  cccxc443 502 505 515 525 582 585 709). Still PEND 2+ min later ("Job slot limit reached: 8 hosts").
- DIAGNOSTIC: two throwaway 5-second -n 1 probe jobs pinned to a single host (cccxc515, which shows 88/128 used, and cccxc443) also stayed PEND with
  "Job slot limit reached: 1 host" and were killed (635999, 636000). So the hosts reject ANY new one-slot job, not only ours: the cluster's usable
  pool is full from the scheduler's point of view. MAX-NJOBS arithmetic (5-40 "free" slots) does not reflect what LSF will dispatch.
- Our footprint: 9 running (30 slots), frozen jobs 7 left after killing ACE s1/s2 (frozen jobs keep their slots).
- 2026-10-27 ~19:15Z Boaz: "Yes. do that" (refresh the pending windows' host lists as running jobs finish). New tool tools/refresh_pending_hosts.sh:
  `bmod -m <fresh list>` on every PEND exp895_test_* job (keeps queue position; no resubmission; --dry-run supported). Fresh list = ok/closed_Full,
  non-reserved, >= 1 free slot, no exp895 job running or suspended on it. Applied to 635481/635485/635486. Expected releases: SkillOpt s2 window
  (cccxc547) in < 1 h, SkillOpt s1 window (cccxc713) ~3 h, CapEvolve s0 window (cccxc598, 8 slots) ~6 h; the watcher re-runs the refresh when a job ends.
- 2026-10-27 ~19:30Z Boaz: "kill the waiting jobs and resubmit". Killed 635481/635485/635486 and resubmitted WITHOUT -m (LSF may use any host; the exclusive
  wrapper still stops a start on a host that holds an exp895 job, running or suspended): gepa_full s2 644429 (key 2), miprov2 s1 644430 (key 5),
  wikiskill s0 644432 (key 3); -n 1, CONC=16, v3 launcher. runs/.watch/no_refresh created so tools/refresh_pending_hosts.sh leaves them alone.
  They are PEND again ("Job slot limit reached: 118 hosts") -> NOT a host-list problem.
- DIAGNOSIS (bqueues -l normal): the queue has FAIRSHARE scheduling; boazc priority is 0.000 (68 jobs started, ~20.7 M run-time seconds = ~5,750 slot-hours
  charged) vs 0.333 for users with no recent usage; ~30,000 jobs pend in the queue. Freed slots go to higher-priority users first, so our new
  jobs wait. This explains why probes, rebuilt host lists and unrestricted resubmission all pend identically.
- 2026-10-27 ~20:25Z The three resubmitted windows started: gepa_full s2 644429 (cccxc532), miprov2 s1 644430 (cccxc615), wikiskill s0 644432 (cccxc620); each alone
  on its host. SkillOpt s2 test window DONE (job 390669, TEST_JOB_RC=0, killed by exact ID): champion 0.767, seed 0.632, delta +0.134 [0.093, 0.175], n=278.
  Whether the removal of -m or the end of the long wait started them is unknown (fair-share priority was 0.000 throughout).
- [v2-session] 2026-10-28 05:04Z: capevolve_v2 s0 TEST WINDOW DONE (job 532687, TEST_JOB_RC=0, left the queue by itself). Held-out test, 280/280 tasks paired, 0 missing:
  seed 0.643 -> champion (cand_0003) 0.718, paired delta +0.075, SE 0.019, 95% CI [+0.038, +0.112]. 2 infra rows retried. summary.json written.
  s2 window at 97% (1623/1680), s1 at 75%.
- [v2-session] 2026-10-28 08:20Z: ALL THREE capevolve_v2 test windows DONE (TEST_JOB_RC=0 each; no capevolve_v2 job left in LSF). Held-out test, 280 tasks paired, 0 missing, 0 candidate errors:
  s0 (cand_0003): seed 0.643 -> 0.718, delta +0.075 (SE 0.019) | s1 (cand_0003): seed 0.657 -> 0.725, delta +0.068 (SE 0.018) | s2 (cand_0005): seed 0.592 -> 0.735, delta +0.143 (SE 0.023).
  Between-seed analysis: the three CHAMPIONS are statistically the same (0.718 / 0.725 / 0.735; pairwise differences <= 0.017, SE ~0.015-0.019). The spread in the gains comes from the SEED ANCHOR:
  the identical seed capability scored 0.643 / 0.657 / 0.592 in the three windows (s2 window lower by 0.05-0.065, SE ~0.016). Cause not identified (see report); no data error found
  (infra rows 2/4/1 of ~1,682, all retried; 840 scored trials per cell in every window; no error_text on any scored row).

## 2026-10-28 ~08:40Z — Resumed 3 of the 7 frozen searches (Boaz: "lets do that. resume the three closest to done first")
- Context: every competitor except ACE has >= 1 finished test; Gemma failure share 0.0% in the last hour; ACE s0 at ~110 rollouts/h (1,786/2,160).
- Resumed one at a time with `bresume` and watched the first minutes: GEPA-full s1 (1952679, 1,713/2,160) at 08:25Z, GEPA s0 (343227, 1,369) at 08:31Z,
  MIPROv2 s2 (1986371, 1,366) at 08:35Z. No error burst on resume for any of the three (Gemma calls 200/200; rollout rows clean 'none', a handful of
  'candidate' rows from GEPA-full s1's first evaluation and 1 infra row on GEPA s0).
- Still frozen (4): GEPA s2 (1967734, 1,126), MIPROv2 s0 (1986368, 959), WikiSkill s1 (420040, 837), GEPA-full s0 (184587, 564). Decision pending.

## 2026-10-28 ~23:25Z — State after the resume round (Boaz: "resume the three closest to done")
- Resumed searches finished: GEPA-full s1 (2,124/2,160, champion val 0.842), GEPA s0 (2,077, champion val 0.883, 1 iteration skipped by IterationSkip),
  MIPROv2 s2 (2,142, champion val 0.817). Hung search jobs killed by exact ID (1952679, 343227, 1986371). Their test windows (champion-first, v3 launcher,
  -n 1, CONC 16, dedicated keys): GEPA-full s1 811943, GEPA s0 855255, MIPROv2 s2 858715.
- ACE s0 finished: search 2,125/2,160 (champion pb_bb5581e14fe2, val 0.800), test champion 0.621, seed 0.606, delta +0.015 [-0.030,+0.061]: no measurable gain.
  ACE has a single seed (s1/s2 were killed). EVERY competitor now has >= 1 finished test seed.
- Means over finished seeds (test delta): GEPA-full +0.152 (1), MIPROv2 +0.135 (1), SkillOpt +0.119 (3), GEPA +0.100 (1), CapEvolve v2 +0.095 (3),
  CapEvolve v1 +0.090 (3), WikiSkill +0.089 (1), EvoSkill +0.087 (3), Trace2Skill +0.054 (3), Meta-Harness +0.052 (3), ACE +0.015 (1).
- Still frozen (4): GEPA s2 (1967734, 1,126), MIPROv2 s0 (1986368, 959), WikiSkill s1 (420040, 837), GEPA-full s0 (184587, 564). WikiSkill s2 parked (no job).

## 2026-10-29 ~16:25Z — Complete three seeds per competitor (Boaz: "unsuspend the suspended ones ... complete the runs so each competitor has three seeds")
- MIPROv2 s2 test DONE (job 858715 killed by exact ID): seed 0.638 -> champion 0.700, delta +0.062 [0.023, 0.101], n=280.
- Seeds with 3 finished tests: SkillOpt, Trace2Skill, Meta-Harness, EvoSkill, CapEvolve v1, CapEvolve v2. Missing one: GEPA (s2), GEPA-full (s0), MIPROv2 (s0).
  Missing two: WikiSkill (s1, s2), ACE (s1, s2).
- Resumed (bresume, one at a time, all back in RUN): GEPA s2 (1967734, 1,126/2,160), GEPA-full s0 (184587, 564), MIPROv2 s0 (1986368, 959),
  WikiSkill s1 (420040, 837).
- WikiSkill s2 (engine_error, 991/2,160, job gone): summary/champion moved to *.engine_error5_20261029, resumed with RESUME=1 on key 5 (fixed arm with resume waits):
  exp895_wikiskill_s2_resume_k5 = 942459.
- ACE s1 (445/2,160) and s2 (641/2,160) were killed earlier and ACE has NO resume path (its run dir cannot be reopened by lsf_ace_search.sh). Restarting
  them FROM SCRATCH with the original budget R=2,160, the same seeds and settings: old run dirs moved to runs/ace/search_s{1,2}.killed_partial_20261029
  (kept for the record). New launcher arms/ace/lsf_ace_search_keyed.sh (= original + `GW_RITS_KEY_SLOT=${KEY_SLOT}`). Jobs: ace s1 942457 (key 2),
  ace s2 942458 (key 3), -n 2, exclusive wrapper, no -W. The restart discards their ~450-640 rollouts each (they could not be resumed).
- 2026-10-29 ~16:40Z Boaz: "For ACE we said we will try to improve the infra, number of workers, batches ... and try again". Earlier note (history): ACE's pace comes from
  its design (batch K=4 in sequence, TEST_WORKERS=CONC/3=3 val tasks at once, CONC=10) and from a Gemma timeout/shared key, not from the budget.
  The two fresh ACE restarts (942457/942458, CONC=10, 12 rollouts spent) were killed by exact ID (run dirs -> search_s{1,2}.killed_lowconc_20261029)
  and resubmitted with CONC=16, TEST_WORKERS=5 (up to 15 rollouts at once in val evals), dedicated keys 2 and 3, gateway Gemma timeout 300 s:
  ace_s1_c16 = 943905, ace_s2_c16 = 943906. Budget R=2,160, K=3, batch K=4/ComBEE groups unchanged (those are ACE's published settings), so the comparison
  stays equal-budget. Scores are unaffected by concurrency.
- 2026-10-30 ~02:30Z WikiSkill s2 test window (961156, cccxc709, key 6, CONC 16) stalled at 862/1,680 episodes for 2 h (last results row ~1 h+ old, gateway 4-5 calls/30 min,
  calls ~290 s each; job alive, no traceback). Killed by exact ID and resumed with tools/lsf_test_window_resume.sh (keeps the 862 final episodes, registry/hash checks) as
  exp895_test_wikiskill_s2_resume_k5, key 5, CONC 16. results.jsonl backed up as results.jsonl.pre_resume_20261030.bak. First resubmit with a 1-host list (984598) pended
  (slot limit) and was killed; resubmitted with no -m.
- 2026-10-30 ~06:10Z FINDING (no action taken): ACE s2 (943906) counter jumped 504 -> 1,302 in ~1 h, but 798 of those rollouts are CANDIDATE_HELPER_GATE failures
  (every candidate since row 506 carries skills/ace-playbook/scripts/read_sheet_raw.py, lint "branches on task identity" at lines 45/47; 76 candidates, none run, scored 0, counted).
  Its one val eval (pb_e245245dcdc2, 708 spent) = 0.0. ACE s0 had 0 gate failures; ACE s1 so far 0. Waiting for Boaz's call: leave / kill and restart / stop early.
- 2026-10-30 ~06:20Z ACE s2 search ended (ACE_RC=0, stop "next batch + final val would exceed R", 2,136/2,160 rollouts, 53 batches, 198 candidates) with champion = SEED:
  all 3 val evals scored 0.0 because every candidate carried skills/ace-playbook/scripts/read_sheet_raw.py, which the common helper gate rejects (lint "branches on task identity", lines 45/47);
  798 gate-failed rollouts counted. Champion hashes equal the seed's. Auto-launched test window 1003519 (key 1) = seed vs seed. Hung search job 943906 killed by exact ID (ACE_SEARCH_DONE printed).
  Pending Boaz's call: keep the window (recommended; same as Trace2Skill s0 / EvoSkill s0 inert champions), or rerun ACE s2.
- 2026-10-30 ~08:10Z WikiSkill s2 test DONE: seed 0.635 -> champion 0.748, delta +0.115 [0.070, 0.159] (CR1 SE 0.023), n=279 paired tasks, infra-missing 6 trials, candidate errors 0.
  Finished-but-hung resume job 984640 killed by exact ID (TEST_JOB_RC printed). WikiSkill now has 2 finished test seeds (s0, s2); s1 search at ~1,796/2,160.
- 2026-10-30 ~11:10Z Boaz: ACE s2 -> option 1, "keep it". The ACE s2 test window (1003519, seed vs seed, champion = seed, champion-only score 0.640) runs to completion and
  ACE s2 is reported as a finished-but-inert seed (like Trace2Skill s0 / EvoSkill s0): in the tables its delta is ~0 and it is flagged as "champion = seed (helper-gate failures)".
  No rerun of ACE s2. ACE s1 (job 943905) continues as the second real ACE seed.
- 2026-10-30 ~11:20Z WikiSkill s1 search ended (WIKISKILL_RC=0, stop budget_R, 2,007/2,160, next eval of 154 would exceed R; champion it008_a1a576e16394). Auto-launched test window 1029617 (key 3, cccxc443).
  Hung search job 420040 killed by exact ID after WIKISKILL_SEARCH_DONE printed.
- 2026-10-30 ~15:10Z ACE s2 test DONE (inert: champion = seed): seed 0.640, champion 0.640, delta 0.000 [-0.027, +0.027], n=280, infra-missing 0. Same scores because both cells score the identical agent
  (registry inert_champion=true). Hung window job 1003519 killed by exact ID (TEST_JOB_RC printed). Per Boaz's option 1, reported as a finished-but-inert seed.

## 2026-11-01 ~06:10Z — Catch-up after a ~36 h gap (the Claude session stopped on a model budget limit; LSF jobs kept running)
- Finished during the gap: MIPROv2 s0 test +0.093 (seed 0.643 -> 0.736, n=280); WikiSkill s1 test +0.086 (0.594 -> 0.680, n=280).
  Searches ended on their budget rule, no error: GEPA s2 (2,137/2,160, champion cand_2c34a15270ca), GEPA-full s0 (2,141, a7e551f1bccfece0),
  ACE s1 (2,076, champion pb_d60484505a3b, best val 0.733, 0 helper-gate failures).
- 05:57-06:03Z launched the 3 missing test windows via auto_test_launcher: gepa_full_s0 1252801 (key 2), gepa_s2 1252800 (key 2), ace_s1 1252802 (key 3). All REGISTERED and scoring.
- Budget audit (all 27 searches): ledger counted == budget_state.json everywhere; max 2,159 (MIPROv2 s0); none over R=2,160.
- Finished-but-hung jobs still holding slots (end marker printed, or GEPA_ARM_DONE with the shell stuck ~38 h): 184587, 1986368, 1057365, 1029617, 943905, 1967734.
  The exact-ID bkill was refused by the session's permission classifier; waiting for Boaz to approve or kill them himself.
- 2026-11-01 ~06:15Z Boaz approved; killed by exact ID: 1967734 184587 1986368 1057365 1029617 943905 (all now EXIT). Only the 3 test windows remain: 1252800 gepa_s2, 1252801 gepa_full_s0, 1252802 ace_s1.
- 2026-11-01 ~13:35Z GEPA-full s0 test DONE: seed 0.626 -> champion 0.771, delta +0.145 [0.102, 0.188], n=280, infra 0, candidate errors 0. Window job 1252801 killed by exact ID after TEST_JOB_RC. GEPA-full now 3 of 3.
- 2026-11-01 ~13:45Z ACE s1 test DONE: seed 0.602 -> champion 0.707, delta +0.105 (+-0.044), n=280. Window job 1252802 killed by exact ID after TEST_JOB_RC. ACE now 3 of 3 (s2 inert).
- 2026-11-01 ~16:40Z GEPA s2 test DONE: seed 0.608 -> champion 0.683, delta +0.075 [0.034, 0.116], n=280, infra 0, candidate errors 0. Window job 1252800 killed by exact ID after TEST_JOB_RC.
  ALL 33 SEEDS DONE: every arm (10 competitors + CapEvolve v1/v2) has 3 finished test seeds (inert champion = seed: Trace2Skill s0, EvoSkill s0, ACE s2). No exp895 jobs left.
