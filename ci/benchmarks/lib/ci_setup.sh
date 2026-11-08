#!/usr/bin/env bash
# ci_setup.sh — idempotently prepare the self-hosted runner for ONE benchmark.
# Creates a cached py3.12 venv + benchmark deps/clones OUTSIDE the checkout (so they
# survive between jobs), ensures the claude-code optimizer CLI is installed, preflights the
# model gateway (fail fast when the SELECTED models are not entitled, or the gateway is over
# budget, rather than score all-0.000), and exports CAPEVOLVE_PY / SKILLSBENCH_SRC / PATH to
# $GITHUB_ENV.
#
#   ci_setup.sh <bench>
set -euo pipefail
BENCH="${1:?bench}"
CACHE="${CAPEVOLVE_CI_CACHE:-$HOME/.cache/capevolve-ci}"
# The tau2_sierra legs get their OWN venv: they install tau2 pinned at the example's
# TAU2_REFERENCE_SHA, while the plain `tau2` leg installs an unpinned clone into the shared venv.
# Same package name, two commits.
case "$BENCH" in
  tau2_sierra|tau2_sierra_blackbox) VENV="$CACHE/venv-tau2-sierra" ;;
  # AppWorld 42b5bcf is verified on Python 3.11 (benchmarks/appworld/examples/react_agent/README.md, Setup), so it gets
  # its own venv, inside its own $AW_EVAL so the example's scripts find it where they expect it.
  appworld)                         VENV="$CACHE/appworld/venv-aw" ;;
  *)                                VENV="$CACHE/venv" ;;
esac
CAPEVOLVE_PY="$VENV/bin/python"
IDX="--index-url https://pypi.org/simple"
mkdir -p "$CACHE"

command -v uv >/dev/null || { echo "::error:: uv is required on the runner"; exit 1; }
VENV_PY_VERSION=3.12; [ "$BENCH" = appworld ] && VENV_PY_VERSION=3.11
[ -x "$CAPEVOLVE_PY" ] || uv venv --python "$VENV_PY_VERSION" "$VENV"

LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$LIB_DIR/../../.." && pwd)"
uv pip install -p "$CAPEVOLVE_PY" -q $IDX "$REPO/core" litellm

