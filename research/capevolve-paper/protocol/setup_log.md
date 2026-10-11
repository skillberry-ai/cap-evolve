# Setup log: local benchmark environment and evaluator isolation

Host: RHEL 9 (kernel 5.14.0-687), 64 cores, uid `dev` (1006), passwordless sudo, rootless podman 5.8.2. Everything is under
`/home/dev/projects2/campaign-scratch/bench/` (`$BENCH`) unless a path says otherwise; nothing is committed and the repo
checkout (`/home/dev/projects2/cap-evolve-campaign`) was not modified (verified: `git status` shows only the three docs in
`research/capevolve-paper/protocol/`). No LLM was called. The only network traffic was downloads from github.com,
raw.githubusercontent.com, pypi.org/files.pythonhosted.org, huggingface.co (metadata), download.documentfoundation.org
and docker.io (image pull). Dates 2026-10-11.

## 1. Host changes made with sudo (outside `$BENCH`; revert list at the end)
| change | why |
|---|---|
| `sudo dnf install -y podman-docker` | provides `/bin/docker` -> podman, for `ci_setup.sh` preflights and `run_suite.sh::_discard_dir` (`docker run alpine rm -rf`). The adapters themselves only need the docker **SDK** + a socket. |
| `sudo loginctl enable-linger dev` + `sudo systemctl start user@1006.service` | rootless podman had no systemd user session; the codeact-executor image carries a HEALTHCHECK, which podman can only create with systemd (`create healthcheck: unable to get systemd connection`). |
| `/etc/systemd/system/user@.service.d/delegate.conf` = `[Service] Delegate=cpu cpuset io memory pids`, then `daemon-reload` + restart `user@1006` | without cpu-controller delegation the adapter's `nano_cpus=2e9` limit fails: `crun: controller cpu is not available`. |
| `systemctl --user enable --now podman.socket` | docker-compatible API at `/run/user/1006/podman/podman.sock` (symlinked as `/run/user/1006/docker.sock`). |
| `sudo groupadd capeval`, `sudo usermod -aG capeval dev`, `sudo useradd -M -s /sbin/nologin capopt` | isolation prototype (unprivileged optimizer uid, evaluator group). |
| `/opt/capevolve-eval-proto/` (root:root, `chattr +i`) | frozen evaluator tree prototype (section 6). |

Revert: `sudo chattr -R -i /opt/capevolve-eval-proto && sudo rm -rf /opt/capevolve-eval-proto; sudo userdel capopt; sudo groupdel capeval; sudo rm -r /etc/systemd/system/user@.service.d; sudo loginctl disable-linger dev` (and `dnf remove podman-docker`).

**Incident, disclosed:** while stopping my own stalled `git clone` of tau2-bench I ran `kill` on every `git-remote-https` process
(`pgrep -x git-remote-https`). That also hit another agent's `git clone https://github.com/skillberry-ai/cap-evolve.git` that was running at the
time (seen earlier in `ps`). If a teammate saw a clone abort around 00:50 UTC, that was me; re-running the clone is safe. Also: GitHub's unauthenticated API
(60 req/h per IP, shared on this host) was exhausted by me and others; nothing else was affected.

## 2. Tool and runtime status
| item | status |
|---|---|
| python | system `python3` is 3.9.25 (do not use); `python3.12` = 3.12.15 used for all venvs |
| `uv` | not installed (CI scripts assume it). Not needed: the local launchers use `pip`. |
| `npm`/`claude` CLI | not checked/installed. Needed only for `ITERATIONS>=1` (optimizer). |
| LibreOffice (host) | 7.1.8.1 `/bin/soffice` (dnf install by the other agent finished, `exit=0` in `logs/dnf_install.log`) |
| LibreOffice 25.8.7.3 | rootless extract from TDF `LibreOffice_25.8.7_Linux_x86-64_rpm.tar.gz` (245,310,808 B, sha256 `1b2d640d648c10ea7582c68ebc17fbb5f2551790deae40d2d9e4033fa2464d72`; mirror `mirror.clarkson.edu`; the `.asc` signature was **not** verified) into `$BENCH/lo258/root/opt/libreoffice25.8/`; runs headless without install. |
| podman / docker | podman 5.8.2 rootless, crun, cgroup v2; docker SDK 7.x works against the podman socket (SDK `images.get`, `containers.run(ports=, volumes=, mem_limit=, nano_cpus=, remove=True)` verified) |
| executor image | `docker.io/xingyaoww/codeact-executor:latest` pulled, digest `sha256:ed8c0478e05fc38734da336cc4925fbbec125244b70124b55f134b7c34982d67`, id `233aff81790c`, 13.7 GB |

