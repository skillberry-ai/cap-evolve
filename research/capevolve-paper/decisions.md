# Decision log

Format: date (UTC) — decision — rationale — reversible?

- 2026-10-11 — Campaign branch `research/capevolve-paper-20261011` created from origin/main `e3cb513` (== reviewed SHA; main has not moved). Worktree `/home/dev/projects2/cap-evolve-campaign`; upstream tracking unset so nothing is pushed to main by accident. — isolation from user work in `/home/dev/projects2/cap-evolve` (clean tree, untouched). — yes.
- 2026-10-11 — No repository or user campaign cap found → adopt the mandate's fallback envelope verbatim in `campaign.yaml` (72 h, $50 preflight, $1000 total, 10k rollouts, 100M tokens, 25 % reserve). — mandate default. — tighten only.
- 2026-10-11 — Experiments will run LOCALLY on this host (it reaches the IBM LiteLLM gateway, RITS and Azure; 64 cores / 500 GB / sudo / podman), not through GitHub CI's self-hosted `ibm-vpc` runner. — local execution gives us control of isolation, scheduling and per-call accounting; CI runner availability is not under our control. — revisit if a benchmark needs the CI runner's images.
- 2026-10-11 — Received documents (literature review, plan, old draft, post, 64 PDFs) are treated as hypotheses to verify, not authority. PDFs are kept in the scratch store (not committed; redistribution licenses unchecked); only hashes/URLs are committed in `literature/pdf_manifest.json`. — mandate + licensing. — no.
- 2026-10-11 — Credentials loaded only by `campaign-scratch/scripts/provider_env.py`, which never prints values; probe logs record status/model id/latency/usage only. — mandate. — no.
