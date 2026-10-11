# Benchmarks: pinned versions, task lists, hashes, local run commands

Written by the benchmark/scorer steward. All facts below were read from the repo checkout
(`/home/dev/projects2/cap-evolve-campaign`, HEAD `e3cb51309`) or fetched on 2026-10-11 from the URLs
given. Nothing here made an LLM call. Companion files: `scorer_audit.md`, `setup_log.md`.
Scratch root (not committed): `/home/dev/projects2/campaign-scratch/bench/` (`$BENCH`).

Hash convention for id lists (same as `ci/benchmarks/spreadsheetbench/utils/make_skillopt_split.py`):
`sha256("\n".join(sorted(str(id) for id in ids)))`. "file sha" is sha256 of the committed bytes.

## 1. How a CapEvolve benchmark run is launched (what CI does, so what local must reproduce)

`ci/benchmarks/lib/run_suite.sh <bench> [out_dir]` is the single entry point (CI calls it after
`ci_setup.sh <bench>`). It: reads `ci/benchmarks/<bench>/<TIER>/tasks.json`; resolves AGENT_MODEL /
OPTIMIZER_MODEL to a provider (`lib/resolve_provider.sh`); scaffolds ONE project under
`ci/benchmarks/.work/suite_<tier>_<bench>_proj/.capevolve/project/` by copying the adapter template
(`templates/adapters/<x>/adapter.py`, `model_config.py`) and a seed capability; writes a `.env` and a
`capevolve.yaml`; runs `python -m cap_evolve.cli check` then `cap_evolve.cli run --spec ... --run-ts suite
--max-iterations $ITER`; then `metrics.py` for the report. Defaults: agent `gpt-oss-120b`, optimizer
`claude-opus-4-8`, `ITERATIONS` 3 (smoke) / 10 (other), `NUM_TRIALS` 3 (smoke) / 1 (full, full_verified) /
10 (rest), `GATE_K_SE` 1.0 (0.2 for the hard-scoring spreadsheetbench tiers via committed `overrides.env`).
`ITERATIONS=0` is a supported "evaluate the seed only" run.

