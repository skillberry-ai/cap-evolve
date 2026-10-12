# Silent environment failures across all arms (read-only audit)

Auditor: metering-auditor. Snapshot 2026-10-12 09:50 UTC. Nothing was restarted, killed or edited in any run dir. Evidence sources: per-run
`events.jsonl`, `graph.jsonl`, `eval_index.jsonl`, rollout JSONs, launcher/driver logs, the optimizer session transcripts (tool-result error
lines only), `manifest/tainted.json`, the gateway log, and a scan script (`analysis/scripts/scan_silent_env_failures.py`, output
`analysis/out/metrics/silent_env_scan.json`). "Proposed" = candidates created beyond the seed; "evaluated" = reached at least one scored rollout.
Counts are per seed s0/s1/s2 unless stated.

## Verdicts

| suite | arm | proposed | evaluated | dominant failure strings (count) | verdict |
|---|---|---|---|---|---|
| B | **HarnessLens** | 0 / 0 / 0 reached a rollout (stage `analyzer_complete`, `rollout_jobs` 0, 98 baseline trials only) | 0 / 0 / 0 | s1: `review_decision: materialization_failed` x44 and `materialization_error: bubblewrap is required for isolated Harness Editor calls` x14 (last at 09:42:16, 10 s after `bubblewrap` was installed at 09:42:06; s1 was last resumed 09:23:54, before the install). All seeds: `"error": "ripgrep execution failed"` in OpenCode tool results (s0 24, s1 44, s2 40; the `rg` binary exists in the OpenCode cache of some runtime dirs, so the cause is unresolved). s2: `BadGatewayError ... timed out` x18. | **SUSPECT** |
| A | hill-climb (E10) | 3 / 4 / 4 | 3 / 4 / 1 (+cand_0004 in progress on s2) | s2: `RuntimeError: agent view dir ... is not empty and was not created by this adapter` x3 (cand_0002, cand_0003, cand_0004 first attempt); the framework aborted with "3 consecutive candidate evaluations raised - this looks like a broken environment" (03:26) and was restarted 08:26. s0: cand_0002 val screen is INVALID (21/40 `NO output file`, mean 0.34 vs ~0.79), already recorded in `manifest/tainted.json`. | **SUSPECT** (3 of 11 proposals on s2 never ran; s0 cand_0002 contaminated; both labelled rejected/indecisive in the metrics) |
| A | hill-climb stock gate (E12A) | 6 / 8 / 8 | 5 / 7 / 7 | seed TRAIN baseline (80 rollouts) INVALID after the 03:02Z daemon hot-swap (`NO output file`, 78-85 of 120 seed rollouts score 0; `tainted.json` on all three seeds). Candidates and val seed are fine. | CLEAN for candidates; seed-train score must not be used |
| A | agent-optimize (E10) | 1 / 1 / 1 | 1 / 1 / 1 | optimizer: `Claude requested permissions to read .../agent-optimize/SKILL.md` x1 each; `ls: cannot open directory '.': Permission denied` x1-2 (capopt ACL). Running. | CLEAN (caveat) |
| A | EvoSkill | 7 / 8 / 8 | 7 / 8 / 8 | sandbox exec 500 x5 (infra, uniform rule) | CLEAN |
| A | GEPA | 20 / 9 / 17 | 10 / 6 / 9 (the rest rejected at the minibatch, by design: 10 `rejected` events) | sandbox 500 / timeout x7; `FileNotFoundError gepa_state.bin` in `to_candidates.log` x2 (converter run before the state file existed) | CLEAN |
| A | MIPROv2 | 6 / 10 / 8 | 5 / 9 / 7 | sandbox 500 x7 | CLEAN |
| A | SkillOpt | 7 / 7 / 8 | 6 / 6 / 7 | `task_template.md broke the placeholder contract - unknown placeholder(s): {(key1, key2)}` x120 rollouts (s0 step_0001 and step_0002, s2 step_0002: 3 of ~20 steps never made an LLM call, 0 turns). Candidate-induced, not host. | CLEAN for environment; note 3 steps never executed |
| A | Trace2Skill | 2 / 2 / 2 | 2 / 2 / 2 | sandbox 500 x9, LLM timeout x8 (26 infra rollouts in all) | CLEAN |
| A | Meta-Harness | 8 / 8 / 8 | 8 / 8 / 8 | sandbox 500 / `litellm.Timeout` x30 (infra) | CLEAN |
| A | WikiSkill | 1 / 1 / 1 (+S0) | 1 / 1 / 1 | `FileNotFoundError .../attempts/<h>/runtime/session.jsonl` repeated 6-7 times per seed in a once-a-minute crash-restart loop (23:52-23:57) after a sandbox 500 left an attempt without a session file; `RuntimeError: 1 tasks need attention`. Progress is slow (one evaluated iteration per seed in ~10 h) but it resumes. | CLEAN (caveat: crash-loop on infra) |
| A | ACE | 17 / 11 / 10 playbook versions | 17 / 11 / 10 | sandbox 500 x2 | CLEAN |
| A | agent-optimize / hill-climb optimizer environment | n/a | n/a | tool results in optimizer sessions: `patch: command not found` (B hc s1 x7, C hc s0 x1), `ModuleNotFoundError: No module named 'tau2'` (x2 per run) and `'loguru'`, `Read-only file system: tools.py` (C ao s0 x1). `patch` and `rg` are not installed on the host (checked as uid capopt). | see Findings 4 |
| A | MCE, Memento, GraphSkillEvo | n/a | n/a | STOPPED by the coordinator for capacity, not by an error (`STOPPED.json`); MCE s0 `run.log` has one `ModuleNotFoundError: No module named 'sb_eval_lib'` | NOT RUN |
| B | hc | 1 / 7 / 1 | 1 / 7 / 1 | optimizer: `patch: command not found` x7 (s1), `No module named 'tau2'` x2; user-simulator `###STOP###` artifacts x3 (classified infra) | CLEAN (caveat) |
| B | agent-optimize | 6 / 6 / 6 | 2 / 2 / 2 (the rest are probe/gate stages by design) | optimizer: `Claude requested permissions to read ... agent-optimize/SKILL.md` and `legacy-SKILL.md` x5, x5, x7 (denied by Claude Code's path permission); `cat legacy-SKILL.md: No such file` x1 (s0); `ls tau2/data/.../user_simulator: No such file` x3 (s2); `cat run_main/rejected.jsonl: No such file` x3-5 | CLEAN (caveat: optimizer could not read its own SKILL.md) |
| B | ctl-oneshot | 1 / 1 / 1 | 1 / 1 / 1 | user-sim `###STOP###` x2 | CLEAN |
| B | GEPA | 13 / 17 / 19 | all with rollouts (42-46 eval ids) | none | CLEAN |
| C | hc | 2 / 3 / 4 | 2 / 3 / 4 | `patch: command not found` x1, `No module named 'tau2'` x2 | CLEAN (caveat) |
| C | agent-optimize | 2 / 2 / 1 | 2 / 2 / 1 | `source dir not found: .../candidates/cand_N` x1-2 (s0, s1: candidate registered before its directory existed), `Read-only file system: 'tools.py'` x1 (s0), SKILL.md permission denial x1-3 | CLEAN (caveat) |
| C | ctl-oneshot, GEPA | 1 each; 11 / 10 / 12 | all | `tau2 terminated for infrastructure reason` x1, user-sim STOP x1 | CLEAN |
| C-E12 | hcstock | 5 / 7 / 7 | 5 / 7 / 7 | none | CLEAN |
| C-E12 | best-of-k | 6 / 6 / 6 proposals | 6 scored each (`progress.json` opt scores) | none | CLEAN (in progress) |
| D | E20 CTL, P, PT, T and E21 ruleP (15 runs) | 0 beyond the seed | 0 (baseline phase; `rollouts_metrics.jsonl` empty) | gateway: target/user/judge 200, about 0.1 percent 500s; no optimizer call yet | NOT YET TESTABLE |
| D | E22-null chunks | n/a | n/a | `The response was filtered due to the prompt triggering Azure OpenAI's content management policy` x8 (400, `E22-null-c2` target); 500 x13 across chunks | CLEAN (note content-filter 400s) |

## Findings, ranked

1. **HarnessLens (B): zero candidates have ever reached a rollout.** s1 still logs `materialization_failed` after the install of bubblewrap
   (the run resumed at 09:23:54, 18 minutes before `rpm` shows bubblewrap installed at 09:42:06). s0 and s2 resumed 09:43:46, after the
   install, and show no `materialization_failed` so far. A nested probe (`unshare --user --map-root-user --mount bwrap --ro-bind / / true`)
   works, so bubblewrap itself is usable inside `hl_sandbox.sh`. **Action:** resume s1; keep checking `grep -c materialization_failed` in
   all three; separately look into `ripgrep execution failed` (present in baseline rollouts and in the harness editor).
2. **hill-climb s2 (A): three proposals never ran** because two evaluations collided on the agent-view directory after the 03:02Z daemon
   hot-swap (`eval_daemon` v2 pre-seeded `adapter._VIEWS` with a wrong key). The graph labels them `rejected` ("indecisive (evaluation
   error)") and the metrics count `rej 3`. They are infrastructure losses, not rejections; the optimizer spend on them is wasted. s0
   cand_0002 is the same bug (documented). **Action:** treat these as missing, not as candidate failures, in every acceptance and
   rejection count.
3. **The hot-swap also made E12A seed-train scores worthless** (all three seeds); documented in `tainted.json`.
4. **Missing host tools in the optimizer sandbox:** `patch` and `rg` are not installed (`sudo -u capopt which patch rg` finds neither),
   and the sandbox Python cannot import `tau2` or `loguru`. The CapEvolve optimizers worked around each failure (candidates still
   reached rollouts), but they spent turns on it and could not run local checks that import the tau2 package. Suite D optimizers will hit
   the same. **Action:** `dnf install patch` (or mount it), and make the venv python the default in the sandbox.
5. **agent-optimize cannot read its own SKILL.md** in B and C (Claude Code path-permission denial; 1-7 per seed) and, in one B seed, the
   legacy skill path is missing in the sandbox. The driver prompt carries the loop instructions, so candidates were produced, but this
   is a deviation from "stock agent-optimize" the paper should mention. Suite A agent-optimize shows the same denial once per seed.
6. **SkillOpt**: 3 of about 20 edit steps produced a `task_template.md` with an unknown placeholder, so the whole val batch scored 0 with no
   LLM call (candidate-induced, native feedback). It looks like an edit that writes braces into the template; worth a line in the deviations.
7. **Suite D has not produced a single candidate yet**: nothing to audit beyond the baseline gateway traffic. Re-run
   `scan_silent_env_failures.py` after the first optimizer iteration.

No other arm shows a repeated identical host-level error (missing binary, import error, sandbox permission denial) that stopped
candidates from materializing or running. Baselines that crashed and resumed did so on sandbox HTTP 500s (infra), not on missing dependencies.

## Suite D pass 1 (2026-10-12, requested early; GEPA counted ready once a reflected candidate had been evaluated)

24 cells (E20 CTL, P, PT, T, GEPA; E21 ruleP, 1S; E26 NOHIST), read-only. Every cell has proposed and evaluated candidates:
CTL 1/1 per seed, P 4/4, PT 4/3/3, T 2/3/4, GEPA 5/6/6 reflected candidates all evaluated (139 to 155 counted rollouts), E21 1S 2/2, E21 ruleP 4/4,
E26 NOHIST 1/1. Error strings: tau2 `INFRASTRUCTURE_ERROR` terminations (E20 T 17, PT 9, CTL 4, E21 1S 4, ruleP 1; about 1 to 2 percent of rollouts)
and user-simulator `###STOP###` artifacts (E20 P 9, T 4, PT 2, CTL 2, E21 1S 5, ruleP 3, E26 1), both already classed infra; one E21 1S s2
`INDECISIVE: only N% of val tasks produced a valid score`. Optimizer tool errors: `No module named 'pydantic'` (CTL, T, E26, one each) and a
missing `bench/src/tau2-.../.venv/bin/python` (PT, T, one each), each a single non-repeating probe by the optimizer, same class as the
intentional tau2/patch/rg gaps. No repeated identical host-level error, no cell with unevaluated proposals. **SUSPECT rows: none.**

## Suite D: tau2 INFRASTRUCTURE_ERROR terminations are candidate-correlated (read-only, 2026-10-12)

Source: `native_sims/<cand>/<split>/*.json` of every Suite D cell (E20, E21, E26): 3,493 non-seed and 1,272 seed simulations.
- **Seed: 0 of 1,272 infra terminations. Non-seed: 45 of 3,493 (1.3 percent).** Same-window gateway check: all D cells see Azure 429s (23 to 46 per
  cell in the 10:40 to 12:05 window), yet only the cells below show the spike, and E20-PT-s1 had no non-200 target call at all in its window.
- **Every one of the 45 ends immediately after a write-tool call** (`exchange_delivered_order_items`, `modify_pending_order_items`,
  `cancel_pending_order`, `return_delivered_order_items`, `modify_pending_order_address`): empty message list, duration 0, the sim `info.error`
  holds the last tool call and its result. None ends on a read tool or on an LLM call.
- Outliers (infra / rollouts, last tool): E20-T s0 cand_0002 12/49 = 24 percent (modify 7, exchange 5) and cand_0003 6/46 = 13 percent
  (modify 5, exchange 1); E20-PT s1 cand_0003 9/49 = 18 percent (cancel 7, modify 1, address 1); E21-1S s2 cand_0002 4/49 = 8 percent (cancel 4);
  E20-CTL cand_0001 4/197 over three seeds (exchange 3, modify 1). The same tasks under the seed and under sibling candidates are 0 of 12 (T s0)
  and 0 of 9 (PT s1); the infra tasks use the edited write tool far more often (T s0: modify on 8/12 infra tasks vs 4/37; PT s1: cancel on 8/9 vs 4/40).
- What the edits have in common: they change a write tool's return value or error behaviour (T s0 cand_0002 returns a dict with a `note` field from
  exchange/modify; PT s1 cand_0003 raises "NOT CANCELLED YET" on the first cancel of a multi-item order). A direct check shows the cancel logic itself runs
  (first call raises ValueError, second succeeds), so the exact exception that the harness converts to INFRASTRUCTURE_ERROR is not yet identified.
- **Verdict: SUSPECT mislabel.** These terminations are very likely candidate-induced and should not be excluded as infra. Under the uniform classifier
  they are currently `infra` (string "tau2 terminated for infrastructure reason") and would be dropped or retried rather than scored as candidate failures.
  Recommended: classify a tau2 INFRASTRUCTURE_ERROR whose last event is a write-tool result as `candidate`, or at least as `unverifiable`, and have the
  adapter owner capture the exception text (the sim JSON has none) before the final evaluation.
