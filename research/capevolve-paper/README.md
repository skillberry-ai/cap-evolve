# CapEvolve paper research campaign

Branch `research/capevolve-paper-20261011`, base `e3cb513`. Everything scientifically material for the
paper lives here or is linked from here; large raw artifacts live in the campaign scratch store with
hashes recorded in `experiments/manifests/`.

| path | purpose |
|---|---|
| `STATUS.md` | plain-language status: known / uncertain / next |
| `campaign.yaml` | budget envelope, concurrency, provider config locations (no secrets) |
| `decisions.md` | dated decision log with rationale |
| `claims.csv` | claim ledger: every paper claim → evidence → script → status |
| `literature/` | paper cards, `evidence.csv`, novelty matrix, `bibliography.bib`, PDF manifest (hashes only; PDFs are not redistributed) |
| `audit/` | repository/algorithm audit and historical-result provenance audit |
| `protocol/` | frozen measurement protocol, splits, model registry |
| `experiments/` | configs, run manifests, `registry.jsonl` (global experiment registry), `run_queue.jsonl` |
| `analysis/` | scripts that generate every table/figure from manifests |
| `paper/` | LaTeX manuscript |
| `reviews/` | independent review reports and responses |
| `handoff/` | `checkpoint.md` resumable state |
