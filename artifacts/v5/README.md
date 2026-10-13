# artifacts/v5/

## `seed/` — the original parsec skill

The 8-file multi-agent bundle (`orchestrator.md`, `shared_context.md`, six `*_agent.md`) that
`v5_b1_e1` evaluated zero-shot on all 136 v5 tasks. One shared copy: nothing in this arm was
optimized, so there is no `best/` and no per-task directory.

**Verified byte-identical (8/8 files) to parsec commit `28e2c40`'s `config/prompts/`**, checked
against a fresh clone of the parsec reference repo, and byte-identical to
[`../v4/seed/`](../v4/seed/) — the two arms' baselines are therefore the same skill.

That verification is not ceremonial. A previous run of the v5 baseline sweep (`v5_t1_e1`) was
discarded after its skill proved byte-identical to
[`../v4/v4_g_e1/rejected/cand_0001`](../v4/v4_g_e1/rejected/cand_0001) — a v4 **global optimizer**
candidate that had been left installed in the live parsec clone's working tree. parsec's git HEAD
still read `28e2c40`, so nothing in `git status` would have revealed it; only a byte comparison
did. It inflated the shared-task mean by +0.151. See
[`../../results/v5/v5_b1_e1/summary.md`](../../results/v5/v5_b1_e1/summary.md).

**Rule this leaves behind:** pin the artifact under test to a known commit and verify it by bytes
before running an arm. Do not copy whatever a live working tree happens to hold.