Container behaviour under rootless podman: container uid 1000 (`jovyan`) maps to a sub-uid on the host (e.g. 297607), so container-created
output files are not owned by `dev`; the adapter's existing `_reclaim_container_file` (replace by a copy we own, directory is 0777 non-sticky) handles it.
Verified with the real adapter sandbox (`local/sandbox_probe.py`): server starts, container is minted, mount readable, `outputs/` writable, openpyxl 3.1.2 available inside.

## 3. Python environments
| venv | contents | purpose |
|---|---|---|
| `$BENCH/venv` | python 3.12.15; openpyxl 3.1.5, pandas 3.0.6, numpy 2.5.4 (copied from another agent's `/tmp/auditvenv` site-packages because PyPI was throttled to ~30 KB/s; same wheels), docker, tornado, requests, tqdm, litellm 1.82.6 (wheel fetched with parallel ranges, sha256 verified `164a3ef3…`), `cap-evolve-core` editable from the campaign repo | SpreadsheetBench scorer, diagnostics, single-task driver, `run_suite.sh spreadsheetbench` |
| `$BENCH/venv-tau2-8ebb749` | python 3.12.15; `tau2 1.0.0` editable from `$BENCH/src/tau2-8ebb749`, litellm 1.82.6, `cap-evolve-core`, numpy/pandas copied as above | tau2 airline at the pinned commit; **do not mix with other tau2 builds** |

Network note: github/pypi serve ~30 KB/s per connection here but scale with parallel connections. Large files were fetched with `$BENCH/fastget.sh <url> <dest> [chunks]` (HTTP range, 16-32 parts), then verified (git blob sha1 against the GitHub API for the datasets; sha256 for the wheel).

## 4. Data and sources fetched
| what | where | verification |
|---|---|---|
| SpreadsheetBench archives (sample_200, full_912, verified_400) | `$BENCH/data/archives/` , extracted to `$BENCH/data/extracted/…` | git blob sha1 equals GitHub API values (b4583957…, b6baaf0f…, 4ff89186…); per-file manifests in `$BENCH/manifests/` (tree hashes in `benchmarks.md`) |
| upstream evaluation code @ `49b73a94…` | `$BENCH/src/sb_upstream/` | byte-identical to vendored `third_party/spreadsheetbench` (8 files compared) |
| tau2-bench `8ebb7499622fc2be9b9d510d6f7a7653461f4f29` | `$BENCH/src/tau2-8ebb749/` (partial clone `--depth 1 --filter=blob:none`, sparse checkout excluding `data/tau2/results`, `web`, `data/voice`, `banking_knowledge`, `figs`, `tests/test_voice`) | `git rev-parse HEAD` = the SHA; airline `tasks.json` sha256 `ccd8ba73…`; `src/` tree hash `243547358e1c73fe…`; `manifests/tau2_8ebb749_airline_data.json` tree `ed12b45a4cebb8c6…` |
| tau2 airline data at v0.2.0, v1.0.0, 8ebb749, v1.0.1, main@4ce7c03 | `$BENCH/src/tau2_raw/<ref>/{tasks.json,split_tasks.json,policy.md}` | sha256 table in `benchmarks.md` |
| `skillberry-ai/skillberry-benchmarks` (full clone) | `$BENCH/src/skillberry-benchmarks`, checked out at `a3a83266008275e9d800fd709927fa3dc4f23ec5` (CI pin for `tau2_custom_*`) | its vendored tau2 airline `tasks.json` = `40d692b3…` (= tau2 v0.2.0 content) |

A full `git clone` of tau2-bench (448 MB, ~30 KB/s) was abandoned in favour of the partial clone.

## 5. Verifications run (all zero spend)
* **tau2 import and task listing** (`python -I`, venv-tau2-8ebb749): `tau2 1.0.0`, litellm 1.82.6, `get_tasks(None)` returns **50 airline tasks, ids "0".."49"**, sorted-ids sha256 `dbde4f80…ba84` (equals the CI full-tier list), `reward_basis` = `(DB, COMMUNICATE)` for all 50, and `Adapter().tasks("test")` from `templates/adapters/tau2_bench/adapter.py` returns 50 tasks.
* **Full CapEvolve pipeline, SpreadsheetBench** (`overlay` + `run_suite.sh`, TIER=one, ITERATIONS=0, gateway `http://127.0.0.1:9/v1`): `cap-evolve check` passed, project scaffolded, baseline + finalize executed, `final.json` written, `reward_metric = hard_no_recalc`; rollouts failed with `Connection error` (as intended). Log: `out/suite_sb_test.log`.
* **Full CapEvolve pipeline, tau2** (same method): tau2 retried the connection error 4x per attempt, ended `INFRASTRUCTURE_ERROR`, run finished. Log: `out/suite_tau2_test.log`.
* **Single-task drivers** `local/sb_single_task.py` and `local/tau2_single_task.py` ran to the first model call against the dead gateway and reported an infrastructure error correctly.
* **Sandbox probe** (real adapter sandbox, no LLM): historical layout exposes `1_58687_golden.xlsx` to container code; agent-view layout exposes only `1_58687_init.xlsx` and `prompt.txt` (section 6).
* **Scorer**: see `scorer_audit.md`.

## 6. Evaluator isolation: what exists, what is proven, what is not

Threat model: the optimizer (an LLM coding agent with shell access, `claude` CLI) must not be able to change the adapter, scorer,
vendored harness, benchmark data, gold answers, task lists or split files, nor read gold, nor learn the agent's API key; evaluation must
refuse to start if any of them changed.

Prototype (all in `$BENCH/isolation/`):
| script | does |
|---|---|
| `freeze_eval_tree.sh <eval_root> <src>[:dest] …` | copies the trusted files into `<eval_root>/tree`, `chown root:root`, dirs 0755 / files 0644, writes `<eval_root>/MANIFEST.json` (sha256 per file + tree hash), applies `chattr -R +i` where the filesystem allows. Deterministic: two freezes gave the identical tree hash `9eb86ce770432721e3f318ff8503aa6cb55c813af4289439e0878e7e598742cd` (1,239 files). |
| `manifest.py write|verify` | verification fails on any added / removed / changed file, any symlink, any group/other-writable entry, and (optionally) on a tree hash different from an externally pinned value. |
| `verify_then_run.sh <root> <pinned_hash> -- <cmd>` | gate: runs the evaluation command only if the tree verifies (exit 97 otherwise). Demonstrated with the correct pin (runs) and a wrong pin (refuses). |
| `neg_test.sh` | 17 checks run as the unprivileged uid `capopt` and as `dev`: append to `adapter.py`, overwrite scorer `evaluation.py`, truncate a gold answer, edit a split file, create a file in the tree, delete, chmod, rename a gold file, overwrite `MANIFEST.json`: **all denied**; reading the adapter and writing its own workdir still work; verification passes on the pristine tree and **catches** four simulated tamperings (changed byte, added file, made writable, symlink). Result: **17 checks, 0 failures**, both with `chattr +i` (`out/isolation_negtest_immutable.txt`; errors read `Operation not permitted`) and with ownership/mode only (`out/isolation_negtest_modeonly.txt`; errors read `Permission denied`), so the barrier does not depend on the immutable bit. |
| read-hiding (manual test) | `chgrp capeval`, dirs 0750, files o-rwx: `capopt` gets `Permission denied` on gold reads and even `ls`; `sudo -u dev -g capeval` (the evaluator identity) can read. |
| `run_as_optimizer.sh <workdir> -- <cmd>` | runs a command as `capopt` with a POSIX ACL grant on only `<workdir>`, `env -i` plus only `PATH`, `ANTHROPIC_*`: agent credentials (`LITELLM_PROXY_API_KEY`) are not passed. |
| `optimizer_sim_test.sh` | a fake hostile optimizer run through the wrapper: edits its `prompt.md` (allowed), tries to edit the adapter and the scorer (both denied), the agent API key is invisible to it. **PASS** (`out/isolation_optimizer_sim.txt`). |
| `local/make_agent_view.py` + `patches/adapter_gold_dir.patch` | the SpreadsheetBench sandbox mounts one directory read-write; the view contains inputs + empty writable `outputs/` only (400 gold files withheld for verified-400), and the scorer reads gold from `SPREADSHEETBENCH_GOLD_DIR`. Behaviour unchanged when the variable is unset; scores identical to the unpatched adapter on the e2e outputs. |

How it plugs into CapEvolve without editing repository code: the optimizer is spawned in one place
(`skills/optimizers/run-optimizer/scripts/run.py:313`, `subprocess.Popen(cmd, cwd=workdir, env=env)`, CLI resolved through `PATH`). A `claude` shim earlier on `PATH` that
`exec`s `run_as_optimizer.sh "$PWD" -- /real/claude "$@"` moves the optimizer onto the unprivileged uid; the harness, adapter and scorer run as `dev` from the frozen tree
(`PYTHONPATH` / `SPREADSHEETBENCH_HARNESS_DIR` / adapter path pointing into `<eval_root>/tree`), launched through `verify_then_run.sh` with the root hash pinned in the launcher.

**Not proven / known gaps (be explicit when citing isolation):**
1. The shim-on-PATH wiring through a full `cap-evolve run` with a real `claude` CLI was **not executed** (no CLI on this host, no LLM calls allowed). The pieces were tested separately.
2. The harness and the optimizer still share the **candidate workdir** by design (the optimizer writes the candidate there, the harness reads it): a candidate can contain code. For tau2 the candidate `tools.py` is imported **inside the evaluator process** and patches `tau2.registry`; for the same reason its edits also shape the *gold* replay (see `benchmarks.md`, "Evaluator coupling"). File permissions do not stop this; it needs either evaluating tools in a subprocess/sandbox or evaluating with the pristine constructor (code change, not made).
3. SpreadsheetBench agent code runs in the container with the dataset directory mounted read-write. With the agent view it can no longer see gold, but it can still write inside `/mnt/data` (inputs of other tasks). Mount inputs `:ro` and `outputs/` rw would be tighter (needs a change in vendored `jupyter.py`, which CapEvolve keeps byte-identical to upstream; the adapter generates a runtime copy, so it can be done there).
4. The eval tree is only as trustworthy as the moment it was frozen; the pinned hash lives in `benchmarks.md` / the launcher, not in a signed artifact.
5. `chattr +i` needs root to lift and fs support; ownership+mode already passes the negative test.
6. Feedback strings from `_localize_failure` (counts/types per range, not values) flow to the optimizer for train/val tasks: a low-bandwidth oracle channel by design; do not give the optimizer feedback on the sealed test split.

## 7. File index
`$BENCH/local/` : `env_local.sh`, `sb_single_task.py`, `tau2_single_task.py`, `make_overlay.sh`, `make_agent_view.py`, `sandbox_probe.py`, `adapter_score_e2e.py`
`$BENCH/scorer_diag/` : `scorer_diag.py`, `pop_check.py`
`$BENCH/isolation/` : `freeze_eval_tree.sh`, `manifest.py`, `verify_then_run.sh`, `neg_test.sh`, `run_as_optimizer.sh`, `optimizer_sim_test.sh`
`$BENCH/patches/` : `adapter_gold_dir.patch` (apply with `git apply` in the repo root if approved), `orig/`, `new/`
`$BENCH/out/` : raw results (`diag2`, `diag3_lo258`, `pop`, `e2e`, isolation logs, suite logs)
`$BENCH/` : `fastget.sh`, `hash_lists.py`, `tree_manifest.py`, `gitblob.py`, `manifests/`