Provider config (names only; values come from the caller's environment, never from the repo):

| purpose | variables |
|---|---|
| gateway "ete-int" (default for plain model names) | `IBM_ETE_INT_API_BASE`, `IBM_ETE_INT_API_KEY` |
| gateway "ete" | `IBM_ETE_API_BASE`, `IBM_ETE_API_KEY` |
| RITS proxy | `IBM_RITS_API_BASE`, `IBM_RITS_API_KEY` |
| model selection | `AGENT_MODEL`, `OPTIMIZER_MODEL` (prefixed `ibm-ete-int/…`, `ibm-ete/…`, `ibm-rits/…`, or a plain name from `ci/benchmarks/model_catalog.txt`) |
| derived by `run_suite.sh` for the adapter | `MODEL=litellm_proxy/<wire>`, `LITELLM_PROXY_API_BASE`, `LITELLM_PROXY_API_KEY` (written to the project `.env`) |
| derived for the optimizer CLI | `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN` (exported process-wide from the OPTIMIZER provider) |
| tau2 user simulator | `TAU2_USER_MODEL` (default: same as `MODEL`, i.e. the agent model plays the customer) |
| other knobs | `TEMPERATURE` (0.0), `MAX_TOKENS` (8000), `TAU2_MAX_CONCURRENCY`, `TAU2_SIM_TIMEOUT` (1800), `SPREADSHEETBENCH_{CONCURRENCY,MAX_TURNS,SCORING,REWARD_RECALC,LIBREOFFICE_BIN,...}` |

Wire detail: `ibm-ete-int/aws/gpt-oss-120b` becomes model `aws/gpt-oss-120b` on the ete-int base URL;
`ibm-rits/x` becomes `rits/x`.

What does NOT run on a GitHub runner: nothing in the adapters needs GitHub. `ci_setup.sh` needs `uv`,
`npm` (installs the `claude` CLI), a docker daemon (spreadsheetbench) and clones external repos. None of that is
required to run the adapters; see section 6 for the local launch that skips `ci_setup.sh`.

### Containers
* SpreadsheetBench: the adapter uses the Python `docker` SDK (`docker.from_env()`) inside the vendored
  `third_party/spreadsheetbench/code_exec_docker/jupyter.py`; image `docker.io/xingyaoww/codeact-executor`
  (tag `latest`). It never calls the `docker` CLI except `run_suite.sh::_discard_dir` (cleanup fallback
  `docker run alpine rm -rf`) and `ci_setup.sh`'s `docker info` preflight. Local image digest pulled
  2026-10-11: `sha256:ed8c0478e05fc38734da336cc4925fbbec125244b70124b55f134b7c34982d67`
  (image id `233aff81790c`, created 2024-01-08, 13.7 GB, runs as uid 1000 `jovyan`, Python 3.11.6,
  openpyxl 3.1.2 inside). Resource limits in code: 8 GB RAM, 2 CPUs per container.
  **podman works** (verified, see `setup_log.md`): the SDK talks to podman's docker-compatible socket via
  `DOCKER_HOST=unix:///run/user/1006/podman/podman.sock`; `podman-docker` (installed) additionally provides
  the `docker` CLI shim.
* tau2 (`tau2` leg): no containers. `swebench`, `skillsbench` use harbor / benchflow containers (not in scope here).

## 2. SpreadsheetBench

### 2.1 Upstream pins
| item | value |
|---|---|
| repo | https://github.com/RUCKBReasoning/SpreadsheetBench , `main` HEAD `49b73a94775fb489063f60ca1865e3a650079a79` (2026-03-12, "Merge pull request #32 from RyanMarten/cross-platform-evaluation") |
| vendored harness | `third_party/spreadsheetbench` (NOTICE.md says upstream `0d9dc14`). Byte comparison on 2026-10-11: `evaluation/{evaluation,open_spreadsheet}.py`, `code_exec_docker/{api,jupyter}.py,config.json`, `inference/{code_exec,prompt_format,inference_single}.py` are IDENTICAL to upstream `main@49b73a9`. So the vendored scorer equals the current official one. |
| vendored scorer sha256 | `evaluation/evaluation.py` `4ae77cee8df01d1f3468…`, `open_spreadsheet.py` `8eafeb70aee06eaefc99…` |
| data URLs used by `fetch_data.sh` | `https://raw.githubusercontent.com/RUCKBReasoning/SpreadsheetBench/main/data/<file>` , i.e. **`main`, not a SHA** (unpinned in CI) |

Data archives (downloaded 2026-10-11; git blob SHA1 verified against the GitHub contents API; also record sha256):

| variant (`SPREADSHEETBENCH_VARIANT`) | file | bytes | git blob sha1 | sha256 | last commit touching it |
|---|---|---|---|---|---|
| `sample_200` (smoke) | `data/sample_data_200.tar.gz` | 19,936,871 | `4ff8918668c2876f1d6b6d17845a4fe76e57ef52` | `d5f97936a348aa84bbd4db818fc261adee1aa0429e21080b3157f98737da50d4` | `3502dd58…` 2024-06-20 |
| `full_912` (full, pilot) | `data/spreadsheetbench_912_v0.1.tar.gz` | 95,752,357 | `b4583957c7838204bb45c1a7af35d3581e7e8fb3` | `9cf7228b54f1edcdd4b372eb736774adf29cb4f804c9920229bac6c154833399` | `fdde69e1eb23b6514b4f6cf3ee8543aadaa7a2e3` 2025-12-03 |
| `verified_400` (full_verified) | `data/spreadsheetbench_verified_400.tar.gz` | 14,958,255 | `b6baaf0f23ef5adc1cd22078f4eeb3102b4a7c72` | `10ef893dd29cb13ab97143ea787e68cdc9574a13873ab9a54e50b31dc03fc949` | `fdde69e1eb23b6514b4f6cf3ee8543aadaa7a2e3` 2025-12-03 |

Note the 912 archive was re-committed on 2025-12-03 (previous: `3abd9f7a` 2025-10-20 "update version 0.1. Fix file name
error and broken files"), so a 912 download made before that date differs from today's. HF mirror used by SkillOpt:
`KAKA22/SpreadsheetBench` revision `ab0b742b0fc95b946f212d80ac7771b5531272e4` (`split_source.json`); we did not
check that this equals the GitHub blob above (their sha256 is not published) — treat as an open provenance item.

Extracted-tree manifests (every file sha256, plus one tree hash) are in `$BENCH/manifests/*.json`:

| extracted dir | files | tree sha256 (sorted `path\0sha256`) |
|---|---|---|
| `sample_data_200` | 1,202 | `5b9771bc0ab14d5542cc09e5bd9f55261dfb6808c95f60ec342ddd2229a53414` |
| `all_data_912_v0.1` | 5,465 | `e04fc0f83a937e0298595236971a0950a4cbae490a532f96f70bd9ad2c638f19` |
| `spreadsheetbench_verified_400` | 1,201 | `6179b6992682260e7d514febc536f5c396b55246c0f1a6fb79c0e2851ae5edf4` |

Data location on this host: `$BENCH/data/extracted/{sample_data_200,all_data_912_v0.1,spreadsheetbench_verified_400}`;
archives in `$BENCH/data/archives/`.

### 2.2 Tiers, task lists, splits (all committed under `ci/benchmarks/spreadsheetbench/`)

| tier | dataset | n tasks | tasks.json file sha256 | sorted-ids sha256 | split |
|---|---|---|---|---|---|
| smoke | sample_200 | 10 | `0aa785fe4ae36e52f805c66a6503457f6bac612bb62947e17927aab40f1c8515` | `fcb46dd884725eb798ab5d3b1031975491f41ee24a8f5df5388af1e790e9059d` | none: no-holdout FIT (train=val=test=10) |
| pilot | full_912 | 60 | `c42a6dbf7a0c96d6bc5d3cd102549b49128f7c7356fb51e23e4fd417034935e5` | `7fb8af0db6bd26e24c66216025aa600e18aabeccaff3a865a749468054d34e41` | 5 / 50 / 5 |
| full | full_912 | 912 | `59291a57e7388b7dfb87e376e9051d75f8f0e1b08e4c9d040d047b57a2b97a72` | `1f49913059a8ff1bdc6cba6e58d798f602d837b3251ff8175d21924681708f38` | 182 / 91 / 639 (CapEvolve's own seed-42 2:1:7 reconstruction) |
| **full_verified** | verified_400 | 400 | `cba080020a5284db37a720b28552dc8e38bc8fade7515e91ac5853bcdbeefb6d` | `51d1a478707515778e3dc15e85640ad314b752fa0b37f0ff948f70cbca8beb54` | **80 / 40 / 280, SkillOpt's released split** |

Split files (file sha256; per-split sorted-id sha256, first 16 hex):

| file | n (train/val/test) | file sha256 | train / val / test id-hash |
|---|---|---|---|
| `full_verified/split_ids.json` (**used**) | 80/40/280 | `fd40cc4ea53027c3cdf733b153c21b01147bbcfe179b4ef500b5207d13523370` | `c5eb753031aad2d5` / `8ac6ed589014d2f0` / `54608b02b59450fb` (full digests in `split_source.json`, which match) |
| `full_verified/split_ids.capevolve_seed42.json` (older CapEvolve draw; shares 194/280 test ids with SkillOpt's) | 80/40/280 | `f7f38e0cab2d8d57407e7b77aa97a3fab2d39db233c0df332f6fc44b6a7a6ef8` | `12dee6e3bf1984ed` / `9a573cecfec134a9` / `23d43cfcb7b8ab45` |
| `full_verified/split_source.json` | | `0f0d895190d4858eafe07166a206a915e1f2d612df4228e3ca88f2f202852aed` | pins `microsoft/SkillOpt@79124b37e9a6371e13b753f8bcd7adb1e493ade1` |
| `full/split_ids.json` | 182/91/639 | `5100fe6dc1fb4161ce8e35c00d9772a3cbc99fbce154825f9233486097ccbfd5` | `c288abae39a026bd` / `bc6cb023835289e0` / `b463c71b48731cd6` |
| `pilot/split_ids.json` | 5/50/5 | `e137e85c95f273ef5c052e3e9d305df420ccb2c37dc7a9556681fd5570a87bb9` | `4f351a7e5af086c0` / `909a3f205f9a62c0` / `aa60222f3938ef7f` |

Verified on this host: every id in each tier's tasks.json exists in that tier's dataset (0 missing); the
`full_verified` split covers exactly its 400 task ids. Smoke ids: `250-20 262-17 32438 32902 47766 48365 48745 493-18 52216 54638`.

Scoring/config per tier (from `overrides.env` and `run_suite.sh`): `SB_SCORING=hard`, `GATE_K_SE=0.2` for full /
full_verified / pilot; max turns 5 (smoke) or 30; container concurrency 4 (smoke) or 8; **reward = as-saved
comparison (`hard_no_recalc`)** unless `SB_REWARD_RECALC=1`; `VERIFY_TURNS=3` extra rounds after the first output
file exists; verified_400 grades 1 case/task, 912 grades 3 (4 tasks ship fewer). Capability = `prompt.md` +
`task_template.md` (`capabilities: [system-prompt]`); the optimizer may edit only those two files.

### 2.3 Scorer: see `scorer_audit.md`. One-paragraph summary
The reward compares cached cell values (`openpyxl data_only=True`) of agent output vs gold over `answer_position`. By
default the output is **not recalculated** (since the #538 follow-up), so a formula written without a cached value
reads `None` and fails; in the verified-400 gold, 282/400 (70.5%) tasks contain formula cells in the answer range, so
this matters a lot. The recalculation path (`SB_REWARD_RECALC=1`, and the always-recorded `*_restriction` metrics)
uses LibreOffice on the candidate output only (never the gold) and is engine-version sensitive. Details and numbers
in `scorer_audit.md`.

## 3. tau2 airline

**Two different task contents exist and must not be mixed** (verified by hashing `tasks.json` at each ref):

| label | where | tau2-bench code | airline `tasks.json` sha256 | `split_tasks.json` | policy.md |
|---|---|---|---|---|---|
| **tau2 (original task content)** | tag `v0.2.0` `f8de30c298689cbe0117d76a378e7315a17e5bd8` (2025-10-06); also the `skillberry-benchmarks@a3a8326` vendored fork used by the `tau2_custom_{direct,blackbox}` arms (`tau2/tau2-bench`, version `0.0.1`) | v0.2.0 | `40d692b3fca780f46b56d48b447fd8db79a653f216667b8ed7c1a88380544532` | absent (404) | `10dc0525…` |
| **tau3 (τ³-bench, task-quality fixes)** | tags `v1.0.0` `17e07b1d…` (2026-03-18), `v1.0.1` `fc0055dc…` (2026-07-22); the example run pin `8ebb7499622fc2be9b9d510d6f7a7653461f4f29` (2026-06-22, 112 commits after v1.0.0, 14 before v1.0.1); `main` `4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699` (2026-10-07) | v1.0.0 … main | `ccd8ba737b4cc371415af70151187788f728d6108d0916e73bb4317b40542052` (identical at all four refs) | 30 train / 20 test; file sha256 prefix `b22ced4d9a9850ac` | `10dc0525…` (unchanged) |

v1.0.0 release notes: "Task Quality (75+ fixes) — Airline (27 tasks): removed incorrect expected actions, clarified
ambiguous instructions, fixed impossible constraints, closed policy loopholes, added missing fallback behaviors."
All 50 tasks' `evaluation_criteria` differ between the two; 22 `user_scenario`s and 10 `description`s differ.
`policy.md` is byte-identical. So a score on the `tau2_custom_*` arms (original tasks) is **not** comparable to the
`tau2` leg or the `examples/tau2_airline` runs (tau3 tasks), and the CI `tau2` leg is unpinned (below).

**What CapEvolve actually used**
* Example / paper-style runs (`examples/tau2_airline`, `docs/RESULTS.md`, `docs/REPRODUCE_tau2.md`): tau2-bench
  `8ebb7499622fc2be9b9d510d6f7a7653461f4f29` (recorded in `examples/tau2_airline/run_full/TAU2_COMMIT.txt`), i.e. tau3-era code and tasks.
* CI `tau2` leg: `ci_setup.sh` does `git clone --depth 1 https://github.com/sierra-research/tau2-bench` (HEAD of main at
  first clone) into a runner cache that is then reused forever; the commit is **not recorded** by CI. Whether any CI
  result used v0.2.0 or tau3 is not recoverable from the repo. For a campaign: pin `8ebb749…` (matches the example
  runs) and record `git rev-parse HEAD` in every run.
* `tau2_custom_*` arms: `skillberry-ai/skillberry-benchmarks` pinned to `a3a83266008275e9d800fd709927fa3dc4f23ec5`
  (2026-07-15; the 2026-07-26 HEAD is `ca102815…`). Original (pre-tau3) task content, Skillberry-modified tau2 build
  (`tau2-bench[skillberry]`, not the public package).

**Task ids and splits used historically** (all ids are strings "0".."49"; airline has 50 tasks;
`reward_basis` is `[DB, COMMUNICATE]` for all 50, so scoring is fully deterministic and needs no LLM judge):
| name | file | n | sorted-ids sha256 (prefix) | notes |
|---|---|---|---|---|
| CI `tau2` full tier | `ci/benchmarks/tau2/full/tasks.json` (file sha `7c3b2f73…`) | 50 | `dbde4f8078714e7b…` | no-holdout: train=val=test=all 50 |
| CI `tau2` smoke | `ci/benchmarks/tau2/smoke/tasks.json` (`2d04226c…`) | 10 | `0889b92fdd9e2afe…` | ids 17 40 12 8 37 23 25 22 19 11 |
| CI `tau2` integration (1 task) | `ci/benchmarks/tau2/integration/tasks.json` (`82e72911…`) | 1 | `19581e27de7ced00…` | id 9 |
| example default | `examples/tau2_airline/split_ids.json` | 50/50/50 | `dbde4f8078714e7b…` | no-holdout fit |
| **example held-out (v4 agent-optimize)** | `examples/tau2_airline/agentopt_split.json` | **26 / 12 / 12** | train `7efe58690573a260` val `864aa4cc3020e10a` test `d79e3003b0b054db` | stride split: val = 0,4,8,…,44; test = 1,5,9,…,45; train = the rest {2,3,6,7,10,11,14,15,18,19,22,23,26,27,30,31,34,35,38,39,42,43,46,47,48,49}. Identical copy in `run_agentopt_v4/splits.json`. |
| example itest / smoke | `itest_split.json` / `smoke_split.json` | 1 / 2 | | id 9 ; ids 0,1 |
| tau2's own official split (tau3 only) | `data/tau2/domains/airline/split_tasks.json` | 30 train / 20 test | train `70166c3fe3cd9ac8`, test `978688d650805deb` | NOT used by CapEvolve. Does not exist at v0.2.0. |

**Runner settings** (`templates/adapters/tau2_bench/adapter.py`): agent `llm_agent` with `MODEL`
(default CI `aws/gpt-oss-120b`), user `user_simulator` with `TAU2_USER_MODEL or MODEL` (CI never sets it, so the
agent model also plays the customer), temperature 0.0 and max_tokens 8000 from the project `.env`, `num_trials=1` per
call (CapEvolve loops trials itself via `run_trials`), **`max_steps=100`, `max_errors=10`** (tau2's own defaults are
200/10), `timeout` 1800 s, seed = harness `base_seed`, concurrency 10 (`TAU2_MAX_CONCURRENCY`). tau2 internal
defaults for NL-assertion judge etc. (`gpt-4.1-2025-04-14`) are not exercised for airline (no NL_ASSERTION basis).
The adapter drops rollouts where the simulator leaks `###STOP###` together with "continue" text as infra noise
(`_leaked_stop_continuation`), i.e. it removes simulator artefacts from the denominator (a CapEvolve-side
modification of the score definition; disclose it).

**Editable surface vs benchmark-owned** (CI `tau2` leg: `CAPS="[system-prompt, tools]"`; seed from
`examples/tau2_airline/seed_capability`):
* Optimizer may edit: `policy/policy.md` (system prompt), `tools/tools.py` (subclass of tau2 `AirlineTools`,
  re-declares every agent-callable tool; module-level `REMOVE_TOOLS` can hide tools), `reference/data_model.py`
  (copy of tau2 types, supplied as guidance via `capability_sources`).
* Benchmark-owned and NOT editable by design (but not technically protected — see isolation): tau2 package code
  (orchestrator, user simulator, evaluator, `get_tasks`), `data/tau2/domains/airline/{db.json,tasks.json,policy.md}`,
  the adapter, `model_config.py`, seeds/splits.
* Important isolation fact: `adapter._load_candidate_tools_class` executes the candidate `tools.py` **in the evaluator
  process** (`spec.loader.exec_module`) and `apply()` monkey-patches `tau2.registry`. Candidate code therefore runs with
  the evaluator's privileges and could in principle alter evaluation state. `capabilities` selects validation and
  guidance, it does not gate writes (comment in `run_suite.sh`).
* **Evaluator coupling (verified in code):** `adapter.apply()` replaces `tau2.registry._domains["airline"]` with a constructor
  built from the candidate `tools.py`. tau2's evaluator (`evaluator/evaluator.py:167,191,273` -> `evaluator_env.py:81,92`) calls
  `registry.get_env_constructor(domain)` to build BOTH the "predicted" environment and the "gold" environment (gold actions are
  replayed on it) for the DB check. So a candidate's tool edits change how the gold final state is computed, not only how the
  agent acts. A candidate that weakens or no-ops state-changing tools shifts both sides. This is an evaluator-isolation gap
  that file permissions alone do not close; the clean fix is to evaluate with the pristine tau2 constructor (patch idea: keep
  the original constructor for `evaluate_simulation`, use the candidate constructor only for the agent's environment).

**Local install** (verified): isolated venv `$BENCH/venv-tau2-8ebb749` (python 3.12.15), tau2 editable from
`$BENCH/src/tau2-8ebb749` (detached HEAD `8ebb7499622fc2be9b9d510d6f7a7653461f4f29`, sparse checkout without
voice/web/banking data), plus `cap-evolve-core` editable and `litellm==1.82.6` (tau2 requires `>=1.80.15,<1.82.7`).
Import / task-listing verification output is in `setup_log.md`.

## 4. Other benchmarks (facts only; nothing installed). Dates are retrieval date 2026-10-11

| benchmark | CapEvolve usage | current upstream | URL |
|---|---|---|---|
| **SkillsBench** | CI: `GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 https://github.com/benchflow-ai/skillsbench` (**unpinned main**) + unpinned `uv tool install benchflow`; smoke = 10 tasks (`offer-letter-generator exceltable-in-ppt xlsx-recover-data sales-pivot-analysis invoice-fraud-detection weighted-gdp-calc financial-modeling-qa pdf-excel-diff pptx-reference-formatting reserves-at-risk-calc`), `full/tasks.json` is EMPTY (`[]`). Version used by past CI runs is not recorded. | Releases: **v1.1** 2026-06-14 "native task.md package release" (tag commit `b63b7b2850226b6aa4fb5929a8c1ac7bc4d9a6af`), **v1.0** 2026-06-12 "87-task benchmark snapshot" (`14f3396760786d4ec9ea28e7b865f2ce4d199fdf`). `main` HEAD `9a1f4dd5f7659f75707435da3ce854b6e48321d1` (2026-07-23). Apache-2.0. | https://github.com/benchflow-ai/skillsbench/releases |
| **Terminal-Bench** | Not used by the CI suite (only mentioned in agent-optimize microcase docs). | `harbor-framework/terminal-bench` is now the "continuous benchmark" repo (formerly TB3 line): tags **v3.0.0** `2b0442c3…`, **v4.0.0** `452bf305c6daa62fc59061d22133a7cbc7c1572e` (release 2026-08-26); HEAD `209679e34327a78ce8e9bf5300b2f317992863c9` (2026-10-09); datasets published on Harbor Hub `terminal-bench/terminal-bench@latest`. Terminal-Bench 2.0 is `harbor-framework/terminal-bench-2` (HEAD `2fd12b88…`, last push 2026-04-30; "TB2.1" task fixes 2026-02-27); the original 1.x line is `harbor-framework/terminal-bench-1` (pushed 2026-07-11). Run with `harbor run -d terminal-bench/terminal-bench@<version>`. | https://github.com/harbor-framework/terminal-bench , https://github.com/harbor-framework/terminal-bench-2 |
| **SWE-bench Pro** | Not used (CapEvolve's swebench leg is SWE-bench *Verified* ids through harbor; 250 in `full`, 5 in `smoke`). | Public set is available without gating on HuggingFace `ScaleAI/SWE-bench_Pro` (dataset sha `2d52cb3df914a3fcf80c7f66738b3a88ae37fc50`, last modified 2026-09-22): config `v1` = original **731** public tasks; `default` = **V2, 642** validated tasks in 11 repos (released 2026-09-22, GitHub release `v2.0.0`, tag commit `66f92766bba642462d4bbe5479e83f91f9211862`); `hard` = HARD-51. V2 task images are public: `ghcr.io/scaleapi/swe-bench_pro-v2:<instance_id>`. There is also a separate private commercial leaderboard that is not public. MIT (GitHub repo). | https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro , https://github.com/scaleapi/SWE-bench_Pro-os |
| SWE-bench (reference) | harbor adapter | `SWE-bench/SWE-bench` v5.0.1 `87ab1f6ced28f75ba73ca899dc759b019310944a`, main HEAD `02e7a74f…` 2026-09-02 | https://github.com/SWE-bench/SWE-bench |

Caveat: GitHub's unauthenticated API rate limit (60/h per IP, shared by all agents on this host) was exhausted during
this session; dates for TB `v3.0.0` and the TB2 releases list could not be retrieved and are left blank rather than guessed.

## 5. Open provenance items that block "pinned" claims for past CI results
1. CI never pinned: SpreadsheetBench data (`main`), tau2-bench (`--depth 1` main + cached), SkillsBench (`--depth 1` main), benchflow, harbor, litellm.
2. LibreOffice version for past SpreadsheetBench CI runs is not recorded; adapter docstring says the runner is RHEL 9 with 7.1.8.1.
3. tau2 `max_steps=100` differs from tau2 default 200 and from published leaderboard settings.
4. Whether the 912 archive used in past runs predates the 2025-12-03 re-commit is unknown.

## 6. Local run commands (the coordinator executes these with provider env set)

Prereqs on this host (already done, see `setup_log.md`): podman 5.8.2 + `podman-docker`, systemd user session for
uid 1006 (lingering), `podman.socket` active, codeact-executor image pulled, LibreOffice 7.1.8.1 at `/bin/soffice`
(RHEL) and 25.8.7.3 at `$BENCH/lo258/root/opt/libreoffice25.8/program/soffice` (rootless extract).

```bash
source /home/dev/projects2/campaign-scratch/bench/local/env_local.sh     # DOCKER_HOST etc., no secrets
# provider (names only; the coordinator supplies values):
export MODEL=litellm_proxy/aws/gpt-oss-120b            # wire id of the AGENT model
export LITELLM_PROXY_API_BASE=$IBM_ETE_INT_API_BASE LITELLM_PROXY_API_KEY=$IBM_ETE_INT_API_KEY
```

**SpreadsheetBench single-task smoke (agent only, no optimizer; <= `--max-turns` + 3 agent calls)**
```bash
$BENCH/venv/bin/python $BENCH/local/sb_single_task.py --task 58687 --variant verified_400 --max-turns 30
#   --isolated is the default: patched adapter (patches/adapter_gold_dir.patch), agent sees a gold-free copy,
#   scorer reads the pristine tree. Add --historical for the repo adapter as shipped.
#   Add --soffice $BENCH/lo258/root/opt/libreoffice25.8/program/soffice to recalc with LibreOffice 25.8.
```
Task 58687 is a verified-400 task whose gold answer range contains formulas and which LibreOffice 7.1.8.1 recalculates
correctly (useful because it exercises both metric families). Output: JSON with `reward` (= `hard_no_recalc`),
all four metrics, feedback, token cost. (`$BENCH/venv` = openpyxl, pandas, docker SDK, tornado, requests, tqdm, litellm 1.82.6, cap-evolve-core editable.)

**Full pipeline smoke through CapEvolve (`run_suite.sh`; optimizer spend only if ITERATIONS>0)**
`run_suite.sh` hard-codes `REPO` from its own path and reads tiers from `$REPO/ci/benchmarks/<bench>/<TIER>`. To run a
1-task tier without editing the repo, build the symlink overlay (`$BENCH/local/make_overlay.sh`, adds tier `one`
containing one task) and call the overlay's `run_suite.sh`. This exact path was exercised end to end on 2026-10-11 with an
unreachable gateway (`IBM_ETE_INT_API_BASE=http://127.0.0.1:9/v1`, dummy key): check, sandbox container start, baseline,
finalize, report all ran and every rollout failed with a connection error, so the plumbing is verified at zero spend.
```bash
$BENCH/local/make_overlay.sh spreadsheetbench one 58687
export CAPEVOLVE_PY=$BENCH/venv/bin/python TIER=one ITERATIONS=0 NUM_TRIALS=1 SB_SCORING=hard GATE_K_SE=0.2 \
       SPREADSHEETBENCH_DATA_DIR=$BENCH/data/extracted/spreadsheetbench_verified_400 SPREADSHEETBENCH_MAX_TURNS=30 \
       SB_KEEP_LATEST_RUN=0 AGENT_MODEL=gpt-oss-120b OPTIMIZER_MODEL=claude-opus-4-8   # plain names: CI picks RITS > ete-int > ete (repo CLAUDE.md)
#   + provider vars (names only): IBM_RITS_API_BASE/KEY, IBM_ETE_INT_API_BASE/KEY, IBM_ETE_API_BASE/KEY
bash $BENCH/overlay/ci/benchmarks/lib/run_suite.sh spreadsheetbench $BENCH/out/suite_sb_one     # out dir must be ABSOLUTE
```
`ITERATIONS=0` evaluates the seed only (no optimizer tokens, no `claude` CLI needed). With `ITERATIONS>=1` the `claude` CLI
must be on PATH (not installed on this host; `npm install -g @anthropic-ai/claude-code --prefix ~/.local`). The overlay path runs the repo
adapter as shipped (historical, un-isolated); use the single-task driver above for the isolated layout.

**tau2 airline single-task smoke (agent + user simulator, no optimizer)**
```bash
$BENCH/venv-tau2-8ebb749/bin/python $BENCH/local/tau2_single_task.py --task 9 --seed 0
#   optional: export TAU2_USER_MODEL=litellm_proxy/<model>   (default = agent model, as in CI)
```
Task 9 is the CI "integration" (1-task) tier. Output JSON: `reward` (tau2's deterministic DB+COMMUNICATE check),
tokens/cost, truncated feedback. Full pipeline (also exercised at zero spend): `make_overlay.sh tau2 one 9`, then
`CAPEVOLVE_PY=$BENCH/venv-tau2-8ebb749/bin/python TIER=one ITERATIONS=0 NUM_TRIALS=1 AGENT_MODEL=gpt-oss-120b bash $BENCH/overlay/ci/benchmarks/lib/run_suite.sh tau2 $BENCH/out/suite_tau2_one`.