case "$BENCH" in
  swebench)
    # Harbor is the ONLY swebench adapter. It runs a real coding agent (claude-code) inside
    # its own sandboxed containers and manages its own dataset, so none of the removed litellm
    # path's machinery is needed: no HuggingFace dataset, no oracle context, no
    # swebench/sweb.eval.* images, no per-instance patch application.
    #
    # Why: the curated tiers' task ids are SWE-bench_Verified, but oracle code context exists
    # only for Lite (46 of full's 250 had it), and single-shot blind patching is not a
    # meaningful target for a mid-tier model. Harbor's agent explores the repo itself.
    # The adapter does `from capevolve_harbor import ...`; that package lives in this repo
    # and was never installed into the CI venv, so the harbor path would have died on
    # import. Install it explicitly.
    uv pip install -p "$CAPEVOLVE_PY" -q $IDX "$REPO/capevolve_harbor"
    "$CAPEVOLVE_PY" -c "import capevolve_harbor; print('capevolve_harbor OK')"
    command -v harbor >/dev/null 2>&1 || uv tool install $IDX harbor >/dev/null 2>&1 || true
    command -v harbor >/dev/null || {
      echo "::error:: harbor CLI unavailable — the harbor adapter cannot run a single task."
      exit 1; }
    echo "harbor: $(command -v harbor)"
    command -v docker >/dev/null && docker info >/dev/null 2>&1 || {
      echo "::error:: docker daemon not reachable — harbor runs every task in a container"
      exit 1; }
    # Pre-warm an npm cache for the in-container agent bootstrap.
    #
    # Harbor's claude-code agent starts every task container with
    #   npm install -g @anthropic-ai/claude-code
    # so a 50-task pass is 50 registry installs and a 250-task pass is 250. That was the
    # dominant failure mode in pilot run 31274531220: of 34 infra-errored tasks, the npm line
    # produced exit 126, exit 128 and NetworkConnectionError, and 8 more rollouts died as
    # CancelledError while waiting on it.
    #
    # Populate the cache ONCE here on the host; the adapter bind-mounts this directory into
    # every container and sets npm_config_cache + npm_config_prefer_offline. prefer-offline
    # (not offline) means a cache miss still falls back to the network, so a stale or empty
    # cache degrades to the old behaviour instead of breaking the run.
    #
    # Lives under $CACHE, which is outside the checkout and survives between jobs, so a
    # freshly provisioned runner warms it on its first benchmark and reuses it thereafter.
    if command -v npm >/dev/null 2>&1; then
      NPM_CACHE_DIR="$CACHE/npm-cache"
      mkdir -p "$NPM_CACHE_DIR"
      if npm cache add @anthropic-ai/claude-code --cache "$NPM_CACHE_DIR" >/dev/null 2>&1; then
        # World-readable: the container's npm may run as a different uid than the host user
        # that warmed the cache, and a bind mount preserves host ownership. Verified locally
        # that `npm install -g @anthropic-ai/claude-code --offline --cache <dir>` resolves
        # entirely from this cache (420ms, no network), so readability is the only barrier.
        chmod -R a+rX "$NPM_CACHE_DIR" 2>/dev/null || true
        echo "npm cache warmed for @anthropic-ai/claude-code: $NPM_CACHE_DIR ($(du -sh "$NPM_CACHE_DIR" 2>/dev/null | cut -f1))"
        export HARBOR_NPM_CACHE="$NPM_CACHE_DIR"
      else
        # Non-fatal: without the cache the agent bootstraps from the network as before.
        echo "::warning:: could not warm the npm cache — containers will install"
        echo "::warning:: @anthropic-ai/claude-code from the registry individually."
      fi
    else
      echo "::warning:: npm not found — cannot pre-warm the agent bootstrap cache"
    fi

    # Reap stale harbor job directories. Harbor writes one per run (agent sessions,
    # trajectories, per-task artifacts, tens of MB each) and never removes them: 43 had piled
    # up for 622M on the ROOT filesystem, which is what tipped / to 100% full and made every
    # task in pilot run 31297290155 die at "importing to docker: failed to ingest". Anything
    # older than 6h cannot belong to a live run — the bench leg is serialized here.
    for _d in /tmp/harbor_jobs_* "$CACHE/harbor-jobs"/*; do
      [ -d "$_d" ] || continue
      if [ -z "$(find "$_d" -maxdepth 0 -mmin -360 2>/dev/null)" ]; then
        rm -rf "$_d" 2>/dev/null || true
      fi
    done
    echo "harbor job dirs after reap: $(ls -d /tmp/harbor_jobs_* "$CACHE/harbor-jobs"/* 2>/dev/null | wc -l | tr -d ' ')"

    # Disk preflight. A harbor task builds and imports a multi-GB image; with no room on the
    # filesystem docker stages through, the build succeeds and the IMPORT fails, so every task
    # infra-errors ~20 minutes in. Check up front instead.
    _root_avail_m=$(df --output=avail / 2>/dev/null | tail -1 | tr -d ' ')
    _root_avail_m=$(( ${_root_avail_m:-0} / 1024 ))
    echo "disk: / has ${_root_avail_m}MB available; docker data-root $(docker info --format '{{.DockerRootDir}}' 2>/dev/null) has $(df -h "$(docker info --format '{{.DockerRootDir}}' 2>/dev/null || echo /)" 2>/dev/null | tail -1 | awk '{print $4}')"
    # Two thresholds, because the exact staging requirement is not something I could measure:
    # docker's data-root is on a big volume, yet the observed 'failed to ingest' happened with
    # 169MB free on /, so SOMETHING in the build->import path needs room there. Hard-fail only
    # where it is unambiguous, warn in the band where it is a judgement call, so this guard
    # cannot block a run that would have worked.
    if [ "$_root_avail_m" -lt 1024 ]; then
      echo "::error:: only ${_root_avail_m}MB free on / — harbor image imports fail with"
      echo "::error::   #10 importing to docker"
      echo "::error::   #10 ERROR: failed to ingest \"blobs/sha256/...\""
      echo "::error:: partway through, after burning the agent budget for every task."
      echo "::error::"
      echo "::error:: Cause on skillberry-1 (measured 2026-08-09): this docker uses the"
      echo "::error:: CONTAINERD IMAGE STORE, so images live in /var/lib/containerd on / no"
      echo "::error:: matter what data-root says — 235GB there (162GB overlayfs snapshots +"
      echo "::error:: 73GB content blobs) while docker info reported data-root=/vol/docker."
      echo "::error:: /var/lib/docker was EMPTY; do not go looking there."
      echo "::error::"
      echo "::error:: Fix — ordinary docker maintenance, no rm -rf required:"
      echo "::error::   docker system df                                  # confirm reclaimable"
      echo "::error::   docker image prune -a -f --filter until=72h       # reclaimed 145.8GB"
      echo "::error:: The until= filter keeps recently built task env images so the next run"
      echo "::error:: does not have to rebuild all of them."
      exit 1
    elif [ "$_root_avail_m" -lt 4096 ]; then
      echo "::warning:: only ${_root_avail_m}MB free on / — harbor image imports may fail with"
      echo "::warning:: 'failed to ingest'. Images live in /var/lib/containerd on this runner"
      echo "::warning:: (containerd image store, ignores data-root). Reclaim with:"
      echo "::warning::   docker image prune -a -f --filter until=72h"
    fi

    # Reap orphaned harbor task containers before starting. Harbor does NOT tear its
    # containers down when a workflow run is cancelled — 6 were found stranded 27-47 hours
    # after their runs ended, competing for CPU and memory with whatever ran next. The bench
    # leg is serialized on this single self-hosted runner, so any *__env-main container alive
    # at setup time can only be a leftover. (This replaces the sweb.eval.* reaper, which
    # became dead along with the litellm adapter.)
    hb_orphans=$(docker ps -aq --filter "name=env-main" 2>/dev/null | tr '\n' ' ')
    if [ -n "$(printf '%s' "$hb_orphans" | tr -d ' ')" ]; then
      # shellcheck disable=SC2086 -- intentional word splitting over container ids
      docker rm -f $hb_orphans >/dev/null 2>&1 || true
      echo "reaped $(printf '%s' "$hb_orphans" | wc -w | tr -d ' ') orphaned harbor container(s)"
    fi
    ;;
  appworld)
    # benchmarks/appworld/examples/react_agent/README.md "Setup", steps 1-2, into the cache ($AW_EVAL), which survives
    # between jobs: AppWorld at its pin with the example's header patch, its data, root_opt with
    # the lint cache, and the optimizer's reference docs. Each step is skipped when its output is
    # already there, so a warm runner pays only the checks.
    AW_EVAL="$CACHE/appworld"; export AW_EVAL
    AW_EX="$REPO/benchmarks/appworld/examples/react_agent"
    AW_PIN=42b5bcf
    command -v git-lfs >/dev/null || { echo "::error:: git-lfs is required on the runner (AppWorld ships LFS bundles)"; exit 1; }
    if [ ! -d "$AW_EVAL/appworld/.git" ]; then
      git clone -q https://github.com/StonyBrookNLP/appworld "$AW_EVAL/appworld" || { echo "::error:: could not clone AppWorld"; exit 1; }
    fi
    (
      cd "$AW_EVAL/appworld"
      [ "$(git rev-parse --short=7 HEAD)" = "$AW_PIN" ] || git checkout -q "$AW_PIN"
      git lfs pull
      # The patch is idempotent here: applied once, skipped when already in the tree.
      if ! git apply --reverse --check "$AW_EX/patches/appworld-extra-headers.patch" 2>/dev/null; then
        git apply "$AW_EX/patches/appworld-extra-headers.patch"
      fi
    ) || { echo "::error:: AppWorld checkout/patch failed"; exit 1; }
    uv pip install -p "$CAPEVOLVE_PY" -q $IDX -e "$AW_EVAL/appworld" -e "$AW_EVAL/appworld/experiments[simplified]" \
      "pydantic>=2.12,<2.13" "fastapi==0.135.0" "starlette>=0.48" -e "$REPO/core" \
      || { echo "::error:: pip install AppWorld failed"; exit 1; }
    # The unpacked apps mark a finished install (generate/tasks is tracked in git, so it is not).
    # It resolves the bundles relative to the cwd, so it runs from the checkout.
    [ -d "$AW_EVAL/appworld/src/appworld/apps/admin" ] \
      || (cd "$AW_EVAL/appworld" && "$VENV/bin/appworld" install --repo >/dev/null) \
      || { echo "::error:: appworld install --repo failed"; exit 1; }
    [ -f "$AW_EVAL/root_full/data/datasets/test_normal.txt" ] \
      || "$VENV/bin/appworld" download data --root "$AW_EVAL/root_full" >/dev/null
    [ -f "$AW_EVAL/lint_cache.json" ] || "$CAPEVOLVE_PY" "$AW_EX/scripts/make_roots.py"
    [ -f "$AW_EVAL/reference/api_index.md" ] || "$CAPEVOLVE_PY" "$AW_EX/scripts/make_reference.py" "$AW_EVAL/reference"
    # No model call: the agent is built and its first request compared with stock (A4).
    APPWORLD_ROOT="$AW_EVAL/root_opt" "$CAPEVOLVE_PY" "$AW_EX/scripts/check_injection.py" "$AW_EX/seed_capability" \
      | tail -1 | grep -q "A4 PASS" || { echo "::error:: AppWorld injection check (A4) failed"; exit 1; }
    echo "appworld ready at $AW_EVAL" ;;
  tau2)
    [ -d "$CACHE/tau2-bench/.git" ] || git clone --depth 1 https://github.com/sierra-research/tau2-bench "$CACHE/tau2-bench"
    uv pip install -p "$CAPEVOLVE_PY" -q $IDX -e "$CACHE/tau2-bench" ;;
  tau2_sierra|tau2_sierra_blackbox)
    # The two DELIVERY ARMS (direct / blackbox) of benchmarks/tau2/examples/sierra_airline, on vanilla
    # sierra-research tau2 — a DIFFERENT checkout from the unpinned `tau2` leg above. The commit is
    # the one the example's adapters and tailoring were created from (TAU2_REFERENCE_SHA in each
    # arm's setup.sh): CI reads it from there, keeps no copy of its own and has no override, so
    # a CI number and a local `bash benchmarks/tau2/examples/sierra_airline/<arm>/run.sh` number run the
    # same benchmark code. ONE checkout for both arms keeps direct-vs-blackbox comparable.
    EX="$REPO/benchmarks/tau2/examples/sierra_airline"
    ref_of() { sed -n 's/^TAU2_REFERENCE_SHA="\([0-9a-f]\{40\}\)"$/\1/p' "$EX/$1/setup.sh"; }
    REF_DIRECT="$(ref_of direct)"; REF_BLACKBOX="$(ref_of blackbox)"
    [ -n "$REF_DIRECT" ] || { echo "::error:: no 40-hex TAU2_REFERENCE_SHA in $EX/direct/setup.sh"; exit 1; }
    [ "$REF_DIRECT" = "$REF_BLACKBOX" ] || {
      echo "::error:: TAU2_REFERENCE_SHA differs between the arms: direct $REF_DIRECT, blackbox ${REF_BLACKBOX:-<none>}"
      exit 1; }
    TAU2_REF="$REF_DIRECT"
    TAU2_DIR="$CACHE/tau2-sierra"
    if [ ! -d "$TAU2_DIR/.git" ]; then
      git clone -q https://github.com/sierra-research/tau2-bench "$TAU2_DIR" || {
        echo "::error:: could not clone sierra-research/tau2-bench (public; usually transient — re-run)"
        exit 1; }
    fi
    [ -z "$(git -C "$TAU2_DIR" status --porcelain)" ] \
      || { echo "::error:: $TAU2_DIR has local changes; delete it so it is re-cloned"; exit 1; }
    if [ "$(git -C "$TAU2_DIR" rev-parse HEAD)" != "$TAU2_REF" ]; then
      git -C "$TAU2_DIR" cat-file -e "$TAU2_REF^{commit}" 2>/dev/null \
        || git -C "$TAU2_DIR" fetch -q origin || { echo "::error:: git fetch in $TAU2_DIR failed"; exit 1; }
      git -C "$TAU2_DIR" checkout -q --detach "$TAU2_REF" \
        || { echo "::error:: cannot check out TAU2_REFERENCE_SHA $TAU2_REF in $TAU2_DIR"; exit 1; }
    fi
    [ "$(git -C "$TAU2_DIR" rev-parse HEAD)" = "$TAU2_REF" ] \
      || { echo "::error:: $TAU2_DIR is not at TAU2_REFERENCE_SHA $TAU2_REF"; exit 1; }
    echo "$TAU2_REF" > "$CACHE/tau2-sierra.COMMIT"
    # tau2 imports websockets unconditionally but declares it only in its `voice` extra.
    uv pip install -p "$CAPEVOLVE_PY" -q $IDX -e "$TAU2_DIR" "websockets>=13.0" \
      || { echo "::error:: pip install tau2-bench failed"; exit 1; }
    "$CAPEVOLVE_PY" -c "import tau2; print('tau2 (sierra) OK')"
    echo "tau2-bench @ $TAU2_REF (= TAU2_REFERENCE_SHA)"
    if [ "$BENCH" = "tau2_sierra_blackbox" ]; then
      # Put the stack's clones in the CACHE, not the checkout. blackbox_env defaults its vendor dir
      # to <repo>/vendor, and actions/checkout wipes untracked files in the workspace — so the
      # default would re-clone and re-install BOTH services on every single run (minutes each),
      # unlike every other cached dependency here. $CACHE survives between jobs.
      export SPA_VENDOR_DIR="$CACHE/spa-vendor"
      mkdir -p "$SPA_VENDOR_DIR"
      # PROVISION ONLY (clone + venv + install the Store and the Proxy-Agent), never start:
      # starting belongs to the run, as in the arm's own setup.sh. blackbox_env is the same module the
      # example uses, so CI and a local run provision an identical stack — including the log
      # rotation it patches into each clone, so nothing here needs to bound a log.
      ( cd "$REPO" && CAPEVOLVE_SKILLS_DIR="$REPO/skills" "$CAPEVOLVE_PY" - <<'PYEOF'
import json, sys
sys.path.insert(0, "skills/interventions/llm-proxies/blackbox/scripts")
import blackbox_env
print("  " + json.dumps(blackbox_env.provision()))
print(f"  store ref {blackbox_env.STORE_REF} @ {blackbox_env.store_dir()}")
print(f"  agent ref {blackbox_env.AGENT_REF[:7]} @ {blackbox_env.agent_dir()}")
PYEOF
      ) || { echo "::error:: Skillberry stack provisioning failed — the blackbox arm cannot run"; exit 1; }
    fi
    if [ -n "${GITHUB_ENV:-}" ]; then
      echo "TAU2_SIERRA_DIR=$TAU2_DIR" >> "$GITHUB_ENV"
      echo "TAU2_SIERRA_REF=$TAU2_REF" >> "$GITHUB_ENV"
      # MUST reach the "Run suite" step: blackbox_env recomputes its vendor dir from the environment
      # in that process too, and a run that disagreed with setup about where the stack lives
      # would re-provision from scratch mid-leg.
      if [ -n "${SPA_VENDOR_DIR:-}" ]; then echo "SPA_VENDOR_DIR=$SPA_VENDOR_DIR" >> "$GITHUB_ENV"; fi
    fi
    export TAU2_SIERRA_DIR="$TAU2_DIR" TAU2_SIERRA_REF="$TAU2_REF" ;;
  skillsbench)
    uv tool install $IDX benchflow >/dev/null 2>&1 || true
    [ -d "$CACHE/skillsbench-src/.git" ] || GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 https://github.com/benchflow-ai/skillsbench "$CACHE/skillsbench-src" ;;
  spreadsheetbench)
    uv pip install -p "$CAPEVOLVE_PY" -q $IDX pandas openpyxl docker tornado requests
    command -v docker >/dev/null && docker info >/dev/null 2>&1 || {
      echo "::error:: docker daemon not reachable — spreadsheetbench runs each task in its own container"; exit 1; }
    if ! command -v libreoffice >/dev/null 2>&1 && ! command -v soffice >/dev/null 2>&1; then
      echo "::warning:: LibreOffice not found — formula-only cells won't be recalculated before scoring"
    fi
    SB_VARIANT="sample_200"
    case "${TIER:-smoke}" in
      # pilot's tasks are drawn from full's train split, so it needs the 912-task dataset too.
      full|pilot) SB_VARIANT="full_912" ;;
      # full_verified evaluates the VERIFIED 400-task re-release, which is a different download
      # and a different on-disk layout — not a subset of the 912 archive (see fetch_data.sh).
      # Giving it full_912's data would silently score the old benchmark under the new tier's name.
      full_verified) SB_VARIANT="verified_400" ;;
    esac
    SPREADSHEETBENCH_DATA_DIR="$(SPREADSHEETBENCH_VARIANT="$SB_VARIANT" "$REPO/ci/benchmarks/spreadsheetbench/fetch_data.sh" "$CACHE/spreadsheetbench-data")" ;;
  rfe-creator)
    # Clones opendatahub-io/rfe-creator + opendatahub-io/agent-eval-harness (both public,
    # unlicensed — see run_suite.sh's rfe-creator arm) and merges this repo's own
    # reward_overlay.yaml onto the upstream eval config. pyyaml is needed both by this
    # merge and by rfe-creator's own scripts (invoked BY the Claude Code agent).
    uv pip install -p "$CAPEVOLVE_PY" -q $IDX pyyaml
    "$REPO/ci/benchmarks/rfe-creator/utils/fetch_data.sh" "$CACHE/rfe-creator-src" >&2
    uv pip install -p "$CAPEVOLVE_PY" -q $IDX -e "$CACHE/rfe-creator-src/agent-eval-harness"
    export RFE_CREATOR_SRC="$CACHE/rfe-creator-src" ;;
esac

"$CAPEVOLVE_PY" -c "import cap_evolve; print('cap_evolve OK')"

# Ensure the claude-code optimizer CLI (the EDIT PROPOSER) is present. If a runner is
# reprovisioned/rebooted the global npm install can vanish; without `claude` the benchmark
# SILENTLY degrades — the optimizer fails every iteration with `cli_present:false`, no edit
# is proposed, and every task reports best=seed / reward 0.000 as if it had "optimized".
# Install idempotently into a user-writable prefix ($HOME/.local/bin is already on PATH and
# exported below), then HARD-FAIL if it is still unavailable so a broken runner is loud.
if ! command -v claude >/dev/null 2>&1; then
  command -v npm >/dev/null || { echo "::error:: npm required to install the claude-code optimizer"; exit 1; }
  echo "claude CLI missing — installing @anthropic-ai/claude-code into $HOME/.local"
  npm install -g --prefix "$HOME/.local" @anthropic-ai/claude-code
fi
export PATH="$HOME/.local/bin:$PATH"
command -v claude >/dev/null || {
  echo "::error:: claude-code optimizer CLI still unavailable after install — aborting."
  echo "::error:: (running anyway would silently yield best=seed / reward 0.000 on every task.)"
  exit 1
}
echo "claude-code optimizer: $(command -v claude) ($(claude --version 2>/dev/null | head -1))"

# Gateway preflight — ENTITLEMENT first, then BUDGET. The agent AND the optimizer share one
# LiteLLM gateway, and both of these faults present identically: every rollout dies with
# INFRASTRUCTURE_ERROR and the suite reports a clean-looking 0.000 that is indistinguishable
# from a real regression. Detect both up front rather than burn hours and dollars.
#
# ENTITLEMENT is the one that actually bites. The model dropdowns in benchmarks.yml are a
# STATIC list; the gateway's per-team allowlist is not, so they drift apart. Run 31124146014
# selected `Azure/gpt-5-mini-2025-08-07` — in the dropdown, absent from the key's allowlist —
# and spent 11 minutes plus $2.56 of optimizer budget before assert_run.py noticed that all
# 5 tasks had infra-errored. 15 of that dropdown's 30 agent options were in the same state,
# including its own default `aws/gpt-oss-120b`.
#
# The previous probe could not have caught that: it asked about a HARDCODED
# `aws/gpt-oss-120b` instead of the models the run actually selected, and only hard-failed on
# HTTP 429 budget_exceeded — so a `team not allowed to access model` rejection printed
# "(not budget-blocked)" and sailed straight through.
# Two providers can be selected (see resolve_provider.sh): the ETE gateway, entitlement- and
# budget-checked below exactly as before, and RITS via skillberry-1's lite-rits proxy, which
# has neither concept — it's a single-tenant proxy scraping IBM RITS's own catalog, so there
# is no per-team allowlist to drift out of sync with the dropdown and no shared budget to
# exhaust. Its `/v1/models` is ALSO always empty by design (it builds routes dynamically per
# request instead of publishing a static model_list), so running check_models.py against it
# would be a guaranteed false failure, not a weaker check — skip straight to a completion
# probe, which is the only signal lite-rits can actually give.
#
# PROVIDER ORDER. A plain model name (see ci/benchmarks/model_catalog.txt) has a list of
# candidate CI ids, one per provider, tried in the catalog's order: RITS (no budget), then
# ibm-ete-int, then ibm-ete. The preflight below keeps the FIRST candidate that is listed and gets
# a 200 from a real completion (or a 400, which blames our probe, not the provider), and exports
# it as
# AGENT_MODEL_RESOLVED / OPTIMIZER_MODEL_RESOLVED so the whole run uses that one provider. A
# prefixed id pins its provider: one candidate, no fallback, and the same hard failures as
# before. The choice is made ONCE, here; a budget that runs out mid-run still fails that run.
if command -v curl >/dev/null; then
  PF_AGENT="${AGENT_MODEL:-gpt-oss-120b}"
  PF_OPTIMIZER="${OPTIMIZER_MODEL:-claude-opus-4-8}"
  # shellcheck source=ci/benchmarks/lib/resolve_provider.sh
  . "$LIB_DIR/resolve_provider.sh"

  # 1. ENTITLEMENT — is this candidate *gateway* model served to this key at all? Only
  # gateway-routed models are checkable this way; an "ibm-rits/*" model has no /models listing
  # to confirm against (lite-rits's /v1/models is always empty by design), so the caller skips
  # this for RITS and relies on the completion probe alone.
  # NB: check_models.py takes a pre-fetched /models JSON file plus --require ROLE=MODEL_ID
  # pairs (see check_models.py's own docstring); it has no --base/--key mode.
  # Returns 0 when listed (or when the listing itself is unavailable — that is a warning, as
  # before), 1 when NOT listed. A pinned id that is not listed aborts here with
  # check_models.py's full diagnosis, exactly as the old single-provider check did.
  check_listed() {
    local role="$1" provider="$2" model="$3" pinned="$4" base key
    case "$provider" in
      ibm-ete-int) base="$IBM_ETE_INT_API_BASE"; key="$IBM_ETE_INT_API_KEY" ;;
      ibm-ete)     base="$IBM_ETE_API_BASE";     key="$IBM_ETE_API_KEY" ;;
      *) return 0 ;;
    esac
    # /models is an `llm_api_routes` call. The richer /model/info and /key/info are NOT: these
    # virtual keys are route-scoped and answer both with 403 "not allowed to call this route",
    # which is also the real reason the old preflight logged a mystery HTTP 403.
    local models="/tmp/capevolve_models_${provider}.$$_${role}.json"
    local mcode
    mcode="$(curl -sS -m 30 -o "$models" -w '%{http_code}' \
      "$base/models" \
      -H "Authorization: Bearer $key" 2>/dev/null)" || true
    case "$mcode" in ''|*[!0-9]*) mcode=000 ;; esac
    if [ "$mcode" != "200" ]; then
      echo "::warning:: $provider /models returned HTTP $mcode — cannot verify $role model entitlement"
      rm -f "$models"; return 0
    fi
    # WIRE ids, not the CI aliases. The gateway's own `GET /models` listing spells models the
    # way it serves them, so requiring "ibm-ete-int/aws/claude-opus-5" made every ibm-ete*
    # model look unserved and aborted preflight (run 36300445911).
    if [ "$pinned" = 1 ]; then
      echo "::group::Entitlement check — $role on $provider"
      if ! "$CAPEVOLVE_PY" "$LIB_DIR/check_models.py" "$models" --require "$role=$(wire_model "$model")"; then
        rm -f "$models"; echo "::endgroup::"; exit 1
      fi
      echo "::endgroup::"
    elif ! "$CAPEVOLVE_PY" "$LIB_DIR/check_models.py" "$models" --require "$role=$(wire_model "$model")" >/dev/null 2>&1; then
      rm -f "$models"; return 1
    fi
    rm -f "$models"
    return 0
  }

  # 2. BUDGET/ENTITLEMENT at call time — one real completion per SELECTED model, against
  # whichever provider actually serves it. Listing a gateway model is necessary but not
  # sufficient (the team check happens at call time), and RITS has no listing step at all, so
  # this probe is the only check it gets.
  # `max_completion_tokens` (not `max_tokens`) is used because the Azure reasoning
  # deployments reject the latter outright, and a probe that 400s on its own parameters
  # would be a false alarm.
  probe_model() {
    local role="$1" model="$2"
    # Graceful skip, not a hard abort: resolve_provider's ibm-ete-int/ibm-ete branches each do a
    # hard `:?` on their own IBM_<NAME>_API_BASE/IBM_<NAME>_API_KEY, which would otherwise kill
    # this WHOLE script (set -uo pipefail; no outer `if` catches a `:?` failure) for a run that
    # never asked for that gateway at all — e.g. a local/laptop run of an ibm-rits-only
    # dispatch, or one with the other role on a different provider and this role's gateway
    # secrets simply not exported. Before this check existed, the only gate was
    # `[ -n "${ANTHROPIC_BASE_URL:-}" ] && ... && command -v curl` around the ENTIRE preflight
    # block above; narrowing that to `command -v curl` (so RITS-only dispatches still get
    # probed) reintroduced exactly the failure mode it used to prevent for the gateway case.
    case "$model" in
      ibm-ete-int/*)
        if [ -z "${IBM_ETE_INT_API_BASE:-}" ] || [ -z "${IBM_ETE_INT_API_KEY:-}" ]; then
          echo "::warning:: IBM_ETE_INT_API_BASE/IBM_ETE_INT_API_KEY not set — skipping $role model preflight probe for '$model'"
          return 0
        fi
        ;;
      ibm-ete/*)
        if [ -z "${IBM_ETE_API_BASE:-}" ] || [ -z "${IBM_ETE_API_KEY:-}" ]; then
          echo "::warning:: IBM_ETE_API_BASE/IBM_ETE_API_KEY not set — skipping $role model preflight probe for '$model'"
          return 0
        fi
        ;;
      ibm-rits/*)
        if [ -z "${IBM_RITS_API_BASE:-}" ] || [ -z "${IBM_RITS_API_KEY:-}" ]; then
          echo "::warning:: IBM_RITS_API_BASE/IBM_RITS_API_KEY not set — skipping $role model preflight probe for '$model'"
          return 0
        fi
        ;;
    esac
    resolve_provider "$model"
    local probe="/tmp/capevolve_budget_probe.$$_${role}.json"
    # RETRY, but only what is plausibly TRANSIENT. A single `curl -m 60` killed two whole
    # dispatches before any work started (runs 36259218074 and 36297602993, both dying at
    # exactly 60s with HTTP 000) while the endpoint was in fact healthy: /health and /v1/models
    # answered 200 minutes later and a real completion answered 200 in 1s one day and 200 in 6s
    # another. An endpoint whose own good answers vary 6x cannot be judged by one shot.
    #
    # The budget is bounded so the WORST case never exceeds the old single-attempt 60s: each
    # attempt gets 25s, backoff is 5s then 15s, and the loop refuses an attempt that could not
    # finish inside probe_deadline. Three instant failures therefore cost ~20s (the backoffs)
    # and three hung ones stop at two attempts rather than spending 95s. A healthy endpoint
    # answers on attempt 1 and pays nothing, which is the normal case.
    local probe_attempts="${CAPEVOLVE_PROBE_ATTEMPTS:-3}"
    local probe_timeout="${CAPEVOLVE_PROBE_TIMEOUT:-25}"
    local probe_deadline=60
    # shellcheck disable=SC2206  # deliberate word split: "5 15" -> per-attempt backoffs
    local backoffs=( ${CAPEVOLVE_PROBE_BACKOFFS:-5 15} )
    local started_at code attempt=1 backoff_s elapsed
    started_at="$(date +%s)"
    while :; do
      # NB: curl's own `-w '%{http_code}'` already prints 000 on a connect failure/timeout, so
      # the old `|| echo 000` fallback CONCATENATED a second one — that is where the mystifying
      # "HTTP 000000" in run 36259218074 came from. Capture the status separately and normalize
      # anything that is not a plain code to 000 instead.
      code="$(curl -sS -m "$probe_timeout" -o "$probe" -w '%{http_code}' \
        "$RESOLVED_API_BASE/chat/completions" \
        -H "Authorization: Bearer $RESOLVED_API_KEY" -H 'Content-Type: application/json' \
        -d "{\"model\":\"$RESOLVED_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_completion_tokens\":16}" \
        2>/dev/null)" || true
      case "$code" in ''|*[!0-9]*) code=000 ;; esac
      echo "$role model probe attempt $attempt/$probe_attempts -> HTTP $code ($RESOLVED_API_BASE)"
      # DEFINITIVE answers, decided on the FIRST response and never retried: a live service has
      # already told us the run cannot work ON THIS PROVIDER. Retrying would burn the backoff to
      # reach the same conclusion and, worse, would dress a decision up as flakiness. These
      # RETURN a reason code instead of exiting: select_provider decides whether the next
      # provider in the order gets a try (plain name) or the run aborts (pinned id).
      if [ "$code" = "429" ] && grep -qi 'budget' "$probe" 2>/dev/null; then
        echo "$role model gateway ($RESOLVED_API_BASE) is OVER BUDGET (HTTP 429 budget_exceeded) for '$model'"
        head -c 300 "$probe" 2>/dev/null; echo; rm -f "$probe"; return 10
      fi
      if grep -qi 'not allowed to access model' "$probe" 2>/dev/null; then
        echo "gateway REFUSED $role model '$model' at call time (HTTP $code): the key's team is not entitled to it"
        head -c 600 "$probe" 2>/dev/null; echo; rm -f "$probe"; return 11
      fi
      [ "$code" = "200" ] && break
      # 000 = connect failure or timeout, 5xx = the upstream itself stumbling. Everything else
      # (any other 4xx) is a definitive answer from a live service — stop and report it.
      case "$code" in
        000|5??) : ;;
        *) break ;;
      esac
      [ "$attempt" -lt "$probe_attempts" ] || break
      backoff_s="${backoffs[$((attempt-1))]:-}"
      [ -n "$backoff_s" ] || backoff_s=15
      elapsed=$(( $(date +%s) - started_at ))
      if [ $(( elapsed + backoff_s + probe_timeout )) -gt "$probe_deadline" ]; then
        echo "::warning:: $role model probe: HTTP $code after ${elapsed}s — no room left in the ${probe_deadline}s preflight budget for another attempt"
        break
      fi
      echo "::warning:: $role model probe: HTTP $code from $RESOLVED_API_BASE looks transient — retrying in ${backoff_s}s"
      sleep "$backoff_s"
      attempt=$(( attempt + 1 ))
    done
    if [ "$code" != "200" ] && [ "$RESOLVED_PROVIDER" = "ibm-rits" ]; then
      echo "RITS probe for $role model '$model' failed (HTTP $code) against $RESOLVED_API_BASE:"
      echo "lite-rits may be down, or this model id is not in its scraped rits.json."
      echo "gave up after $attempt attempt(s); last observed HTTP $code."
      head -c 600 "$probe" 2>/dev/null; echo; rm -f "$probe"; return 13
    fi
    echo "gateway preflight: $role='$model' -> $RESOLVED_API_BASE; completion probe HTTP $code (attempt $attempt/$probe_attempts)"
    rm -f "$probe"
    # PROBE_LAST_CODE lets select_provider name the HTTP code in its skip reason.
    PROBE_LAST_CODE="$code"
    # 200 is usable. 400 is kept too: the model is listed, so a 400 means our probe's own
    # parameters are wrong, and another provider would reject them the same way.
    # 000 / 5xx: still unreachable after the retries (12). Any other answer (401, 403, 404, a 429
    # without "budget", ...) means this provider cannot serve the model right now (14). For both,
    # a pinned gateway id goes ahead with a warning, as before; a plain name tries the next
    # provider instead.
    case "$code" in
      200|400) return 0 ;;
      000|5??) return 12 ;;
    esac
    return 14
  }

  # select_provider <role> <requested-id> — walk the candidates for one role and record the
  # first usable one in $PF_DIR/<role>.{model,provider,skipped}. Aborts (exit 1) when none is.
  # Reason codes from probe_model: 10 over budget, 11 not entitled, 12 unreachable, 13 RITS
  # failed, 14 another non-200 answer (named by its HTTP code, e.g. "http-404").
  select_provider() {
    local role="$1" requested="$2" pinned=0 cands c provider rc reason skipped=""
    if is_pinned "$requested"; then
      pinned=1; cands="$requested"
    else
      cands="$(catalog_candidates "$requested")" || {
        echo "::error:: $role model '$requested' is not a prefixed id and not a plain name in ci/benchmarks/model_catalog.txt"
        exit 1
      }
      echo "provider order: $role '$requested' candidates: $(printf '%s ' $cands)"
    fi
    for c in $cands; do
      provider="$(provider_of "$c")"
      reason=""
      if [ "$pinned" = 0 ] && ! provider_has_creds "$provider"; then
        reason="no-secrets"
      elif [ "$provider" != "ibm-rits" ] && provider_has_creds "$provider" \
          && ! check_listed "$role" "$provider" "$c" "$pinned"; then
        reason="not-listed"
      else
        # `|| rc=$?`, not `; rc=$?`: this script runs under `set -e`, which would end it on the
        # first non-zero reason code before the next provider got a try.
        rc=0; probe_model "$role" "$c" || rc=$?
        case "$rc" in
          0) ;;
          12) if [ "$pinned" = 1 ]; then
                echo "::warning:: $role model '$c' did not answer the probe; continuing because it is pinned"
              else
                reason="unreachable"
              fi ;;
          14) if [ "$pinned" = 1 ]; then
                echo "::warning:: $role model '$c' probe answered HTTP $PROBE_LAST_CODE; continuing because it is pinned"
              else
                reason="http-$PROBE_LAST_CODE"
              fi ;;
          10) reason="over-budget" ;;
          11) reason="not-entitled" ;;
          *)  reason="probe-failed" ;;
        esac
      fi
      if [ -z "$reason" ]; then
        printf '%s\n' "$c" > "$PF_DIR/$role.model"
        printf '%s\n' "$provider" > "$PF_DIR/$role.provider"
        printf '%s\n' "${skipped# }" > "$PF_DIR/$role.skipped"
        echo "provider order: $role '$requested' -> '$c' (provider $provider${skipped:+; skipped:$skipped})"
        return 0
      fi
      echo "provider order: $role '$requested' — $provider skipped ($reason)"
      skipped="$skipped $provider:$reason"
      if [ "$pinned" = 1 ]; then
        case "$reason" in
          over-budget)
            echo "::error:: $role model '$c' is pinned to $provider, which is OVER BUDGET — aborting."
            echo "::error:: every rollout would score 0.000 as INFRASTRUCTURE_ERROR. Raise/reset the budget,"
            echo "::error:: or dispatch the plain model name so CI can fall back to the next provider." ;;
          not-entitled)
            echo "::error:: gateway REFUSED pinned $role model '$c': the key's team is not entitled to it, so"
            echo "::error:: every rollout would fail and the suite would publish a fake 0.000." ;;
          *)
            echo "::error:: pinned $role model '$c' failed its preflight probe ($reason) — aborting." ;;
        esac
        exit 1
      fi
    done
    echo "::error:: no provider can serve $role model '$requested' (tried:$skipped)."
    echo "::error:: every rollout would fail and the suite would publish a fake 0.000 — aborting."
    exit 1
  }
  # Select both roles concurrently — each hits a different role's endpoint (often a
  # different provider entirely, gateway vs. RITS) and neither depends on the other's
  # result, so the worst-case wall time is one role's probes instead of both. Backgrounding a
  # shell function still lets `exit 1` inside it end just that subshell; `wait "$pid"`
  # below recovers that as a normal nonzero status, so a failure still aborts this script.
  # The subshells cannot set variables here, so each writes its choice under $PF_DIR.
  PF_DIR="$(mktemp -d "${TMPDIR:-/tmp}/capevolve_provider.XXXXXX")"
  select_provider agent "$PF_AGENT" & pid_agent=$!
  select_provider optimizer "$PF_OPTIMIZER" & pid_optimizer=$!
  fail=0
  wait "$pid_agent" || fail=1
  wait "$pid_optimizer" || fail=1
  [ "$fail" = 0 ] || { rm -rf "$PF_DIR"; exit 1; }
  AGENT_MODEL_RESOLVED="$(cat "$PF_DIR/agent.model")"
  OPTIMIZER_MODEL_RESOLVED="$(cat "$PF_DIR/optimizer.model")"
  AGENT_PROVIDER="$(cat "$PF_DIR/agent.provider")"
  OPTIMIZER_PROVIDER="$(cat "$PF_DIR/optimizer.provider")"
  AGENT_PROVIDER_SKIPPED="$(cat "$PF_DIR/agent.skipped")"
  OPTIMIZER_PROVIDER_SKIPPED="$(cat "$PF_DIR/optimizer.skipped")"
  rm -rf "$PF_DIR"
  echo "provider choice: agent '$PF_AGENT' -> '$AGENT_MODEL_RESOLVED'; optimizer '$PF_OPTIMIZER' -> '$OPTIMIZER_MODEL_RESOLVED'"
  if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
    {
      echo "### Model providers"
      echo ""
      echo "| role | requested | runs on | provider | skipped |"
      echo "|---|---|---|---|---|"
      echo "| agent | \`$PF_AGENT\` | \`$AGENT_MODEL_RESOLVED\` | $AGENT_PROVIDER | ${AGENT_PROVIDER_SKIPPED:--} |"
      echo "| optimizer | \`$PF_OPTIMIZER\` | \`$OPTIMIZER_MODEL_RESOLVED\` | $OPTIMIZER_PROVIDER | ${OPTIMIZER_PROVIDER_SKIPPED:--} |"
      echo ""
    } >> "$GITHUB_STEP_SUMMARY"
  fi
fi

# Export for later workflow steps (no-op locally).
if [ -n "${GITHUB_ENV:-}" ]; then
  {
    echo "CAPEVOLVE_PY=$CAPEVOLVE_PY"
    echo "SKILLSBENCH_SRC=$CACHE/skillsbench-src"
    # The warmed npm cache must reach the NEXT step — `export` above dies with this shell,
    # and the adapter (which does the bind-mount) runs in the "Run suite" step.
    if [ -n "${HARBOR_NPM_CACHE:-}" ]; then echo "HARBOR_NPM_CACHE=$HARBOR_NPM_CACHE"; fi
    if [ -n "${SPREADSHEETBENCH_DATA_DIR:-}" ]; then echo "SPREADSHEETBENCH_DATA_DIR=$SPREADSHEETBENCH_DATA_DIR"; fi
    if [ -n "${RFE_CREATOR_SRC:-}" ]; then echo "RFE_CREATOR_SRC=$RFE_CREATOR_SRC"; fi
    if [ -n "${AW_EVAL:-}" ]; then echo "AW_EVAL=$AW_EVAL"; fi
    # The provider the preflight chose. run_suite.sh and the runmeta step prefer these over the
    # dispatch's own AGENT_MODEL/OPTIMIZER_MODEL, which may be a plain catalog name.
    if [ -n "${AGENT_MODEL_RESOLVED:-}" ]; then
      echo "AGENT_MODEL_RESOLVED=$AGENT_MODEL_RESOLVED"
      echo "OPTIMIZER_MODEL_RESOLVED=$OPTIMIZER_MODEL_RESOLVED"
      echo "AGENT_PROVIDER=$AGENT_PROVIDER"
      echo "OPTIMIZER_PROVIDER=$OPTIMIZER_PROVIDER"
      echo "AGENT_PROVIDER_SKIPPED=$AGENT_PROVIDER_SKIPPED"
      echo "OPTIMIZER_PROVIDER_SKIPPED=$OPTIMIZER_PROVIDER_SKIPPED"
    fi
    echo "PATH=$HOME/.local/bin:$PATH"
  } >> "$GITHUB_ENV"
fi
echo "ci_setup done for $BENCH (venv: $VENV)"
