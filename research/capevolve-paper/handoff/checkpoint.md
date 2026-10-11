# Checkpoint — 2026-10-11 ~08:45 UTC

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
