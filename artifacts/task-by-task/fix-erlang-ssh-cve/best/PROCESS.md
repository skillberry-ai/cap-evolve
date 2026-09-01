# PROCESS — what I did this iteration (explainability; REQUIRED)

## Decision summary
**No skill edits shipped this iteration — champion (seed) preserved deliberately.** After
full diagnosis, every candidate edit fails the THREE TESTS (fails SAFE + VERIFIED). Shipping
a refuted, regression-causing edit to appear productive is the exact anti-pattern the
discipline forbids ("the only brake on breadth is regression; drop any edit that doesn't pass
the three tests"). Rationale below.

## Ranked issue list (clusters by # failing trials × recoverable score, biggest first)
| rank | cluster | trials | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | infra build timeout | t2, t8, t9 (3/10) | `make` builds the whole `otp_src_27.3.2` tree (eunit, ssh, …) and hits the 2400s wall; variance in build time, NOT skill content | INFRA-NOISE (not a skill defect) | none — explicitly "do not optimize against it" |
| 2 | illegal-in-guard compile error | t5 (1/10) | agent wrote `when not (element(1,StateName)==connected orelse renegotiation(StateName)) ->`; `renegotiation/1` is a local fn call in a `when` guard → `ssh_connection_handler.erl:760:54: ... illegal in guard` → build.sh rc≠0 → test_00_build_sh_output / test_ssh_works / test_exploit all fail | KNOWLEDGE/BEHAVIORAL | (candidate) erlang-otp-behaviors body/script — REJECTED as unsafe/unverifiable below |

## Changes made this iteration
None. See "Deliberately skipped" for the per-cluster justification.

## Verify-the-fix
- Not applicable — no edits shipped.

## Why the only real cluster (t5) yields no shippable edit (the THREE TESTS)
- **REAL:** ✓ t5 is a genuine failure in this iteration's trajectories (illegal-in-guard).
- **SAFE:** ✗ The observed blast radius of adding content to `erlang-otp-behaviors` (the
  skill that governs gen_statem guards) is *regression*: cand_0001 (prose + linter) → val
  0.40; cand_0002 (minimal, zero-runtime prose pitfall) → val 0.30. Both dropped ~0.20–0.30
  below the 0.60 seed. Extra reading plausibly lengthens rollouts on a task where 3/10 trials
  already die at the 2400s wall, and even the minimal-prose variant regressed.
- **VERIFIED:** ✗ Max recoverable real signal is t5 = +0.10 (1 of 10 trials). The timeout
  trials inject ±0.30 variance, so a +0.10 fix cannot clear the significance/noise margin.
  Both prior fixes were "verified on paper" (correct diagnosis, correct guard rule) yet the
  gate REJECTED both — proving the metric here is noise-dominated and +0.10 is below the bar.

## The two remaining levers, and why neither is positive-EV
1. Re-fix t5 (prose or script). Both forms are already REFUTED (cand_0001 linter/prose,
   cand_0002 prose). JOURNAL forbids re-testing them. No un-tried form is safer: the miss is
   a single syntax rule the agent already "knows conceptually," so more prose it will skip
   does little (guidance), and the script form was rejected + added runtime.
2. Trim skills to shorten rollouts / reduce timeouts. Rejected: (a) instructions classify the
   timeouts as "uncontrollable noise, not a skill defect; do not optimize against it"; (b) the
   2400s wall is dominated by compiling the entire OTP source tree (`make[3]` over eunit/ssh/
   …), not by skill reading time — trimming won't move it; (c) trimming risks removing content
   the 6 passing trials rely on → real breakage, strictly worse than noise.

## Process & features used
- Subagents/worktrees: not used — single-task, single genuine cluster, and the decision is a
  diagnosis+risk judgment, not a fan-out of independent edits. Serial inspection of the 10
  trajectories + the two prior iterations was sufficient and cheaper.
- Prior iterations read (RUNMAP + ./prior_iterations/): cand_0001 (prose section + mandated
  guard linter → rejected 0.40) and cand_0002 (minimal prose pitfall → rejected 0.30). Learned:
  the correct t5 diagnosis is already established; both fix forms regressed via noise; the
  only recoverable non-noise signal (+0.10) is below the significance bar.

## Good things to PRESERVE (do not let a future iteration undo these)
- The seed guard behavior: 6/10 trials correctly write guard-safe `?CONNECTED(StateName)`
  guards and pass. Do NOT rewrite erlang-otp-behaviors guard guidance — it already elicits
  the correct pattern in the majority of trials.
- Do NOT re-add the guard-restriction prose section or the guard linter script (both refuted).
- Do NOT pad candidates with content additions to erlang-otp-behaviors — every observed
  addition regressed the val.

## Deliberately skipped (cluster + why)
- **Cluster 1 (timeouts t2/t8/t9):** infra build noise; instructions forbid optimizing it;
  root cause is OTP full-tree build time, not skill content.
- **Cluster 2 (t5 illegal-guard):** genuinely real but not safely/verifiably fixable — the
  two fix forms are refuted and regressed, and +0.10 is below the noise floor. Re-shipping a
  refuted edit would risk sinking the 0.60 champion for no reliable gain.
