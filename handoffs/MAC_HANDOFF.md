# Handoff — running the 7 CCC-blocked SkillsBench tasks on Mac

**Goal:** run cap-evolve on the 7 SkillsBench tasks that our CCC LSF+rootless-podman setup could not execute, so we can complete the full-87-benchmark scoreboard.

**Where you're starting:** a fresh Mac with (I assume) Docker Desktop OR you're willing to install it. You'll be talking to Claude Code inside this handoff — paste this whole file into your first message so it has the full picture.

---

## The 7 tasks and why CCC failed each

| # | task | category | why CCC failed | why Mac should work |
|---|---|---|---|---|
| 1 | `earthquake-phase-association` | natural-science / seismology | `python:3.12-slim` Docker build fails: `ModuleNotFoundError: pkg_resources` when `pip install seisbench==0.10.2`. CCC's rootless-podman can't complete the wheel-install chain. | Docker Desktop's rootful daemon completes pip installs cleanly. |
| 2 | `fix-build-google-auto` | software-engineering / build-repair (BugSwarm) | Docker BUILD step aborts inside CCC rootless-podman: `setgroups/setegid/seteuid ... Operation not permitted` + `Method http has died unexpectedly`. The base image is `bugswarm/cached-images:...` (linux/amd64 only) which needs privileged apt-get inside a rootful daemon. | Docker Desktop is rootful; `--platform=linux/amd64` runs via Rosetta 2 on Apple Silicon. |
| 3 | `fix-visual-stability` | software-engineering / performance-optimization (Playwright) | The task's own `docker-compose.yml` has a genuine config bug: `service main declares mutually exclusive network_mode and networks: invalid compose project`. Not a rootless issue — the compose file itself is broken. | You'll need to patch the compose file (see per-task section) before it works anywhere. |
| 4 | `glm-lake-mendota` | natural-science / hydrology | `ubuntu:20.04` + `libnetcdf15` apt install fails inside CCC rootless-podman. `--platform=linux/amd64` was already declared. | Docker Desktop handles apt-get cleanly; amd64 via Rosetta 2. |
| 5 | `suricata-custom-exfil` | cybersecurity / intrusion-detection | Base `jasonish/suricata:7.0.11` uses `dnf` (Fedora-based). CCC's rootless-podman fails on `dnf -y install python3 python3-pip jq ...` — same setgroups issue. Also downloads a large Node.js runtime. | Docker Desktop rootful — dnf works. Large image (~2GB) but downloads once. |
| 6 | `seismic-phase-picking` | natural-science / seismology | The Dockerfile builds, but the task runs to reward=0.0 across seed+all candidates. Likely cause: at inference time the agent needs to download a PhaseNet model from HuggingFace, and something about CCC's outbound network or the container's local model cache prevents it. Not strictly "infra-broken" — the run completed, just at 0.0. | Home internet is likely more permissive; HuggingFace model download should succeed. If it still scores 0.0 on Mac, task is genuinely hard, not infra-blocked. |
| 7 | `offer-letter-generator` | office-white-collar / document-editing | NOT actually infra-broken. The task had valid results in an earlier c1 run but the v5 rerun's data got lost (all cells recorded as null in results.json). Just needs a fresh run to get recorded numbers. | Small, standard `ubuntu:24.04` + `python-docx` image — will just work. |

---

## Step 0 — one-time Mac setup

Ask Claude Code (on your Mac) to do these in order:

```bash
# 1. Install Docker Desktop (if not already):
#    Download from https://www.docker.com/products/docker-desktop/
#    Then launch it once so the daemon starts.

# 2. Install Homebrew if not present:
which brew || /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 3. Install prerequisites:
brew install python@3.12 git uv

# 4. If on Apple Silicon (M1/M2/M3/M4), enable Rosetta for amd64 emulation:
softwareupdate --install-rosetta --agree-to-license

# 5. Verify Docker is rootful and can run linux/amd64:
docker info | grep -i rootless   # should say "false" or nothing
docker run --rm --platform=linux/amd64 hello-world  # should succeed
```

---

## Step 1 — clone the repo and create an isolated worktree

The current work lives in a git repo shared on CCC. Your Mac needs its own copy.

