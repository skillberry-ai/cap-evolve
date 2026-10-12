DRAFT, not posted. Proposed title: `[experiment] SWE-bench Verified with GLM 5.3 as agent and optimizer: clean design (Suite F) and what the 482/500 claim needs`
Proposed labels: `paper-experiment`, `honesty`. Related: #777, #774, #513, #306; PRs #673, #699.

## Summary

The colleagues report that after CapEvolve optimization with GLM 5.3 as agent and optimizer, a Harbor run over all 500 SWE-bench Verified instances solved 482 (96.4%). We treat this as the colleagues' reported internal result, not yet a leaderboard result: section 1 states what must be established before it can be claimed as one. This issue (1) lists what must be established before that number can be claimed, and (2) specifies a self-contained design that any agent can run to get a clean number. Full design, split files and hashes: [`research/capevolve-paper/designs/swebench_verified_experimental_design.md`](https://github.com/skillberry-ai/cap-evolve/blob/research/capevolve-paper-20261011/research/capevolve-paper/designs/swebench_verified_experimental_design.md) and `designs/swebench_assets/` on branch `research/capevolve-paper-20261011`.

## 1. Validity: what the repository records already show (PR #673, issue #777)

- Optimization and selection used Verified itself: split 250 / 125 / 125 of the 500 (seed 0); best of 10 candidates chosen on val (0.976); the "sealed" test 125 (0.959, 117 of 122 scored) is also Verified. If 482/500 pools the subsets it includes 375 instances the optimization saw.
- Gold access: the optimizer notes say `/tmp/swebench_rows.json` held gold patch, test patch and FAIL_TO_PASS/PASS_TO_PASS for all 500 instances.
- Lookup: Harbor's SWE-bench task template gives the agent `network_mode = "public"`; the notes record agents fetching the upstream fix, and candidate `cand_0005/prompt.md` tells the agent to find the upstream commit and port it. The SWE-bench leaderboard checklist requires no use of F2P/P2P/hints and no web lookup of solutions.
- One trial per task, but best of 10 candidates; the final score was reassembled after finalize crashed (`recovered: true`); cost and tokens were not recorded; Harbor, Claude Code and grader versions were not recorded.
- The seed already scores 0.925 / 0.896 (train / val) in that setup; the highest entry in the checked leaderboard data file is 79.2 (December 2025). 482/500 is 98% of the 493 tasks that pass under Harbor's oracle (7 known oracle exceptions). Since 2025-11-18 Verified submissions also need an academic affiliation, an open method and an arXiv report.

### What must be established (evidence per item, details in design section 2.2)

1. Per-instance exposure ledger: which Verified instances' text, trajectories, verifier logs, gold or test patches the optimizer saw, and at which iteration.
2. Which split chose the winner, over how many candidates.
3. Attempts per instance in the final scoring; any retry after a failed result is best-of-k, not pass@1.
4. Harness versions and digests (Harbor, dataset snapshot, grader `swebench`, images, Claude Code, GLM serving revision) and a re-grade of the extracted patches with the official `swebench` harness.
5. Test-patch isolation, future-commit leakage in the images, hints/F2P in any candidate file, network blocked, optimizer sandbox.
6. Denominator (500, 497 or 493), errored instances and their scoring, leaderboard rules met.
7. An independent second scoring with different attempt seeds.

### What to rerun for a clean claim

Fresh optimization on non-Verified executable data only (below), network blocked, gold unreachable, 3 search seeds, champions fixed from the selection set before any Verified number is read, one scored pass over Verified for all arms together in one interleaved window.

## 2. Design (Suite F)

**Data.** Verified (500 instances, 12 repos) is scored once. Official splits, counted from the pinned parquet files: SWE-bench `train` 19,008 instances / 35 repos and `dev` 225 / 6 repos are both repo-disjoint and instance-disjoint from Verified; but `train` has empty `FAIL_TO_PASS`, `PASS_TO_PASS`, `test_patch` and `version` in all rows, so it gives no executable reward and is used for decontamination statistics only. Search and selection therefore use SWE-Gym (2,438 instances, 11 repos, none shared with Verified, pre-built images, Harbor adapter): OPT-100 (gate), SEL-60 (champion selection), REH-100 (rehearsal), PIL-40 (pilot). SWE-bench `dev` (225) is a transfer set (DEV-225; DEV-PIL-60 for the pilot). Decontamination: instance, repo and time-window checks plus a gold-patch hash check inside the evaluator; the pretraining contamination of GLM 5.3 cannot be removed, so claims are paired differences between artifacts. Split files and hashes (sha256): `gym_splits.json` `e4615cb6ea6940e265280dbacd27ec8a86fd6b6d312faa3a1e99a9e569312b7b`, `dev_splits.json` `ed9704c566aee64de7b2e39b3d5a7ee513ee2cd5c38d605f6299f3bb85c29a0a`, `id_hashes.json` `ce156f7824d89614de5e3f0e2d1b713ad310e9012b0707d8d05265031b03d29d`, `decontam_report.json` `fd611588fb563a5ef68366245bb5546175374095758277fbbae8c51547aa8ab9`. Verified id-list hash `fad0fdea4fc2315e9b78cdf80882a32e32393297052e502e0e63c79ad648fb85`.

