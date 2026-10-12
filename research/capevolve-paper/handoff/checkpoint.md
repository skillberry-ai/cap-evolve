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

## Host changes to undo after the campaign (2026-10-11T22:22)
- systemd unit e10-capopt-egress.service (enabled) and /etc/e10-capopt-ip{,6}tables.rules: gateway-only egress for uid capopt. Remove after the campaign: `systemctl disable --now e10-capopt-egress`, then delete the rules files and flush the capopt OUTPUT rules.
- Check during every periodic check: campaign-scratch/runs/E10/_tools/capopt_egress.sh check.
- Also undo after the campaign:
  - ~/.config/containers/containers.conf (default_network=sb_internal) and the sb_internal podman network;
  - the gw_bridge process (baselines/gwbridge), which Meta-Harness, HarnessLens and the B/C shims depend on. Check it in periodic checks while the campaign runs.
  - system package bubblewrap-0.6.3-1.el9 (installed 2026-10-12 for HarnessLens' isolated Harness Editor calls): remove with `sudo dnf remove -y bubblewrap`.
  - second gw_bridge process for the Azure gateway (baselines/gwbridge/gw4112.sock, forwards to 127.0.0.1:4112), used by the Suite E HarnessLens sandbox: stop it after the campaign.

## Update 00:50 UTC 10-12 (periodic check)
- WikiSkill crashed on all 3 seeds at about 22:42 (session.jsonl missing); bl-wikiskill is fixing it.
- Trace2Skill is paused at about 200 (bl-skills checking). ACE batch restart: status asked of bl-context.
- Final-eval machinery: dry runs OK on RITS and Azure; the HarnessLens worker is validated with v0; the HL 8-task validation run is in progress.
- Token pace about 2.2M/h, projecting to about 98M at the cutoff. Apply the 65M stop order when reached, or ask the user to raise the cap.

## Update 03:50 UTC 10-12 (periodic check)
- No stalls. Infra retry hot-swapped into the CapEvolve daemons (03:02); GEPA and EvoSkill resume-restarted; ACE relaunched. MIPROv2 and MH stay on pre-rule handling.
- Root cause of most sandbox 500s: the jupyter.py drain bug. Fix behind SB_DRAIN_ERROR, final evaluation only. KERNEL_TIMEOUT_S: search 600, final 10800.
- Token budget: projection about 110M, over the cap. Asked the user whether to raise the cap or apply the stop order at 65M.

## Update 08:25 UTC 10-12 (periodic check)
- Stalls being checked: E10 hc s2 (counter at 200 for 5.3 h), E10B HarnessLens s1 (98 for 5.6 h).
- Meta-Harness s0 and s1 finished at 600 (val 0.975 / 0.875; val is optimistic because the proposer saw val aggregates).
- Token cap 150M; projection about 139M; stop rule at 125M/130M (decisions.md).

## Update 09:50 UTC 10-12 (periodic check)
- Capped 75.2M/170M (13M last hour, HarnessLens restarts). Stop rule 145M exploratory, 155M secondary.
- HarnessLens: no-bubblewrap environment defect found; bubblewrap 0.6.3 installed (undo: sudo dnf remove -y bubblewrap); s0/s2/hlext clean-cut restarts; s1 live refund.
- Amendment 8 + E26 no-history cell approved (experiment-designer registers; patch reviewed before merge).
- Review round 3 on draft4 (35b73dd7e) done; triage3 running. Resume: read draft4/TRIAGE.md, dispatch fixes.
- Silent environment-failure audit of all arms requested of metering-auditor (audit/silent_env_failures.md).

## Update 12:50 UTC 10-12 (periodic check)
- Capped 95.4M/200M (cap raised by the user); ladder 170/178/182M; 18M final reserve; capped watcher at 160M (background task in this session).
- Suite E admission loop (tau-runner) and E12B relaunch watcher armed. E26-nohist running with shim v2.
- Azure mini quota is the bottleneck; caps.json azoai:gpt-4.1-mini=15. Undo after campaign: remove bubblewrap, gw4112 bridge, plus earlier items.
- Resume: watch D searches ending (about 19:30-20:00), Suite E waves, the 06:00 cutoff (cron b76737e4) for A/B/C.

## Paper repo mirror (13:31 UTC 10-12)
- github bcarmeli/mlsys2027-cap-evolve-paper (private, main) mirrors research/capevolve-paper/ commit by commit, plus the built PDF and an Overleaf zip. The writer is the repo-sync loop, PID in campaign-scratch/logs/paper_repo_sync.pid (every 600 s). Stop with kill $(cat .../paper_repo_sync.pid). Restart with nohup python3.12 -I campaign-scratch/scripts/paper_repo_sync.py --loop 600.
- After the campaign, decide with the user whether to keep the loop running. It is a host process to stop.

## Update 15:50 UTC 10-12 (periodic check)
- Capped 111.8M/200M. ACE ledger guards (s1/s2) and HL-extended 10M watcher running; HL 3.5 h cumulative per-trial cap watcher running.
- Pending: ACE s0 final validation rerun, then reconstruct; E12B relaunch when B hill-climb ends; Suite E waves; 21:11 forecast; cutoff 06:00 (cron b76737e4).

## Update 18:50 UTC 10-12 (periodic check)
- Capped 125.6M/200M. Suite E wave 1 started. GEPA A s1 budget_cap (finalize from state pending, baseline-eng). Host loops: paper_repo_sync, metrics_commit_loop (pid file in campaign-scratch/logs), HL watchers, ACE ledger guards.

## Update 21:50 UTC 10-12 (periodic check)
- Capped tokens are 144.7M. Resume points are unchanged: the cutoff is 06:00 (cron b76737e4), with N*, reconstruct, freeze and final evals after it.
- v2 build: read research/capevolve-paper/improve/V2_PLAN.md. PRs target main.
  - PR-0 #814 is merged.
  - v2/gate is coded (PR-1).
  - #815 is HC-2.
  - Agents v2-gate, v2-ao2, v2-helpers and v2-hc2 are live.
  - Each PR gets a review agent, then fixes, then an admin merge.
  - Register amendment 11 (v2 runs on pooled F/C) before any rerun.