```bash
# 1. Clone the primary repo (skillberry_ai). Ask Boaz for the SSH URL or use HTTPS.
#    The repo already has cap-evolve + skillsbench vendored as submodules or subtrees.
mkdir -p ~/workarea && cd ~/workarea
git clone --recurse-submodules <REPO_URL> skillberry_ai
cd skillberry_ai

# 2. Create an isolated worktree for this run.
#    We branch from origin/main (matches what CCC's c3 branched from).
git worktree add -b mac_intake_skillbench cap-evolve-worktrees/mac_intake_skillbench origin/main

# 3. Enter the worktree — everything from here on is done inside it.
cd cap-evolve-worktrees/mac_intake_skillbench

# 4. Set up the Python venv for cap-evolve
uv venv .venv
source .venv/bin/activate
uv pip install -e ../../cap-evolve  # or path to the cap-evolve package
uv pip install -e ../../cap-evolve-benchmarks  # if it's a separate package

# 5. Copy essentials from a reference worktree (Boaz will scp / send these):
#    - .env (contains ANTHROPIC_API_KEY / bearer token — NEVER commit)
#    - .capevolve/project_<task>/ dirs for each of the 7 tasks (yaml + seed_capability/)
#    Boaz: to package these from CCC, run:
#      cd /dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-worktrees/intake_skillbench_c3
#      tar czf /tmp/mac_intake_essentials.tar.gz \
#          .env \
#          .capevolve/project_earthquake-phase-association \
#          .capevolve/project_fix-build-google-auto \
#          .capevolve/project_fix-visual-stability \
#          .capevolve/project_glm-lake-mendota \
#          .capevolve/project_suricata-custom-exfil \
#          .capevolve/project_seismic-phase-picking \
#          .capevolve/project_offer-letter-generator
#    Then scp mac_intake_essentials.tar.gz to your Mac and extract at the worktree root.

# 6. Sanity check .env has real credentials:
grep -E "^ANTHROPIC" .env  # should show a key/token, redacted
```

---

## Step 2 — how cap-evolve is invoked (the general pattern)

Every task runs with the same shape — one `cap-evolve run` command per task, dedicated Docker container.

```bash
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)  # load ANTHROPIC creds

cap-evolve run \
  --spec   .capevolve/project_<TASK>/capevolve.<TASK>.yaml \
  --project .capevolve/project_<TASK> \
  --run-ts task_<TASK>_mac_v1 \
  --max-iterations 4

# Results land at:
#   .capevolve/run_task_<TASK>_mac_v1/
#     ├── state.json          (spent iterations, best_id, budget)
#     ├── final.json          (test.reward = final holdout number)
#     ├── events.jsonl        (per-candidate val evals, accepts/rejects)
#     ├── bench_jobs/         (per-candidate trial rollouts + rewards)
#     ├── candidates/cand_XXXX/  (the skill package cap-evolve proposed)
#     └── report.md
```

**Budget guidance (per task):**
- ~1–3 hours wall time (single container, single machine).
- ~$5–$15 in Anthropic API usage per task (Opus 4.8 optimizer + Sonnet 5 agent).
- 4 iterations × up to 10 trials/candidate. Kill early if you see val=1.0 (memory rule: "kill on ceiling reached").

**Run tasks ONE AT A TIME on a single Mac** — Docker Desktop shares a rootful daemon, so parallel podman-style graphroot corruption isn't an issue, but disk I/O and Anthropic rate limits make sequential the sensible default.

**When to kill early:**
- `val=1.0` reached at any candidate → kill (`Ctrl+C`, or `docker kill`). No room to improve.
- Baseline saturated `val=1.0` at seed → kill; optimizer has nothing to work with.
- 90+ minutes with no new events in `events.jsonl` → suspect hang; investigate.

---

## Step 3 — per-task runbook

Do them in the order below (easiest → hardest). Move on when one succeeds or you kill it as unfixable.

### 3.1 offer-letter-generator (start here — smoke test)

**Why first:** Docker image is trivially clean (`ubuntu:24.04` + `python-docx`). If this works, your Mac setup is fine. If it doesn't, fix Mac before continuing.

```bash
cap-evolve run \
  --spec   .capevolve/project_offer-letter-generator/capevolve.offer-letter-generator.yaml \
  --project .capevolve/project_offer-letter-generator \
  --run-ts task_offer-letter-generator_mac_v1 \
  --max-iterations 4
```

