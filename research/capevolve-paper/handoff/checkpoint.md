# Checkpoint — 2026-10-11 ~00:45 UTC

- Branch `research/capevolve-paper-20261011` @ see `git log -1`; worktree `/home/dev/projects2/cap-evolve-campaign`; base `e3cb513`.
- Issues: index #735; backlog #736–#754 (`issues.json`).
- Scratch store: `/home/dev/projects2/campaign-scratch` (venv, scripts/, logs/, papers/ (64 PDFs, hash-verified), inputs/ (extracted handoff ZIPs), issues/).
- Installed on host: libreoffice-calc, texlive (dnf, exit 0). podman rootless; no docker binary.
- Active subagents (background): lit-lead, repo-auditor, provenance-auditor, bench-steward, stats-reviewer. Their outputs land in literature/, audit/, protocol/, reviews/, analysis/scripts/.
- Provider reservations: none in flight. Preflight spend so far: ~25 tiny probes + 72 concurrency-probe requests (~150k tokens total, proxy cost < $0.50).
- Pending decisions: token-cap accounting for cache reads; final model selection; fresh final-test set (280 SkillOpt test likely dev-exposed — awaiting exposure ledger).

## Resume
```
cd /home/dev/projects2/cap-evolve-campaign && git pull --ff-only
cat research/capevolve-paper/STATUS.md research/capevolve-paper/handoff/checkpoint.md
python3.12 -I /home/dev/projects2/campaign-scratch/scripts/provider_env.py   # redacted provider check
```