**Harness and models.** Harbor (`github.com/harbor-framework/harbor`, v0.24.0, Apache-2.0; the `laude-institute/harbor` URL redirects), SWE-bench adapter. Track C: Claude Code agent with GLM 5.3 (gateway id `rits/zai-org/glm-5-3`, served build UNVERIFIED), temperature 1.0, top_p 0.95, `reasoning_effort` high (pilot decides); surfaces: prompt, skills, scaffold and tool code. Track M (reduced): mini-swe-agent 2.1.0. 200 turns, 3,600 s agent timeout, 1,800 s verifier timeout, 2 vCPU / 8 GB / 20 GB per container, 48 concurrent, agent network allowlist = model gateway only, optimizer in a no-egress sandbox with a feedback directory limited to OPT-100 trajectories and verifier logs.

**Arms (3 search seeds each).** Baseline S0 (no search); CapEvolve hill-climb with the stock gate (reference) and with rule P; agent-optimize; one-shot control; matched-optimizer control (hill-climb stock gate with Claude Sonnet 5.5 as optimizer, GLM 5.3 target); Tier 2: surface ablations (prompt only, skills only, tools only), one-stage gate, no-history; Tier 3 competitors: GEPA, ACE, SkillOpt, Meta-Harness, EvoSkill, Trace2Skill, HarnessLens (feasible with adapters), MIPROv2 (instruction addendum only), and as references only AHE, VERSE, DGM/HGM, Mixture of Branches, DarwinX (frameworks or budgets out of reach). Budget per search: 1,500 counted rollouts, 10 iterations, 4M optimizer tokens; matched checkpoint N\* as in analysis plan 5N.

**Trials.** Champions 2 attempts per Verified instance, baseline 4, one interleaved randomized window. Headline pass@1 = mean over attempts; leaderboard-style single attempt = attempt 0 only; pass@k estimator is diagnostic and not leaderboard-comparable; no best-of-k.

**Statistics.** Paired by instance, cluster = repo (12 clusters, CR1 t with 11 df), primary family of 6 contrasts with Holm (each gate arm and agent-optimize vs baseline, search vs one-shot, optimizer strength, stock gate vs rule P), TOST margin 0.05, inert-artifact rule, infrastructure rule 5O (three retries, then failure; sensitivity as missing). MDE at 500 instances (s2 = 0.05, tau = 0.15, rho = 0.02, 2 vs 4 attempts): 4.5 points uncorrected, 6.0 at Holm m = 6; pipeline level at 3 seeds about 10 to 12 points. Planning inputs are re-estimated in the pilot before freezing.

**Budget.** Unit: about 10 min per rollout (8.4 and 11.4 min measured in PR #673). Tier 1: 41,025 rollouts (18,600 search, 17,000 Verified, 3,825 dev, 1,600 rehearsal) = 142 h at 48 containers, about $41k at an assumed $1 per rollout (token price UNVERIFIED). Tier 2: 30,000 rollouts (104 h). Tier 3: 36,000 rollouts (125 h). Pilot: about 1,000 rollouts, no Verified contact (about 3.5 h). Reduced replication: 8,800 rollouts (31 h), three arms.

**Build checklist (acceptance tests in the design, section 12).** Split loader and Verified-id guard; Harbor SWE-Gym and dev task generation with oracle check; candidate injection and surface lock; network allowlist probe; future-commit probe on all images; phase-separation probe; optimizer sandbox with canary file; patch-hash decontamination; empirical null pool for the gates; cap-evolve Harbor adapter with infrastructure classification and retries; patch extraction and official re-grade; Suite F final-evaluation entry; competitor adapters; candidate static scan; cost ledger; analysis-script simulation.

**Deliverables and claims.** Validity report; frozen package with chained registry lines; pilot report; clean score table (artifact-level claim: "this artifact scores X on Verified, cross-repo, network blocked, D above baseline"); six-row contrast table; optimizer-strength decomposition; ablations; competitor comparison; dev and rehearsal replications; cost table; leaderboard readiness note. Not supported: an uncontaminated absolute score, "top across all leaderboards", other models or scaffolds beyond the reduced Track M check, or a method-level claim under about 10 points at 3 seeds.

## 3. UNVERIFIED (each has a settling test in the full document)

GLM 5.3 served build, price and training cutoff; Harbor dataset name and snapshot at v0.24.0; Claude Code version and Harbor agent kwargs for turns, system prompt and skills; allowlist enforcement in the docker and openshift environments; future commits in images; dev and SWE-Gym image availability; current top leaderboard entry; SWE-smith and SWE-rebench repo overlap; competitor repositories and licences; wall time per rollout at 2 vCPU and 48-way concurrency; `reasoning_effort` pass-through; and the 482/500 figure itself (no artifact in the repository).
