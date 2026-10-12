# CapEvolve on SWE-bench Verified with GLM 5.3 as agent and optimizer: experimental design (Suite F)

Status: DRAFT for team-lead review, written 2026-10-12. Nothing in this document has been posted to GitHub. The repository is public, so this text contains no endpoints, keys or internal host names. It becomes binding only when its SHA-256 and the hashes of the split files are written to `experiments/registry.jsonl` (section 10) before any search rollout starts.

Audience: a colleague's coding agent that must run every experiment from this document alone. Each section says what to do, what number to record, what passes and what stops the run. Where something does not exist yet, section 12 gives a build checklist with acceptance tests. Items marked **UNVERIFIED** could not be checked from here; they are collected in section 15 and each carries the test that settles it.

Method sources reused: `protocol/analysis_plan.md` (amendments 1 to 10: paired, task-clustered estimators, Holm families, TOST equivalence, inert-artifact rule 9D, infrastructure rule 5O, interleaved final window 5H, matched checkpoint N*), `redesign/EXPERIMENTS.md` (Suites D and E), `experiments/registry.jsonl` (hash chain). Suite names A to E are taken; this design is Suite F.

---

## 0. One-screen summary

1. **The reported 482/500 (96.4%) cannot be claimed yet.** The repository already holds the nearest record (open PR #673, audit issue #777). That record optimized and selected on SWE-bench Verified itself (250/125/125 split of the 500), used an agent with public network access, kept a file with the gold patch, test patch and FAIL_TO_PASS/PASS_TO_PASS lists for all 500 instances on the optimizer's disk, and wrote prompt rules telling the agent to find the upstream fix commit and port it. Section 2 lists what must be established and what to rerun.
2. **Clean design.** Optimize and select only on non-Verified executable data: SWE-Gym (2,438 instances, 11 repos, none shared with Verified) for search and champion selection, and the official SWE-bench `dev` split (225 instances, 6 repos, none shared) as a transfer set. The official SWE-bench `train` split (19,008 instances, 35 repos, also disjoint from Verified) has empty `FAIL_TO_PASS`, `PASS_TO_PASS`, `test_patch` and `version` fields, so it cannot supply an executable reward; it is used for decontamination statistics only. Verified's 500 instances are scored once, in one interleaved window.
3. **Arms.** Unoptimized baseline; CapEvolve hill-climb with the stock gate and with rule P; agent-optimize; one-shot control; surface ablations (prompt, skills, scaffold code); no-history ablation; a matched-optimizer control that swaps GLM 5.3 for Claude Sonnet 5.5 as optimizer while GLM 5.3 stays the agent; competitors GEPA, ACE, SkillOpt, Meta-Harness, EvoSkill, Trace2Skill, HarnessLens (feasible), MIPROv2 (policy addendum only), and SWE-specific optimizers (reference only unless noted).
4. **Statistics.** Paired by instance, clustered by repo (12 clusters, CR1 t with 11 df), Holm within the primary family (m = 6). With 500 instances, 2 attempts per champion and 4 for the baseline, the artifact-level minimum detectable effect is 4.5 points uncorrected and 6.0 points at Holm m = 6 (planning inputs, section 9). A claim about the optimizer rather than the three frozen artifacts needs the pipeline-level interval, whose MDE at 3 seeds is about 10 to 12 points.
5. **Cost.** Tier 1 (claim-bearing minimum) is about 41,000 rollouts: about 142 hours of wall clock at 48 concurrent containers, and about $41k if a rollout costs $1 (token price UNVERIFIED, formula in section 8). The pilot is about 1,000 rollouts (about 3.5 hours at 48 containers, about $1k). A reduced replication is about 8,800 rollouts (31 hours).

---

## 1. Facts used, with sources

| Item | Value | Source and check date |
|---|---|---|
| Harbor | `github.com/harbor-framework/harbor` (the old `laude-institute/harbor` URL returns "Moved Permanently"). Apache-2.0, "Framework for evaluating and improving agents", from the Terminal-Bench creators. Latest release v0.24.0 (2026-10-05). Install `uv tool install harbor`. | GitHub API and README, 2026-10-12 |
| Harbor SWE-bench adapter | `adapters/swebench` converts the 500 Verified instances to Harbor tasks (`task.toml`, `instruction.md`, per-task Dockerfile on the prebuilt SWE-bench image, `tests/test.sh` that grades with `swebench==4.0.3` log parsers and `/tests/config.json`). Run: `harbor run -d swebench-verified -a <agent> -m <model>`. Python 3.13+ for the adapter. | adapter README, 2026-10-12 |
| Harbor task defaults | `agent network_mode = "public"`, `verifier network_mode = "public"`, `cpus = 1`, `memory_mb = 4096`, `storage_mb = 10240`, `build_timeout_sec = 1800`, agent and verifier timeout both `max_timeout`. Harbor's network policy enum also has `no-network` and `allowlist` with `allowed_hosts`. | adapter `task.toml` template and `models/task/config.py`, 2026-10-12 |
| Harbor oracle exceptions | 7 Verified tasks fail or time out even with the gold patch: `astropy__astropy-8872`, `-7606`, `-8707`, `django__django-10097` (always); `scikit-learn__scikit-learn-14710` (times out on a 1-vCPU Daytona sandbox, passes locally in 6.5 min), `sphinx-doc__sphinx-8595`, `-9711` (upstream grader issue, SWE-bench PR #475). Harbor's own parity table uses 499 comparable tasks. | adapter README |
| SWE-bench | `github.com/SWE-bench/SWE-bench`, Jimenez et al., ICLR 2024 (arXiv 2310.06770). `princeton-nlp/SWE-bench` revision `e48e2bd1e9fecd5bbd641e9414ac59da9f2e69f6`: train 19,008, dev 225, test 2,294. | Hugging Face API, 2026-10-12 |
| SWE-bench Verified | `princeton-nlp/SWE-bench_Verified` revision `c104f840cc67f8b6eec6f759ebc8b2693d585d4a`, 500 instances, a human-validated subset of the 2,294-instance test split (OpenAI, 2024). 12 repos, created 2013-01-25 to 2023-08-07. | Hugging Face API; computed from the parquet |
| SWE-Gym | `SWE-Gym/SWE-Gym` revision `bb94ed9e39bbeb96a7fcbfb533b80f25a7fd59cb`, 2,438 instances, 11 repos, MIT, executable images `xingyaoww/sweb.eval.x86_64.*`. Harbor has an `swegym` adapter (full 2,438 and Lite 230). | Hugging Face API; Harbor adapter README |
| Other training sets | SWE-smith `SWE-bench/SWE-smith` 59,136 rows (MIT; Harbor `swesmith` adapter). SWE-rebench `nebius/SWE-rebench` 21,336 + 6,542 filtered rows (CC-BY-4.0). Repo overlap with Verified not computed (UNVERIFIED), so neither is used in the main arms. | Hugging Face size endpoint |
| Leaderboard rules | Pass@1 submission (one attempt per instance; best@k allowed only with a distinct selector that does not use the tests); does not use `PASS_TO_PASS`, `FAIL_TO_PASS` or `hints_text`; no web browsing, or steps taken to block lookup of solutions; reasoning traces required. Since 2025-11-18, Verified accepts only submissions from academic or research institutions with an open-source method and an arXiv or technical report. | `SWE-bench/experiments` README and `checklist.md`, 2026-10-12 |
| Leaderboard top | The `leaderboards.json` file on the SWE-bench site repo lists 180 Verified entries; the highest is 79.2 (two entries, December 2025). The file may lag the live board. | file fetched 2026-10-12; current top UNVERIFIED |
| GLM 5.3 | Hugging Face `zai-org/GLM-5.3`, architecture `GlmMoeDsaForCausalLM`, created 2026-08-25, last modified 2026-10-12 (revision `c5087a76d148760811ffbdedfe6ff9f194e46e38` at check time), license "glm-5.3". Model card: `reasoning_effort` in {low, high, max}, default max; agentic evaluations use temperature 1.0 and top_p 0.95 (or 1.0), mini-swe-agent DeepSWE at temperature 0.95. The card lists no SWE-bench Verified score in the lines checked. The colleagues' run used the gateway id `rits/zai-org/glm-5-3` (PR #673 `capevolve.yaml`); the served build behind that id (revision, quantization) is UNVERIFIED. | Hugging Face API and model card |
| Existing cap-evolve support | `capevolve_harbor/` (run, results, tasks), `templates/adapters/harbor` (registry dataset, claude-code agent, candidate injection), `templates/adapters/swe_bench` (single-shot litellm patching, not an agent), `ci/benchmarks/swebench/{smoke,pilot,full}` (250 Verified ids split 100/50/100 with a HarnessFix seed), `examples/swebench_glm` in PR #673 (not merged). | worktree and `gh pr view`, 2026-10-12 |

---

## 2. VALIDITY: what must be established before 482/500 can be claimed

Treat 482/500 (96.4%) as the colleagues' reported internal result. The repository records below are what exists; they come from PR #673 and issue #777 (filed by this campaign, open). The colleagues should confirm or correct each one.

### 2.1 What the existing records show

| Question | What the record shows | Consequence |
|---|---|---|
| Was any Verified instance used during optimization or selection? | Yes. `splits.json`: seed 0, train 250 / val 125 / test 125, all drawn from the 500 Verified instances. The optimizer trained on the train 250, the gate selected among 10 candidates on val 125 (best of 10, val 0.976), and the "sealed" test 125 is also a Verified subset. If 482/500 pools all three subsets, it includes 375 instances the optimization saw. | The 482 is a fit metric on at least 75% of its denominator. |
| Was test-split information reachable? | `INSIGHTS.md` (optimizer notes) states that `/tmp/swebench_rows.json` held all 500 instances with gold patch, test patch and FAIL_TO_PASS/PASS_TO_PASS, and that task-level facts were "verified against gold/test patches". The file covered the test split too. Whether the optimizer read test-split rows is not established. | Gold access during optimization. Test isolation unproven. |
| Did the agent have network access? | Harbor's SWE-bench task template sets agent `network_mode = "public"`. `INSIGHTS.md` documents agents fetching the upstream fix commit or PR (up to 165 `curl` calls on one task, "WebFetch the real commit, port it exactly"). Candidate `cand_0005/prompt.md` instructs the agent to find the upstream fix and port it. | Solution lookup. Not permitted by the leaderboard checklist unless blocked. |
| Attempts per instance? | One trial per task (`num_trials: 1`), best of 10 candidates chosen on val. The sealed test record has `recovered: true`: finalize died, the test record was assembled afterwards from rollouts and `baseline.json`. 3 of 125 test tasks errored (122 scored, 117 passed = 0.959; baseline 106/122 = 0.869). Costs and tokens were not recorded (`cost_usd` 0). | Pass@1 per candidate, but selection over 10 candidates, and a reconstructed rather than direct final score. |
| Harness version? | Harbor from the user's environment (version not recorded), dataset id `swe-bench/swe-bench-verified`, grader `swebench==4.0.3` inside Harbor's `test.sh`, claude-code agent with GLM through a gateway, unlimited turns, OpenShift environment. Claude Code version and Harbor dataset snapshot not recorded. | Cannot attribute the number to a harness version. |
| Hints and FAIL_TO_PASS in the prompt? | Harbor's `instruction.md` is the problem statement only. The `hints` field is not in it. Whether the candidate prompts or skills embed FAIL_TO_PASS lists is not checked; `INSIGHTS.md` shows the optimizer reasoning from F2P content. | Needs a scan of every candidate file. |
| Leaderboard comparability? | The baseline GLM 5.3 agent already scores 0.925 (train) and 0.896 (val) in this setup, well above the 79.2 top entry in the checked leaderboard file; combined with public network and gold access this points to lookup and contamination effects, not only optimization. 482/500 equals 98% of the 493 tasks that pass under Harbor's oracle. Leaderboard policy since 2025-11-18 also requires academic affiliation, an open method and an arXiv report. | "Top result across all leaderboards" cannot be stated. |

### 2.2 What to establish, as a checklist

Each item needs a file or a log line, not a statement.

1. **Instance usage ledger.** For every Verified instance: was its problem statement, trajectory, verifier log, gold patch or test patch visible to the optimizer at any iteration (read the optimizer transcripts and the events file)? Output: a table of 500 rows with the iteration of first exposure. Pass: only instances with zero exposure count as held out.
2. **Selection ledger.** Which split chose the winning candidate, over how many candidates, and was any number from the final scoring read before the choice?
3. **Attempts.** Number of attempts per instance in the final scoring (expected 1) and whether any instance was retried after a failure. Any retry triggered by a failed result is best-of-k, not pass@1.
4. **Harness.** Harbor version, dataset snapshot digest, `swebench` library version in the verifier, Docker image digests, Claude Code version, GLM serving revision. Cross-check the Harbor verdicts against the official `swebench.harness.run_evaluation` on the extracted patches (section 11.4); all disagreements listed.
5. **Test patch isolation.** Inside the agent container, during the agent phase, `/tests`, `/solution`, `test_patch` and any gold file must be absent; the verifier must apply the test patch only after the agent exits. Run the probe in section 6, item 1, on all 500 images.
6. **Future-commit leakage in the images.** `git log --all` and `git for-each-ref` in `/testbed` must show no commit later than `base_commit` (probe in section 6, item 2). **UNVERIFIED** for the current images.
7. **Hints and F2P.** Scan every prompt, skill and tool file of the champion for FAIL_TO_PASS, PASS_TO_PASS, `hints_text`, Verified instance ids, commit SHAs, and github.com pull or commit URLs.
8. **Network.** Show that the agent container could not reach github.com, PyPI or any host except the model gateway (probe in section 6, item 3), or report the run as "web access allowed" and do not compare to leaderboard rows. Probe: section 6, item 3.
9. **Denominator and errors.** 500 or 497 or 493? Which instances errored, which were retried, which were excluded, and how infrastructure errors were scored (rule 5O: three retries, then failure).
10. **Optimizer sandbox.** Prove the optimizer had no access to the dataset rows file, the Hugging Face cache, or the internet (section 6, item 5).
11. **Leaderboard rules.** pass@1 definition, no F2P/P2P/hints, no web lookup, reasoning traces, open method, arXiv report, affiliation. State which of these the submission meets.
12. **Reproduction.** A second, independent scoring of the same champion on Verified with different attempt seeds; report the instance-level agreement.

### 2.3 What to rerun so the claim is clean

1. Freeze a fresh seed artifact (section 5.1) and fresh splits (section 3). Nothing from the PR #673 optimization carries over, including its candidates and INSIGHTS.
2. Run the optimization on SWE-Gym pools only (OPT-100 for the gate, SEL-60 for champion selection), network blocked, gold unreachable.
3. Choose each champion before looking at any Verified number: highest SEL-60 score with ties broken by the lowest rollout count, recorded in the registry.
4. Score Verified once, for all arms together, in one interleaved randomized window (section 7.4). The first attempt of each instance is the leaderboard-style single attempt; later attempts are for variance only.
5. Three search seeds per arm, with the seeds listed in section 7.1; report all three, not the best.
6. Report the baseline, one-shot and matched-optimizer arms next to the headline arm. If the headline arm does not beat the baseline by more than the MDE of section 9, the wording is "no detectable difference at an MDE of X".

---

## 3. Data, official splits and decontamination

### 3.1 What the official splits are

| Source | n | Repos | Created range | Overlap with Verified | Usable as executable reward? |
|---|---|---|---|---|---|
| SWE-bench `test` | 2,294 | 12 | 2013 to 2023 | contains Verified (500) | not allowed for optimization (Verified is a subset) |
| **Verified** | 500 | 12 (django 231, sympy 75, sphinx 44, matplotlib 34, scikit-learn 32, astropy 22, xarray 22, pytest 19, pylint 10, requests 8, seaborn 2, flask 1) | 2013-01-25 to 2023-08-07 | n/a | final evaluation only, scored once |
| SWE-bench `train` | 19,008 | 35 (pandas 5,049, qiskit 1,406, transformers 1,058, meson 954, numpy 937, ... , JohnSnowLabs/spark-nlp 3) | 2010-12-29 to 2023-08-26 | 0 repos, 0 instances | **No.** `FAIL_TO_PASS`, `PASS_TO_PASS`, `test_patch` and `version` are empty in all 19,008 rows; no execution environments |
| SWE-bench `dev` | 225 | 6 (pvlib-python 63, pydicom 56, sqlfluff 50, astroid 31, pyvista 16, marshmallow 9) | 2019-01-20 to 2023-09-26 | 0 repos, 0 instances | Yes (validated instances); image availability UNVERIFIED |
| SWE-Gym | 2,438 | 11 (pandas 737, MONAI 374, moto 343, mypy 257, dvc 225, dask 145, modin 107, pydantic 83, conan 75, hydra 66, bokeh 26) | 2018-09-13 to 2024-05-28 | 0 repos, 0 instances | Yes (pre-built images, Harbor adapter) |

All counts above were computed from the pinned parquet files by `swebench_assets/swebench_splits.py` and are in `swebench_assets/splits/decontam_report.json`.

Reading: the official SWE-bench `train` and `dev` splits and SWE-Gym are all repo-disjoint from Verified, so the optimization is a cross-repo transfer test. That is the honest direction: it measures whether an artifact learned on other repositories transfers to the 12 Verified repositories. It will probably show smaller gains than an in-repo fit. The in-repo alternative (SWE-rebench instances from Verified's 12 repos created after 2023-08-07) is the optional extension X1 in section 6.6.

### 3.2 Decontamination check (run before registration; stop on any failure)

Run `python3 -I swebench_assets/swebench_splits.py --cache <dir> --out <dir>`; it downloads each parquet at a pinned revision, verifies its sha256, and aborts on a mismatch. Checks, all in `decontam_report.json`:

1. **Instance level:** the intersection of every optimization or selection pool with the 500 Verified ids is empty (assertion in the script). Result: 0 for train, dev and SWE-Gym.
2. **Repo level:** repos of every pool versus the 12 Verified repos. Result: empty intersection for all three sources. Any future pool with a non-empty intersection must also pass check 3 and 4.
3. **Time window:** `created_at` of each pool instance versus the latest Verified `created_at` (2023-08-07T19:30:22Z). Counts later than that date: train 66, dev 10, SWE-Gym 603. For repo-disjoint pools this is informational. For any pool that shares a repo with Verified (extension X1), require `created_at` strictly later than 2023-08-07 plus 30 days, and also later than the GLM 5.3 training cutoff if the vendor publishes one (UNVERIFIED; the model card was not found to state it).
4. **Near-duplicate patches (build item B8):** hash the normalized gold patch of every pool instance and compare with the normalized gold patches of Verified (the check runs inside the evaluator, so nothing from Verified enters the search environment). Pass: zero identical patches.
5. **Limits stated up front:** GLM 5.3's pretraining data may contain Verified instances, upstream commits and mirrors. This design cannot remove that. Claims are therefore paired differences between artifacts of the same model, and the absolute Verified score is reported with that caveat.

### 3.3 Frozen splits

Generated by `swebench_splits.py` (seed 20261012; largest-remainder allocation by repo; repo queues shuffled once and sliced; all runs reproduced the same hashes). Files are in `swebench_assets/splits/`.

| Pool | Source | n | Role | Who may read it |
|---|---|---|---|---|
| OPT-100 | SWE-Gym, repo-stratified | 100 | gate and screen (search signal); all optimizer feedback comes from here | optimizer sandbox (trajectories and verifier logs only, never gold) |
| SEL-60 | SWE-Gym | 60 | champion selection at finalize; GEPA and other competitors' selection set | evaluator only; scored once per candidate at finalize |
| REH-100 | SWE-Gym | 100 | rehearsal hold-out: one scoring of every champion before Verified, to test the final machinery and give an in-pool generalization number | evaluator only |
| PIL-40 | SWE-Gym | 40 | pilot: noise, timing, token and infra measurements; baseline calibration | pilot only, never reused as OPT |
| DEV-225 | SWE-bench dev | 225 | transfer set scored in the final window; second-repo-family generalization | evaluator only |
| DEV-PIL-60 | subset of DEV-225 | 60 | stand-in for "the final set" in the pilot, so that the pilot never touches Verified | pilot only |
| VER-500 | Verified | 500 | final, once | evaluator only |

File hashes to record (sha256), as produced on 2026-10-12:

| File | sha256 |
|---|---|
| `splits/id_hashes.json` | `ce156f7824d89614de5e3f0e2d1b713ad310e9012b0707d8d05265031b03d29d` |
| `splits/decontam_report.json` | `fd611588fb563a5ef68366245bb5546175374095758277fbbae8c51547aa8ab9` |
| `splits/gym_splits.json` | `e4615cb6ea6940e265280dbacd27ec8a86fd6b6d312faa3a1e99a9e569312b7b` |
| `splits/dev_splits.json` | `ed9704c566aee64de7b2e39b3d5a7ee513ee2cd5c38d605f6299f3bb85c29a0a` |

Source id-list hashes (sha256 of the sorted instance ids joined by newlines): Verified `fad0fdea4fc2315e9b78cdf80882a32e32393297052e502e0e63c79ad648fb85`; dev `6524b8e78c347c257640857b17fa742c95aec2f41a2cb8dd2ce8fb7aae0c11f4`; train `240ec200ae4f55151c26478d29ec7d6ddbfa619de7066f7ee20fa392fe150e13`; SWE-Gym `1b7c178da5d88b9bf484254a782948209fa4d5d8e8bae8e26c0241031c1ece56`. Parquet sha256 values are in `id_hashes.json` and in the script. The exact instance ids of OPT-100, SEL-60, REH-100 and PIL-40 are in `gym_splits.json` (keys `pools`); DEV-PIL-60 is in `dev_splits.json`.

Replacement rule (outcome-blind): before the pilot, run Harbor's oracle agent (gold patch) on OPT-100, SEL-60, REH-100 and DEV-225. An instance that fails the oracle is replaced by the next unused id of the same repo in `reserve_queue_per_repo`, and the replacement is logged. Oracle results are never agent outcomes.

### 3.4 What each party may see

- **Optimizer:** the current candidate files, per-task rewards on OPT-100, agent trajectories, extracted patches and verifier stdout of OPT-100 only. Not visible: gold patches, `test_patch`, FAIL_TO_PASS and PASS_TO_PASS files (verifier logs on OPT-100 may name failing tests; that is the training signal), any SEL-60, REH-100, DEV or Verified content, the internet, and the dataset caches.
- **Agent at rollout time:** the problem statement, the repository at `base_commit`, its own tools. No hints field, no test lists, no network except the model gateway.
- **Evaluator:** everything, in a separate process the optimizer cannot read.

---

## 4. Models and providers

| Role | Model | Id used | Notes |
|---|---|---|---|
| Target agent, main arms | GLM 5.3 | gateway id `rits/zai-org/glm-5-3`; weights `zai-org/GLM-5.3` | served build UNVERIFIED; record the gateway's reported model string and a response-header or `/models` listing at pilot time. Sampling: temperature 1.0, top_p 0.95 (model card); `reasoning_effort = high` pinned (pilot decides high vs max, section 8.3). |
| Optimizer, main arms | GLM 5.3 | same id, run through the claude-code optimizer shim with `behavesAs` settings (as in PR #673) | optimizer-token cap 4M non-cache-read per search |
| Matched-optimizer control | Claude Sonnet 5.5 | `aws/claude-sonnet-5-5` | same shim, same prompts, same caps; target stays GLM 5.3 |
| Provider order | RITS first, then ETE-INT, then ETE | repo `CLAUDE.md` | a prefixed id only when an arm must stay on one gateway; say why in the registry |

Record in the registry, per arm: provider, exact id string, the gateway's model listing at start, temperature, top_p, reasoning effort, max output tokens, and the date. If the gateway changes the served build mid-campaign, the affected window is flagged and not mixed (hourly 5-task canary on the baseline, as in amendment 5K).

---

## 5. Agent scaffold, surfaces and environment

### 5.1 Scaffold

**Track C (primary): Claude Code via Harbor.** Harbor agent `claude-code`, model GLM 5.3 through an Anthropic-compatible gateway, matching the colleagues' setup so the result is comparable to theirs. Surfaces that Claude Code exposes natively map onto the three surfaces asked for:

| Surface id | What is editable | Where it lives in the candidate directory |
|---|---|---|
| P (system prompt) | appended system prompt or `CLAUDE.md` text | `prompt.md` |
| S (skills) | `.claude/skills/<name>/SKILL.md` plus reference files | `skills/` |
| T (scaffold and tools code) | helper executables on PATH (localization, test-running, patch-summarizing scripts), hook scripts, an optional MCP server | `tools/` |

How the candidate is injected into the container (Harbor mount, `HOME/.claude`, `--append-system-prompt` or `CLAUDE.md`) follows `templates/adapters/harbor/adapter.py` and must be re-checked against Harbor v0.24.0 (UNVERIFIED; build item B3). Surface lock: a locked surface is restored to the seed before every evaluation, and candidates that differ on a locked surface are counted as `surface_violations`, as in Suite D.

**Seed artifact S0 (the unoptimized baseline).** Claude Code defaults plus the minimal two-file seed that already exists in PR #673 (`prompt.md`, 174 bytes; `SKILL.md`, 835 bytes, a generic "fix a bug from an issue and produce a minimal diff" skill), with one added neutral sentence: "Do not use the internet." Nothing else. Its content hash is the INERT reference (analysis plan 9D). A second reference, S0-open (same seed, network public), is scored on PIL-40 and DEV-PIL-60 only to quantify how much of the baseline depends on web lookup. It is descriptive and never in a test.

**Track M (robustness replication, reduced): mini-swe-agent bash-only**, version pinned to the one used in Harbor's parity record (`mini-swe-agent==2.1.0`), GLM 5.3 through LiteLLM. Editable surfaces: system and instance prompt templates (P) and a patched agent config or environment wrapper (T). Skills are not native there, so S is not run. Track M runs only the reduced configuration of section 8.5, to show that the finding is not specific to Claude Code.

### 5.2 Limits and resources

| Setting | Value | Reason |
|---|---|---|
| Max turns | 200 | colleagues ran unlimited; a cap bounds runaway rollouts. Count of rollouts that hit the cap is reported. How `claude-code` receives the cap through Harbor `--ak` is UNVERIFIED. |
| Agent timeout | 3,600 s | measured mean rollout was 8.4 to 11.4 min (section 8.1); the cap leaves headroom |
| Verifier timeout | 1,800 s | `scikit-learn__scikit-learn-14710` needs about 6.5 min locally and failed on a 1-vCPU sandbox |
| Build timeout | 1,800 s | Harbor default |
| Container resources | 2 vCPU, 8 GB RAM, 20 GB disk per agent container | Harbor default of 1 vCPU and 4 GB caused a verifier timeout in Harbor's own oracle sweep; 2 vCPU costs half the concurrency per host. Re-check on PIL-40. |
| Concurrency | 48 containers (96 vCPU, 384 GB RAM) for the full design; 16 for the pilot | PR #673 ran 16 workers |
| Disk for images | at least 400 GB free for the Verified, SWE-Gym sample and dev images, plus Docker layer cache (the exact image sizes are UNVERIFIED) | |
| Docker images | Verified: the prebuilt SWE-bench images named by the Harbor adapter; SWE-Gym: `xingyaoww/sweb.eval.x86_64.*`; dev: SWE-bench dev images (availability UNVERIFIED, build via `swebench` if absent) | pull and pin by digest before the pilot; record digests |
| Network, agent phase | `allowlist` with the model gateway host only | no GitHub, no PyPI (`pip download <pkg>==<later version>` would retrieve the upstream fix) |
| Network, verifier phase | Harbor default (public), after the agent process has exited | Harbor's `test.sh` resolves `swebench==4.0.3`, `datasets` and `fastcore` with `uv` at grading time, so a no-network verifier fails; to close this channel bake the grader dependencies into derived images (build item B5) and then use `no-network` |
| Sampling | temperature 1.0, top_p 0.95 | model card; attempts are therefore stochastic, so attempt seeds are recorded but do not make the run reproducible |

### 5.3 What the harness owns and the optimizer cannot edit

The Harbor `tests/` directory and verifier, the patch-extraction step (a harness-owned post-step that writes `git diff` of `/testbed` to `/logs/agent/model_patch.diff`), the network policy, the turn and time caps, the surface lock, the gate and the promotion rule, the scorer adapter and the infrastructure classifier.

---

## 6. Gold and test isolation: probes that must pass

All probes run in the pilot and again on a random 10% of containers during the main runs. A failing probe stops the campaign.

1. **Phase separation.** In the agent container, during the agent phase: `test -e /tests`, `test -e /solution`, `find / -name '*.patch' -newer /etc/hostname` limited to non-repo paths, and a search for `test_patch` strings. Expected: none.
2. **Git history.** In `/testbed`: `git for-each-ref`, `git rev-list --all --since="<base_commit committer date> + 1 day" --count` must print 0, and `git log --all -S"<first line of gold patch>" --oneline` must print nothing (the gold patch text is supplied by the evaluator for this probe, never to the agent). Run on all 500 Verified images and on all pool images. **UNVERIFIED** whether the current images pass; if any fail, strip future objects in a derived image and record the new digest (build item B5).
3. **Network.** From the agent container: `curl -sS -m 5 https://github.com` and `https://pypi.org` must fail; a request to the gateway host must succeed. Log the count of denied connections per rollout (non-zero counts show attempted lookups).
4. **Candidate scan (static).** Reject any candidate file containing: a Verified instance id pattern from the 500 ids, a 40-hex SHA, `github.com/*/(pull|commit)/`, the strings `FAIL_TO_PASS`, `PASS_TO_PASS`, `hints_text`. A rejected candidate counts as a surface violation and the iteration is lost.
5. **Optimizer sandbox.** Run the optimizer in a network namespace with no egress except the gateway, read-only mounts for the candidate directory and a staged feedback directory, a masked `/tmp`, and no mount of the dataset caches, `~/.cache/huggingface`, the splits file or `swebench_rows.json`-style dumps. The campaign's `_sbx_bin` shim (Suite D) is the template. A transcript scan (as in 8G of the analysis plan) counts tool calls that name a path outside the sandbox or a Verified id.
6. **Extension X1 only:** the time-window rule of 3.2 item 3 and a Verified-instance-id scan of every training instance text.

### 6.6 Optional extension X1 (in-repo pool)

If the cross-repo design shows no transfer, X1 asks whether in-repo data helps: build OPT and SEL from SWE-rebench instances in Verified's 12 repos with `created_at` later than 2023-09-06, drop any instance whose normalized gold patch matches a Verified patch, and rerun the Tier 1 headline arm with S=3. Requires SWE-rebench environments (availability UNVERIFIED). Its results are labelled in-repo and never pooled with Suite F.

---

## 7. Arms, seeds, trials and the matched checkpoint

### 7.1 Seeds

- **Search seeds:** 0, 1, 2 for every searched arm (optimizer randomness and proposal order; splits fixed). Three seeds give 2 degrees of freedom at pipeline level (analysis plan section 2).
- **Attempt seeds:** every final rollout gets `seed = sha256(artifact_id | task_id | attempt)` truncated to 31 bits. The gateway may ignore the seed at temperature 1.0; it is recorded, and the order file is hashed before the first final rollout.
- **Baseline:** one shared measurement of S0 serves every contrast (plan section 1). It is scored inside the final window (n = 4 attempts) and on every other set that a champion is scored on.

### 7.2 Arms

Cell ids use prefix F. Optimizer is GLM 5.3 unless stated. Surface "PST" means prompt, skills and tools all editable.

| Cell | Algorithm and gate | Surface | Seeds | Tier |
|---|---|---|---|---|
| F00-seed | no search; S0 | none | n/a | 1 |
| F10-hc | hill-climb, stock gate (paired, k_se 1.0, footprint masking on, candidate-side coverage 0.6, errored trial policy fail) | PST | 3 | 1, reference |
| F11-hcP | hill-climb, rule P (k_se 1, n_conf 3, z_conf 1.282, dmin 0) | PST | 3 | 1 |
| F12-ao | agent-optimize, rule P | PST | 3 | 1 (gold-isolation flag, section 6, item 5, applies) |
| F13-ctl | one-shot control: baseline evaluation on OPT-100, one proposal, one evaluation, no selection (200 rollouts) | PST | 3 | 1 |
| F14-mo | hill-climb stock gate, **optimizer Claude Sonnet 5.5**, target GLM 5.3 | PST | 3 | 1, matched-optimizer control |
| F20-P, F20-S, F20-T | F10-hc with `SURFACES` locked to prompt, skills, or tools | P, S, T | 3 each | 2 |
| F21-1S | one-stage gate (footprint masking off, joint coverage, no confirmation) | PST | 3 | 2 |
| F22-nohist | F10-hc with `CAPEVOLVE_HISTORY=0` and the hidden-history sandbox of amendment 8H (no LEDGER, JOURNAL, RUNMAP, prior iterations; per-invocation config; PROCESS.md reset) | PST | 3 | 2 |
| F30 to F37 | competitors (section 7.5) | see table | 3 each, HarnessLens 1 | 3 |

Why these: F10 versus F11 is the gate question (stock gate shipped, rule P nearly inert in Suites A to C). F10 versus F13 asks whether search beats a single proposal. F10 versus F14 separates optimizer strength from target strength: if Sonnet-optimized and GLM-optimized artifacts differ, the "self-optimizer" gain depends on the optimizer; if they match, it does not. F20 versus F10 shows which surface carries the effect (analysis follows Suite D 7D). F22 versus F10 tests the value of the causal history.

### 7.3 Budget rule and matched checkpoint

- Search budget per cell: at most 1,500 counted rollouts and 10 iterations, optimizer-token guard 4M non-cache-read (soft 3.5M). Counted rollouts are those of amendment 9 erratum 4: baseline evaluations, screens, confirmations and native selection evaluations; finalize and SEL-60 rescoring are excluded.
- OPT-100 at n = 1 per task: a screen costs 100 rollouts, a rule-P confirmation 2 x 100 x 3 = 600. A stock-gate search reaches about 14 screens; a rule-P search about 8 screens plus 1 to 2 confirmations.
- **N\*:** the largest counted-rollout count reached by every seed of every primary-family arm (F10, F11, F12, F14), rounded down to a multiple of 50, floor 600. Every primary comparison uses each arm's artifact at min(N\*, its own count at the end), with the count disclosed per seed (analysis plan 5N).
- Native end-of-run artifacts (unmatched budget) are a secondary analysis (5D).
- A search that crashes stays in the denominator; its champion is the seed unless a candidate was already accepted.

### 7.4 Final evaluation: trials and pass@k

Definitions (fixed here, used in every table):

- A rollout is one independent agent attempt on one instance, graded by the Harbor verifier. r(t, a, i) is 1 if attempt i of artifact a on instance t resolves it, else 0. An attempt that ends in `infra_final` counts as 0 in the primary analysis (rule 5O-1) and as missing in the sensitivity analysis.
- **Headline metric (pass@1, mean of attempts):** P1(a) = (1/T) sum over t of (1/n_a) sum over i of r(t, a, i), with T = 500.
- **Leaderboard-style single attempt:** P1-first(a) uses attempt index 0 only, so each instance is attempted once. This is the only number to quote next to leaderboard rows, and it needs section 2.2 items 1 to 12 satisfied.
- **Pass@k estimator (diagnostic):** for k up to n_a, 1 - C(n_a - c, k) / C(n_a, k), c the number of successes. It is **not** leaderboard-comparable (leaderboard rules forbid pass@k) and is labelled so. No best-of-k selection with a verifier is used in any arm.
- **All-attempts-succeed (pass^n):** reported as a robustness view.
- Attempts per instance: champions n = 2, baseline S0 n = 4 (attempts 0 and 1 are paired with each champion; 2 and 3 sharpen the baseline), scored in one window. DEV-225: champions n = 1, baseline n = 2. REH-100: n = 1 for all.
- **Denominators:** all 500 (primary); the 493 that pass under Harbor's oracle (sensitivity, listed in the registry before scoring); leave-one-repo-out (section 9.4).
- **Interleaving (5H):** every rollout of the final window, all arms and seeds and the baseline, in one randomized order (seeded, order file hashed beforehand) in one window. Time-block sensitivity per 5I. Hourly canary of 5 baseline tasks to detect provider-side change.

### 7.5 Competitors: feasibility on SWE-bench

All competitors get the same target (GLM 5.3), the same OPT-100 / SEL-60 split and the same counted-rollout budget (1,500), count their own optimizer-side generation, and are scored in the same final window. A competitor that does not finish leaves the family and the reason is logged (analysis plan 5A).

| Method (arXiv) | What it edits | Feasible here? | What it needs | Plan |
|---|---|---|---|---|
| GEPA (2507.19457) | prompt text | Yes | official `gepa` package, a `GEPAAdapter` whose evaluate call runs a Harbor batch on a minibatch and returns reward and trajectory text; reflection model GLM 5.3; selection on SEL-60 | F30, 3 seeds, prompt only. Suite E used GEPA 0.1.4. |
| MIPROv2 (2406.11695) | instructions and few-shot demos | Partly | a DSPy program wrapper around one agent call. Few-shot demos would be full agent trajectories of tens of thousands of tokens, so only the instruction (a policy addendum) is optimized, as in Suite E | F31 optional, descriptive only |
| ACE (2510.04618) | evolving playbook | Yes | generator = the agent, reflector and curator = GLM 5.3, playbook appended to the prompt; offline mode on OPT-100 | F32, 3 seeds |
| SkillOpt (2605.23904) | skill text | Yes | official code adapted to Claude Code skill blocks and Harbor batches; selection split SEL-60 | F33, 3 seeds |
| Meta-Harness (2603.28052) | harness code with a filesystem of all prior candidates | Yes, heavy | proposer agent with read access to prior candidates, code edits in `tools/`; the same hidden-gold rules | F34, 3 seeds |
| EvoSkill (2603.02766) | skill folders, Pareto frontier | Yes, adapter needed | designed for small QA validation sets; frontier of k = 3 programs as git branches; use the actual code | F35, 3 seeds |
| Trace2Skill (2603.25158) | skills distilled from trajectories | Yes, cheap | trajectory collection counted in the budget (reuse baseline OPT-100 trajectories; count them once); hierarchical merge of patches | F36, 3 seeds |
| HarnessLens (2608.27311) | harness, behavior-aware task subset per candidate | Yes | MIT code; the Suite B and E adapter with the sandbox fix | F37, 1 seed, exploratory |
| AHE, Agentic Harness Engineering (2604.25850) | prompts, tools, middleware, memory | No in this campaign | NexAU framework and E2B sandboxes; its own SWE-bench Verified numbers are frozen-harness transfer from a Terminal-Bench 2 discovery run (75.6 vs seed 75.2) | cite only |
| VERSE (2610.02616) | executor harness and optimizer assets | No | evaluated on SWE-rebench with local Qwen models under vLLM; its host optimizers are re-implementations | cite as design reference for time-based splits |
| DGM, HGM (2505.22954, 2510.21614) | agent source code by self-modification | No | native budgets of about $22k per run exceed the matched budget | cite only |
| Mixture of Branches (2609.37834), DarwinX (2608.07545) | branch harnesses and router, archive of harness snapshots | No | different deployment (router) or heavy archive search | cite only |

Code availability and licences were read only from the campaign's cards for VERSE (MIT), AHE (MIT) and HarnessLens (MIT); for the rest, confirm the official repository, licence and commit before building (UNVERIFIED).

---

## 8. Budget, wall clock and cost, with arithmetic

### 8.1 Unit costs

- **Wall per rollout w = 10 min** (planning value). Measured in the colleagues' baseline records: 7,918.6 s for 250 tasks at 16 workers is 7,918.6 x 16 / 250 = 506.8 s = 8.4 min; 5,362.0 s for 125 tasks is 5,362.0 x 16 / 125 = 686.3 s = 11.4 min. Our 2-vCPU containers and the extra patch-extraction step should land in that range; the pilot re-measures.
- **Tokens and dollars per rollout are not recorded** in those files (`cost_usd` 0). Use a symbolic cost c per rollout and report cost = (rollouts) x c. Illustration only (assumed, UNVERIFIED): 3.0M input tokens of which 90% cached, 40k output tokens, and an assumed list price of $1.00 per M uncached input, $0.20 per M cached input and $3.50 per M output give 0.3 x 1.00 + 2.7 x 0.20 + 0.04 x 3.50 = $0.98, so c is about $1. Tables use c = $1 with the range $0.3 to $3 in the last column. The pilot replaces c with the measured gateway-ledger value; GLM on RITS has no per-token charge, so for those runs the binding cost is GPU time and wall clock.
- **Wall** = rollouts x w / C, with C = 48 concurrent containers.

### 8.2 Tier totals (rollouts)

Tier 1 (claim-bearing minimum):

| Item | Arithmetic | Rollouts |
|---|---|---|
| Searches F10, F11, F12, F14 | 4 cells x 3 seeds x 1,500 | 18,000 |
| F13 one-shot | 3 seeds x 200 | 600 |
| Verified, champions | 15 artifacts (F10, F11, F12, F14, F13 x 3 seeds) x 500 x n = 2 | 15,000 |
| Verified, baseline | 500 x n = 4 | 2,000 |
| DEV-225 | 15 x 225 x 1 + 225 x 2 | 3,825 |
| REH-100 | 16 artifacts x 100 x 1 | 1,600 |
| **Tier 1 total** | | **41,025** |

Wall at C = 48: 41,025 x 10 / 48 = 8,547 min = 142 h = 5.9 days. Cost at c = $1: $41k (range $12k to $123k for c = $0.3 to $3).
Optimizer tokens: 12 GLM searches with a 4M cap = 48M GLM tokens for F10, F11, F12; plus the 3 Sonnet 5.5 searches at a 4M cap = 12M non-cache-read tokens, to be priced from the provider table in `protocol/pricing.json` (the Claude side is in the campaign's budget lines).

Tier 2 (surface, one-stage and history ablations): 5 cells x 3 seeds x 1,500 = 22,500 search rollouts + 15 artifacts x 500 x 1 = 7,500 final = **30,000** rollouts, 104 h, $30k.

Tier 3 (competitors): 6 competitors x 3 seeds x 1,500 = 27,000 search + 18 artifacts x 500 x 1 = 9,000 final = **36,000** rollouts, 125 h, $36k (HarnessLens at 1 seed adds 1,500 + 500).

Whole program: 107,025 rollouts, 372 h (15.5 days), $107k at c = $1. Tiers 2 and 3 start only after Tier 1 searches are registered and capacity is approved; their search cells are registered before the Tier 1 final window opens, so no cell is chosen by a score.

### 8.3 Pilot configuration (about 1,000 rollouts, no Verified contact)

Purpose: measure what the planning inputs assume, and test every probe, before registration.

| Step | Content | Rollouts |
|---|---|---|
| P0 | Oracle agent on OPT-100, SEL-60, REH-100, PIL-40, DEV-225 (no LLM), plus the Verified oracle sweep for the 493-instance list | no agent rollouts |
| P1 | Baseline S0 on PIL-40, 3 trials, `reasoning_effort` high and max (the pre-registered choice rule: use high unless max improves the pass rate by more than 5 points) | 240 |
| P2 | Network probe: S0 and S0-open on DEV-PIL-60, 1 trial each | 120 |
| P3 | One mini search: F10-hc, seed 0, OPT-40 taken as the first 40 ids of OPT-100 (sorted), 400 counted rollouts, GLM optimizer | 400 |
| P4 | Mini final: S0 (n = 2) and the P3 champion (n = 2) on DEV-PIL-60 | 240 |
| Total | | about 1,000 |

At C = 16: 1,000 x 10 / 16 = 625 min = 10.4 h; at C = 48 about 3.5 h. Cost about $1k at c = $1.

Outputs that feed the freeze: within-task Bernoulli variance s2 (planning 0.05), the discordant-pair rate of two attempts of the same artifact (planning 0.10), the mean wall per rollout, tokens and dollars per rollout, the infrastructure error rate and exception-type list (for the classifier), the turn-cap hit rate, the baseline pass rate on PIL-40 (decision rule: if it is below 0.15 or above 0.90, stop and revisit the pools before registering), and the probe results of section 6. Pilot results may change planning constants (C, caps, s2) but never an arm, split, rule or claim.

### 8.4 Reduced replication (about 8,800 rollouts)

Arms F00, F10 (GLM optimizer) and F14 (Sonnet optimizer), S = 3, search budget 800 counted rollouts, final on Verified with n = 1 per champion and n = 2 for the baseline, no REH or DEV scoring.
Search: 2 cells x 3 seeds x 800 = 4,800. Final: 6 artifacts x 500 + 500 x 2 = 4,000. Total 8,800 rollouts; 8,800 x 10 / 48 = 1,833 min = 30.6 h; $8.8k at c = $1. The MDE rises to about 6 to 8 points; the reduced run supports only the F10-versus-seed and F10-versus-F14 contrasts and is labelled reduced.

### 8.5 Track M (mini-swe-agent) reduced run

F00-M and F10-M (prompt and scaffold surfaces), S = 3, 800 rollouts per search, final n = 1 on Verified: 2,400 + 4 x 500 = 4,400 rollouts, about 15 h at C = 48.

---

## 9. Statistics

Everything follows `protocol/analysis_plan.md`; this section fixes the SWE-specific values.

### 9.1 Estimands and estimators

- **E1** fixed-task-set score on VER-500 (execution randomness only). **E2** generalization to new repos and tasks, with repo as cluster (headline). **E3** optimizer variance across the 3 search seeds. **E4** cost.
- Unit: the instance; trials averaged within an instance; every instance has weight 1. Cluster: repo (12 clusters; django has 231 instances, 46% of the set).
- Paired difference per instance: d(t) = mean over attempts of champion minus the baseline mean over its attempts, broadcast over seeds (section 3 of the plan). Artifact-level test: CR1 cluster-robust t with 11 degrees of freedom (fewer than 30 clusters, so no percentile bootstrap as headline), and the pipeline-level interval t(S - 1) with SE^2 = SE_task^2 + s_seed^2 / S (5M-2). A claim about the method or optimizer, rather than the frozen artifacts, needs the pipeline-level interval.
- Sign-flip randomization p-value as a pre-declared robustness check; if the two disagree both are reported.
- Inert artifacts (content tree hash equal to S0): per-task delta = 0 by construction and an extra seed-check cell (9D). Own-seed identity column (erratum 8) is descriptive.

### 9.2 Primary family F (Holm m = 6, Verified, matched checkpoint)

1. F10-hc vs F00-seed. 2. F11-hcP vs F00-seed. 3. F12-ao vs F00-seed. 4. F10-hc vs F13-ctl (search vs one-shot). 5. F10-hc vs F14-mo (optimizer strength; two-sided). 6. F10-hc vs F11-hcP (gate).
Secondary families, each with its own Holm: S-ab (Tier 2: F20-P, F20-S, F20-T vs F10; F21-1S vs F10; F22-nohist vs F10; each vs seed); S-comp (F10 vs each competitor that finishes); S-dev (the F-family contrasts re-run on DEV-225, a second-repo-family replication, no pooling with Verified); S-reh (REH-100, descriptive). Equivalence (TOST) on non-significant primary rows with margin **0.05** absolute (about the conditional MDE below), design power reported, never at pipeline level; non-passing rows read "inconclusive". Winner's-curse shrinkage per arm (5P-2): SEL-60 gain minus Verified gain, non-inert seeds only.

### 9.3 Minimum detectable effect at T = 500

Model (analysis plan section 7): Var(delta-hat) = DEFF x (tau^2 + s2/n_a + s2/n_b) / T, alpha .05 two-sided, power .80, critical value = t(alpha/2, df) + 0.842. Planning inputs, to be re-estimated from the pilot before freezing: s2 = 0.05 (within-instance Bernoulli variance; the discordant rate of two attempts of one artifact is 2 x s2 = 0.10), tau = 0.15 (SD across instances of the true advantage), cluster size 42 (500 / 12), ICC rho.

Worked example, n = 2 vs 4, rho = 0.02: DEFF = 1 + 41 x 0.02 = 1.82; variance per instance = 0.0225 + 0.05/2 + 0.05/4 = 0.06; SE = sqrt(0.06 x 1.82 / 500) = 0.0148; MDE = (2.201 + 0.842) x 0.0148 = 0.045.

| Attempts (champion / baseline) | rho | SE | MDE uncorrected (t, 11 df) | MDE at Holm m = 6 |
|---|---|---|---|---|
| 1 / 1 | 0 (iid, 499 df) | 0.0157 | 0.044 | 0.055 |
| 1 / 1 | 0.02 | 0.0211 | 0.064 | 0.086 |
| 1 / 1 | 0.05 | 0.0273 | 0.083 | 0.111 |
| 2 / 4 | 0 | 0.0110 | 0.031 | 0.038 |
| **2 / 4** | **0.02** | **0.0148** | **0.045** | **0.060** |
| 2 / 4 | 0.05 | 0.0191 | 0.058 | 0.077 |

Sensitivity to s2 at 2 / 4, rho 0.02: s2 0.03 gives 0.039, 0.05 gives 0.045, 0.08 gives 0.053. Pipeline level, 2 / 4, rho 0.02, S = 3, t(2) = 4.303: seed SD 0.02 gives SE 0.0188 and MDE 0.096; seed SD 0.03 gives 0.117. At S = 5 (t(4) = 2.776), seed SD 0.02: 0.062. DEV-225 (6 repos, 5 df, n = 1 vs 2): MDE 0.093, so DEV is a descriptive replication.
Search time: with OPT-100 at n = 1 the null SE of a paired split delta is sqrt(0.10 / 100) = 0.032. Under a normal null the stock gate (k_se 1) accepts a null edit with probability 0.159 per candidate, or 0.82 over 10 candidates; rule P (screen then 3 fresh trials at z 1.282) is about 0.016 per candidate and 0.15 over 10. A true +0.06 edit passes the stock screen with probability 0.82. These approximate the real operating characteristics, which come from the empirical null pool (item B9).

Reading: with 500 instances the design can resolve about 4.5 to 6 points between frozen artifacts, so it can detect a gain of the size at stake (the colleagues' own test baseline was 0.869 and their final 0.959, a 9-point difference) but only if the gain is real and transfers; it cannot resolve 2 to 3 point differences between arms, and a method-level claim at 3 seeds needs roughly 10 to 12 points. A baseline that is already near the ceiling (0.87 or above) narrows the room: the largest possible gain is 13 points before the oracle-fail tasks.

### 9.4 Sensitivity analyses (pre-declared)

Time-block adjustment (5I); leave-one-repo-out (drop django, then each other repo; report the range of the primary contrast); 493-instance denominator; `infra_final` as missing; "no retry credit" (erratum 7); attempt-0-only estimate; Harbor verdict versus official `swebench` re-grade (section 11.4); surface-violation seeds removed (9H). If primary and sensitivity disagree both are shown and the primary stands.

---

## 10. Registry, freeze and logging

### 10.1 Registry (`experiments/registry.jsonl`, one JSON object per line, hash chain)

Fields as in the existing file: `item`, `note`, `path`, `prev_line_sha256`, `script_commit`, `sha256`, `t_utc`. Items to write, in order, before the first search rollout:

`suiteF_design` (this file), `suiteF_analysis_plan_amendment` (the amendment 11 text, section 14), `suiteF_registration_json` (cells, contrasts, Holm families, margins), `suiteF_splits_gym`, `suiteF_splits_dev`, `suiteF_id_hashes`, `suiteF_decontam_report`, `suiteF_oracle_exclusions` (oracle result per pool and Verified), `suiteF_model_registry` (provider, id string, listing, sampling), `suiteF_seed_artifact` (tree hash of S0), `suiteF_infra_classifier` (code hash), `suiteF_probe_report` (section 6 results), `suiteF_image_digests`, `suiteF_harbor_swebench_versions`, `suiteF_commit_cap_evolve`, `suiteF_commit_adapter`. Before the Verified window opens: `suiteF_champions` (artifact tree hashes and the selection rule output on SEL-60), `suiteF_final_order` (hash of the randomized order file), `suiteF_nstar`. Deviations go to `decisions.md` with the reason; affected analyses become exploratory.

### 10.2 Logging

- One record per rollout: `cell`, `seed`, `artifact_tree_sha256`, `pool`, `task_id`, `attempt`, `attempt_seed`, start and end UTC, queue seconds, Harbor job and trial dir, hash of `result.json`, reward, `exception_info`, classifier label, retries and their causes, turn count, wall seconds, tokens by role (gateway ledger with tags `tag:F10-hc-s0:<arm>:{target,optimizer}`), count of denied network connections, `counted` flag (for N\*), path of `model_patch.diff` and its hash.
- Search level: `events.jsonl`, candidates, rejected, promotions per search (5M-4), optimizer transcripts, history-read scan counts (F22).
- The final order, window start and end, every interruption (a block boundary), the hourly canary.
- Artifacts are stored by content hash; the trajectories needed for leaderboard-style reasoning traces are kept with the final rollouts.

---

## 11. Run commands, infrastructure rule and re-grading

### 11.1 Commands (shape; pin real flags in build item B2)

```
# install and pin
uv tool install harbor==0.24.0      # confirm the PyPI name and version, UNVERIFIED
harbor datasets list | grep -i -E "swebench|swegym"     # confirm dataset names and versions
python3 -I swebench_assets/swebench_splits.py --cache $CACHE --out $OUT   # splits, hashes, decontam

# oracle sweep (harness check, no model)
harbor run -p datasets/swegym -a oracle -n 48 -o jobs/oracle_gym

# one evaluation batch (what the adapter issues per candidate)
harbor run -p $TASKDIR -a claude-code -m "$GLM_ID" -n 48 -o $JOBS \
   --ae ANTHROPIC_BASE_URL="$GATEWAY" --ak max_turns=200 -y        # key and agent-kwarg names UNVERIFIED

# a search (hill-climb, stock gate), from the cap-evolve campaign tooling
cap-evolve run --spec suiteF/F10-hc.yaml --project $PROJ --run-ts s0 --dashboard off

# final window, all arms interleaved
python3 experiments/final/run_final.py --suite F --order $ORDER_FILE --manifest $MANIFEST
```

Environment variables, as in the colleagues' launcher but with the isolation changes: `HARBOR_DATASET` (local path to the generated pool), `HARBOR_AGENT=claude-code`, `HARBOR_MODEL`, `HARBOR_PARALLEL=48`, `HARBOR_TIMEOUT` per batch, `HARBOR_EXTRA_FLAGS` for the environment (docker or openshift). Never write keys into the run directory or the registry.

### 11.2 Infrastructure error rule (analysis plan 5O, applied to Harbor)

Frozen classifier, applied blind to arm and reward, published with its code hash. Labels:

- **Valid:** the verifier wrote a reward (0 or 1).
- **Artifact-induced, scored 0, never retried:** agent timeout, turn cap, empty or non-applying patch, context exhaustion, a verifier timeout on a task whose oracle run finished well inside the timeout in the same image (the artifact's patch slowed the tests), a candidate crash.
- **Infrastructure, retry up to 3 times with new attempt seeds, same policy on every arm:** image pull failure, container start or build timeout, Docker daemon or host out-of-memory not attributable to the artifact, gateway 429 or 5xx or timeout with provider evidence, verifier crash with no reward file and no agent fault, Harbor internal error.
- After the third retry an infrastructure cell is `infra_final`: scored 0 in the primary analysis, missing in the sensitivity analysis. Hangs beyond 3 h: one retry, then missing.
- Anything unclassified counts as a failure. The exception-type list comes from the pilot (Harbor writes `exception_info` in `result.json`); freeze before the first search.
- Report per arm: attempted, retried, infrastructure-first, recovered at retry 1, 2 or 3, `infra_final`, hang cases, with Wilson intervals next to the in-window seed's rate (5O-3, 5O-4). Search-time promotion decisions treat `infra_final` as a failure for the candidate and for the baseline alike (issue #306 fixed the earlier zero-as-reward bug; keep its test).

### 11.3 Candidate-induced sandbox damage

The Suite B finding (a candidate induced 17% sandbox 500 errors) applies here: a tool that fills the disk, spawns runaway processes, or kills the container produces infrastructure-like errors. The first-attempt and final rates per artifact are compared with the seed's in the same window and flagged (5O-4); the "no retry credit" sensitivity (erratum 7) is reported for flagged artifacts.

### 11.4 Re-grade with the official harness

For every champion on Verified, extract `model_patch.diff` and run the official evaluation (`python -m swebench.harness.run_evaluation` with the dataset revision of section 1, the same Docker image digests) on all 500 patches of the headline champion and on a random 100 of every other champion. Report agreement with the Harbor verdict. Disagreements are listed by instance, with the Harbor `swebench==4.0.3` grader and the official library version both stated. The 7 known oracle exceptions are marked.

---

## 12. Build checklist and acceptance tests

Existing: `capevolve_harbor` (run, results, tasks), the Harbor adapter template, the swe_bench litellm template (not agentic), the campaign's final-eval machinery (`experiments/final`), gateway tagging, rule P, the stock gate, the hidden-history flag, the Claude shim sandbox. Existing CI tier `ci/benchmarks/swebench/full` is built from Verified itself (250 ids, split 100/50/100) and **must not be used** for optimization in Suite F; add a guard that fails a Suite F spec if any pool id is a Verified id.

| Id | Build item | Acceptance test |
|---|---|---|
| B1 | Split loader: `swebench_splits.py` plus a verifier that recomputes the four hashes of section 3.3 on a clean machine | hashes equal; an injected Verified id in a pool makes the guard fail |
| B2 | Harbor environment: install v0.24.0, list datasets, generate SWE-Gym and dev task dirs for the pools | `harbor run -a oracle` passes on at least 95% of each pool; failures listed and replaced per 3.3 |
| B3 | Candidate injection for Claude Code: prompt, skills, tools mounted per rollout, surface lock, `max_turns` | a canary candidate whose prompt says "write READY to /logs/x" produces the file in every container; a candidate editing a locked surface is counted as a violation |
| B4 | Network allowlist (gateway only) in the chosen Harbor environment | probe 3 of section 6 fails github.com and pypi.org, passes the gateway, in 100 of 100 random containers |
| B5 | Future-commit probe on all images; derived clean images where needed (future objects stripped; optionally grader dependencies baked in so the verifier can run with no network) | probe 2 of section 6 prints 0 on all 500 + pool images, a derived image grades the oracle patch identically to the original, digests registered |
| B6 | Phase-separation probe (no `/tests`, `/solution`, test patch in the agent phase) | probe 1 of section 6 clean on 100% of containers in the pilot |
| B7 | Optimizer sandbox for GLM 5.3 and Sonnet 5.5 (no egress, masked mounts, feedback staging directory with trajectories and verifier logs of OPT-100 only) | a planted file `canary_gold.txt` outside the feedback directory is never read in a 3-iteration dry run; transcript scan shows 0 forbidden paths |
| B8 | Patch-hash decontamination inside the evaluator | planted duplicate (a Verified gold patch inserted into a toy pool) is caught |
| B9 | Empirical null pool: S0 evaluated K = 40 times on OPT-100, replayed through the real stock gate, one-stage gate and rule P (as in 7F of the plan) | false-accept rates per decision and per 10-candidate search with intervals; compared with section 9.3 approximations |
| B10 | Harbor adapter for cap-evolve: batch evaluation, per-task rewards, trajectories, `exception_info`, infra classification, retries, token ledger tags | on PIL-40, 20 forced infrastructure failures (kill container, block gateway) are retried and labelled; 20 forced agent timeouts are scored 0 |
| B11 | Patch extraction post-step and official re-grade script | on 50 instances, Harbor verdict equals the official verdict, or each difference is explained |
| B12 | Scorer adapter and final-eval entry for Suite F (`run_final.py --suite F`), order file, interleaving, block analysis | dry run on REH-100 with S0 and one dummy champion reproduces the paired CR1 numbers of a hand computation |
| B13 | Competitor adapters F30, F32 to F37 | each runs 3 iterations on OPT-40 within budget accounting, returns an artifact that loads in the scaffold, and its counted rollouts match the harness counter |
| B14 | Candidate static scan (section 6, item 4) | 20 planted violations rejected, 20 clean candidates pass |
| B15 | Cost and token ledger for GLM on the gateway | pilot reports tokens and dollars (or GPU hours) per rollout by role |
| B16 | Analysis scripts for section 9 on synthetic data | a simulated null reproduces size 0.05 within Monte Carlo error; a planted +0.06 effect is detected with power near 0.8 at the MDE table settings |

Stop rules: any failure of B4 to B7 blocks all search and final rollouts. B9 and B15 results may update planning constants but not rules.

---

## 13. Deliverables and the claims each supports

| Deliverable | Contents | Supports |
|---|---|---|
| D1 Validity report | section 2.2 items 1 to 12 answered for the colleagues' run, with files | which parts of 482/500 are held out; wording of any public statement |
| D2 Frozen package | this design, registration JSON, split files, hashes, classifier, probes, image digests, chained registry lines | that the design was fixed before scoring |
| D3 Pilot report | s2, discordant rate, wall, tokens, infra rate, probe results, baseline pass rates | planning constants; go or stop |
| D4 Clean score table | P1 and P1-first with intervals for F00, F10, F11, F12, F13, F14 on Verified at N\*; per-seed values; promotions per search; inert fraction | "this artifact, as found in these runs, scores X on SWE-bench Verified (cross-repo, network blocked, held out), D above the baseline" (artifact level) |
| D5 Contrast table | the six primary rows with Holm-adjusted p, artifact-level and pipeline-level intervals, TOST rows | "gate A beats gate B", "search beats one-shot", "optimizer strength matters or does not", at the stated MDE |
| D6 Optimizer-strength decomposition | F10 vs F14 and both vs F00 | whether GLM 5.3 can optimize itself as well as Claude Sonnet 5.5 can optimize it |
| D7 Surface and history ablations (Tier 2) | S-ab family | which surface carries the effect; value of history |
| D8 Competitor comparison (Tier 3) | S-comp family, native-budget view | relative standing at matched rollouts; no "best optimizer" claim in advance |
| D9 DEV-225 and REH-100 replication | S-dev, S-reh | transfer to a second repo family and the in-pool number |
| D10 Cost table | rollouts, tokens, dollars, wall per search and per champion, cost per point (9D vi), break-even only if the CI excludes 0 | amortized value |
| D11 Leaderboard readiness note | which checklist items are met, which are not, and the re-grade table | whether a submission is allowed and with what wording |

Claims not supported by this design: any statement that the absolute Verified score is uncontaminated by pretraining; "state of the art across all leaderboards"; a claim that holds for other models or other scaffolds beyond the reduced Track M check; a claim about the optimizer from fewer than 5 seeds that is smaller than about 10 points.

---

## 14. Proposed amendment 11 to the analysis plan (text to register)

Amendment 11 (Suite F, SWE-bench Verified): the cells, splits, rules and contrasts of sections 3, 7 and 9 of this document; the primary family F of six rows at Holm m = 6; clusters = repos; TOST margin 0.05; DEV-225 and REH-100 are secondary and descriptive; section 5O applies; 9D (inert), 9H (surface violations) and 5H/5I (window and blocks) apply unchanged. Disclosure to write at registration: which of the campaign's results had been seen (all Suites A to E search-time results; none of Suite F), and that the planning inputs of section 9.3 come from the pilot.

---

## 15. UNVERIFIED items and how to settle each

1. Exact served build behind `rits/zai-org/glm-5-3` (weights revision, quantization): read the gateway model listing and server metadata at pilot time; the Hugging Face repository changed on 2026-10-12.
2. GLM 5.3 pricing and per-rollout tokens: none recorded; settle from the pilot ledger (B15).
3. GLM 5.3 training cutoff: not found; ask the vendor or state "unknown".
4. Harbor dataset names and versions at v0.24.0 (`swebench-verified` vs `swe-bench/swe-bench-verified`), and the digest of the dataset snapshot: `harbor datasets list`.
5. Claude Code version used by the colleagues, and the Harbor `claude-code` agent kwargs for max turns, appended system prompt and skills path: read the Harbor agent source and run B3.
6. Whether Harbor's `allowlist` network mode is enforced in the docker and openshift environments in use: B4.
7. Whether the SWE-bench images contain future commits: B5.
8. Availability and size of SWE-bench dev images and SWE-Gym images (Docker Hub rate limits): B2.
9. Whether the current top Verified leaderboard entry is higher than the 79.2 in the checked data file.
10. Repo overlap of SWE-smith and SWE-rebench with Verified (not computed).
11. Code availability, licence and commit of GEPA, ACE, SkillOpt, Meta-Harness, EvoSkill and Trace2Skill official repositories.
12. Whether the colleagues' final scoring used the same Harbor snapshot as the optimization runs, and whether any test-split gold was read by the optimizer (section 2.2 items 1, 4).
13. Wall per rollout under 2-vCPU containers and 48-way concurrency (planning 10 min).
14. Whether `reasoning_effort` can be passed through the gateway to the claude-code shim.
15. The 482/500 and 85.9% figures themselves: no artifact backs them in the repository (issue #777).
