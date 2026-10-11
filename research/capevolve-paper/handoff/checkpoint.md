# Checkpoint — 2026-10-11 ~11:20 UTC

Branch `research/capevolve-paper-20261011` (see `git log -1`); index #735; backlog #736–#754; defects #755–#766; provenance #767–#778, #782, #784; design #785; PR #779 (changes requested).

## Live processes
- Campaign gateway: `python3.12 -I /home/dev/projects2/campaign-scratch/scripts/campaign_gateway.py --port 4111` (restart: find the PID via /proc cmdline; do NOT `pkill -f` from a shell whose command line contains the pattern). Live caps: `campaign-scratch/logs/caps.json`. Call log: `logs/gateway_calls.jsonl` (ledger replays on restart).
- E10 searches (Suite A): skillopt s0–s2, gepa s0–s2 (baseline-eng; `runs/E10/<m>/s<k>/`), metaharness s0–s2 (bl-harness). Being parallelized/relaunched under gold isolation.

## Worktrees (agent-owned)
wt-paper-mode (PR #779), wt-sb-gold (gold isolation), wt-run (integration f5906110b: campaign + #779 + gold isolation), wt-tau (Suite B), wt-algo (algorithm improvements).

## Agents
repo-auditor (fixing #779), bench-steward (gold-isolation PR), provenance-auditor (idle), lit-lead (idle), stats-reviewer (idle), baseline-eng (GEPA/SkillOpt/EvoSkill), bl-skills (Trace2Skill/CoEvoSkills/GraphSkillEvo), bl-context (ACE/MIPROv2), bl-harness (Meta-Harness/HarnessLens/VERSE), bl-harness2 (AHE/MCE/RHO/Memento), bl-wikiskill (reimplementation), capevolve-runner (HC/AO Suite A), tau-runner (Suite B), algo-eng (#785 + merge + screen accounting), design-writer (done).

## Spend (gateway, 08:40 UTC)
9.0M tokens total: 8.8M RITS (uncapped), 0.28M capped; priced proxy ≈ $0.2.

## Pending decisions
Suite A fresh final set (912-residual vs SpreadsheetBench 2); matrix fit (wall time / non-RITS tokens) after pilots; ablation selection.

## Resume
cd /home/dev/projects2/cap-evolve-campaign && git pull --ff-only; read STATUS.md, decisions.md tail, this file; `curl localhost:4111/health`; `python3.12 -I /home/dev/projects2/campaign-scratch/scripts/spend.py E10`.

## Update 11:20 UTC
- Merged into campaign branch: #779, #783, #786, #788, #790, #791, #792 (head see git log). None to main.
- MATCHED-CHECKPOINT PROTOCOL (user decision): SEARCH CUTOFF 2026-10-13 06:00 UTC; B* from counters only; artifact = method's own selection at B*. Runner brief: campaign-scratch/baselines/CHECKPOINT_PROTOCOL.txt. Session cron jobs (die with session!): one-shot cutoff at 2026-10-13 06:00 UTC; 3-hourly health check at :17. If the session restarted, re-create them.
- Rule P campaign values: k_se 1, n_conf 3, z_conf 1.282, dmin 0, min_coverage 0.95 (both CapEvolve arms).
- Suite A running (Tier 1): GEPA×3, SkillOpt×3 (baseline-eng), Meta-Harness×3 (bl-harness, container-isolated), EvoSkill×3 (baseline-eng, capopt mount-ns), Trace2Skill×3 (bl-skills); pending launch: CapEvolve HC×3/AO×3 (capevolve-runner), WikiSkill community×3 (bl-wikiskill), ACE×3/MIPROv2×3 (bl-context). Tier 2 exploratory paused for capacity (GraphSkillEvo, MCE, Memento s0; STOPPED.json).
- Suite B (tau-runner): relaunching HC/GEPA with judge azure/gpt-5.5 + rule P parity; AO, controls, HarnessLens (container-isolated) pending.
- Failed reproductions: VERSE, CoEvoSkills; HarnessLens Suite A (moved to B).
- Design page v2: research/capevolve-paper/design/experimental_design.html (+ generator/).

## Update 13:00 UTC (periodic check)
- No 3h stalls. CapEvolve main seeds not launched (chased capevolve-runner). Suite B relaunch ordered (tau-runner).
- Tier 2 paused; AHE prepared for Suite B (no launch). RHO paused after smoke.
- Caps OK: non-RITS 4.5M/100M, $12.81/$1000 proxy.

## Update 16:20 UTC (periodic check)
- Gateway upgraded 13:11 (transparent upstream retry; priority; finish logging). Since then 0.34% non-200: gpt-oss harmony-parse 500s (Suite B, infra classification being confirmed) + Claude CLI output_config 400s (retried by CLI).
- AO runs the digest/act engine (active_eval on) with rule P on both suites. CapEvolve Suite A main seeds started 14:42.
- Suite B v2 (12:44) + isolation shim (14:57) + AO engine correction (15:45).

## Update 19:16 UTC (periodic check)
- No stalls; gateway healthy (101.7k calls, not blocked). Caps OK: non-RITS 15.2M/100M; $47.18/$1000 proxy.
- COORDINATOR ERROR fixed 18:40: E10-evoskill/E10-harnesslens/probe were left in caps.json low_priority_tags after EvoSkill promotion; EvoSkill restarted 18:28 on canonical tags (pre-18:28 data invalid).
- Suite C (airline) launched; tau-runner monitors B and C every 2h. HarnessLens (bl-harness) trial e2e9 still running; hand-over to tau-runner pending.
- Cron jobs are session-only: cutoff one-shot b76737e4 (2026-10-13 06:00 UTC), 3-hourly check 82e47de9.

## Update 21:50 UTC (periodic check)
- Gateways: :4111 (main) and :4112 (Azure-direct, azoai/<dated deployment>). Both healthy.
- Agents active:
  - paper: paper-core, paper-results, paper-lit;
  - measurement and runs: stats-reviewer, metering-auditor, final-eval-eng (building bstar/reconstruct/order/run_final/freeze), provenance-auditor, capevolve-runner, tau-runner, bl-harness, bl-context, baseline-eng.
- Pending:
  - HarnessLens hand-over;
  - ACE batch restart;
  - E12C best-of-k (after the C controls);
  - closing Suite B sealed-file visibility (tau-runner);
  - final-eval machinery dry run.
- Token budget plan in decisions.md (65M stop order).
- Session-only crons: 3-hourly check and the cutoff one-shot. Re-create them if the session restarts.