**Expected:** seed likely 0.5–0.9 (it's a docx-substitution task); cand should push to 1.0. ETA 1–2h.

### 3.2 glm-lake-mendota

**Pre-flight:** the Dockerfile declares `--platform=linux/amd64`. On Apple Silicon this triggers Rosetta 2 emulation.

```bash
cap-evolve run \
  --spec   .capevolve/project_glm-lake-mendota/capevolve.glm-lake-mendota.yaml \
  --project .capevolve/project_glm-lake-mendota \
  --run-ts task_glm-lake-mendota_mac_v1 \
  --max-iterations 4
```

**Watch for:** first-iteration seed evaluation should show a NON-zero reward. If seed=0.0 with an error about `libnetcdf` or `glm` binary, the amd64 emulation isn't running the GLM Fortran binary correctly. Try `docker run --platform=linux/amd64 -it <IMG> /usr/local/bin/glm --help` to smoke-test.

### 3.3 earthquake-phase-association

**Pre-flight:** if you hit the same `pkg_resources` build error we saw on CCC, add this to the Dockerfile RUN before the pip install (Boaz has a patched version; ask):
```
RUN pip install --upgrade pip setuptools wheel
```

```bash
cap-evolve run \
  --spec   .capevolve/project_earthquake-phase-association/capevolve.earthquake-phase-association.yaml \
  --project .capevolve/project_earthquake-phase-association \
  --run-ts task_earthquake-phase-association_mac_v1 \
  --max-iterations 4
```

**ETA:** 2–3h (first build downloads seisbench + PhaseNet model, ~1GB).

### 3.4 seismic-phase-picking

Same seisbench stack as 3.3 — if 3.3 built cleanly this will too.

```bash
cap-evolve run \
  --spec   .capevolve/project_seismic-phase-picking/capevolve.seismic-phase-picking.yaml \
  --project .capevolve/project_seismic-phase-picking \
  --run-ts task_seismic-phase-picking_mac_v1 \
  --max-iterations 4
```

**Watch for:** if you see `HTTPError: 429` or `ConnectionError` on the HuggingFace model download during seed evaluation, that's the CCC-observed issue reproducing. Try `HF_HUB_OFFLINE=0` and ensure Docker Desktop → Settings → Resources → Network isn't behind a corporate proxy. If still failing, pre-pull the model:
```
docker exec <container_id> python -c "import seisbench.models as sbm; sbm.PhaseNet.from_pretrained('original')"
```

### 3.5 suricata-custom-exfil

**Pre-flight:** the base image is `jasonish/suricata:7.0.11` (RHEL/Fedora-based) — ~1.5GB pull. The build also downloads Node.js v22 from `nodejs.org` (~50MB). Ensure Docker Desktop has enough disk (Settings → Resources → Disk image size: at least 60GB).

```bash
cap-evolve run \
  --spec   .capevolve/project_suricata-custom-exfil/capevolve.suricata-custom-exfil.yaml \
  --project .capevolve/project_suricata-custom-exfil \
  --run-ts task_suricata-custom-exfil_mac_v1 \
  --max-iterations 4
```

**ETA:** longest of the batch (3–5h). Seed evaluation takes ~25 min (Suricata rules setup is slow).

### 3.6 fix-build-google-auto

**Pre-flight:** BugSwarm base image is `bugswarm/cached-images:google-auto-101506036` (~3GB, linux/amd64 only). Rosetta 2 required on Apple Silicon.

```bash
cap-evolve run \
  --spec   .capevolve/project_fix-build-google-auto/capevolve.fix-build-google-auto.yaml \
  --project .capevolve/project_fix-build-google-auto \
  --run-ts task_fix-build-google-auto_mac_v1 \
  --max-iterations 4
```

**Watch for:** the container needs to run Maven builds inside. Java + Maven inside amd64-emulated container will be VERY SLOW (5-10× slower than native). Budget 4–6h. If seed evaluation takes >60 min per trial and rewards are 0.0, add `--platform=linux/amd64` to Docker Desktop's default platform in preferences and increase container memory (Settings → Resources → Memory: 8GB+, CPUs: 6+).

### 3.7 fix-visual-stability (LAST — needs a patch)

**This task's compose file has a config bug** (declared `network_mode` AND `networks:` in the same service). Before running cap-evolve, patch it:

```bash
# Locate the compose file
COMPOSE=vendor/skillsbench/tasks/fix-visual-stability/environment/docker-compose.yml
# Show it
cat $COMPOSE
# Ask Claude Code to remove EITHER the `network_mode:` line OR the `networks:` block from the `main` service — keep whichever is actually needed (usually keep `networks:` and drop `network_mode`).
```

After patching:
```bash
cap-evolve run \
  --spec   .capevolve/project_fix-visual-stability/capevolve.fix-visual-stability.yaml \
  --project .capevolve/project_fix-visual-stability \
  --run-ts task_fix-visual-stability_mac_v1 \
  --max-iterations 4
```

**Additional pre-flight:** the task uses Playwright + Chromium. First run downloads ~150MB of browser binaries. Test with `docker run --rm <IMG> node -e "require('playwright').chromium.launch().then(b=>b.close())"` before the full cap-evolve run.

---

## Step 4 — collect results back to CCC

After each successful run, sync the run dir + final.json back so the master `task-by-task-87/` scoreboard can be updated:

```bash
# On Mac, tar up the results for one task:
TASK=<taskname>
tar czf ~/${TASK}_mac_v1_results.tar.gz \
  .capevolve/run_task_${TASK}_mac_v1/final.json \
  .capevolve/run_task_${TASK}_mac_v1/state.json \
  .capevolve/run_task_${TASK}_mac_v1/events.jsonl \
  .capevolve/run_task_${TASK}_mac_v1/report.md \
  .capevolve/run_task_${TASK}_mac_v1/candidates

# Send to Boaz (email/Slack/scp), and he'll re-run the task-by-task-87 aggregation.
```

Or, if you have git push access from your Mac:
```bash
git add .capevolve/run_task_*_mac_v1/final.json .capevolve/run_task_*_mac_v1/state.json .capevolve/run_task_*_mac_v1/events.jsonl
git commit -m "Mac runs: 7 CCC-blocked tasks (final/state/events only)"
git push origin mac_intake_skillbench
# Then Boaz pulls the branch on CCC and aggregates.
```

---

## Success criteria per task

For the run to count as "cap-evolve delivered a signal," the run must:

1. Complete `final.json` — cap-evolve reached the FINAL test eval.
2. Have at least seed val recorded ≠ 0.0 OR at least one candidate with val > 0.0 (otherwise the run is infra-broken on Mac too, or the task is genuinely 0-signal).
3. NOT show `tool_calls: []` in every rollout — that's the signature of the container never starting.

If a run finishes with `best=0.0` and no rollout has `tool_calls>0`, the container never started and the task is still blocked. Save the log and share; may need a different image.

---

## Standing rules (from Boaz's playbook)

- **Never** push to public git remotes without explicit approval. `.env` is gitignored — don't commit it.
- **Kill on saturated baseline**: if seed val=1.0 with stderr=0.0, kill the job. No room for the optimizer.
- **Kill on val=1.0 at any candidate**: same reasoning. Preserve the run dir with a `_KILLED_ceiling_reached_1.0` suffix so it's obvious in the scoreboard.
- **Kill on >90 min stall**: if `events.jsonl` hasn't grown in 90 min and no new bench_jobs subdirs, investigate — probably a container hang.
- **One task at a time on Mac.** Sequential.
- **Anthropic budget:** you have ANTHROPIC creds in `.env`. Each task ~$5–$15. Full batch ~$50–$100. Stop and confirm before continuing if any single task exceeds $20.

---

## Fast lookup — task IDs, paths, and expected times

| task | expected wall time | cost estimate | disk needed |
|---|---|---|---|
| `offer-letter-generator` | 1–2h | $5 | negligible |
| `glm-lake-mendota` | 2–3h (amd64 emul) | $8 | ~2GB image |
| `earthquake-phase-association` | 2–3h | $10 | ~3GB (seisbench+model) |
| `seismic-phase-picking` | 2–3h | $10 | shares seisbench image |
| `suricata-custom-exfil` | 3–5h | $15 | ~3GB |
| `fix-build-google-auto` | 4–6h (amd64 emul + Maven) | $15 | ~6GB (BugSwarm base) |
| `fix-visual-stability` | 2–3h (after compose patch) | $10 | ~2GB (Playwright/Chromium) |
| **Total (sequential)** | **~20h** | **~$75** | **~20GB peak** |

---

## Contact

If anything is missing or wrong, ask Boaz — he has the full context on CCC + cap-evolve.

Files referenced:
- Master scoreboard: `third_party/skillbench/results/results.json`
- Interactive heatmap: `third_party/skillbench/results/heatmap.html`
- EvoSkill comparison: `third_party/skillbench/results/evoskill_comparison_chart.html`
