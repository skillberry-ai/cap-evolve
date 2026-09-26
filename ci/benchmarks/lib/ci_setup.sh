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
# The arms get their OWN venv. They install tau2 from either skillberry-benchmarks or
# the public sierra-research checkout. Same package name, two sources.
case "$BENCH" in
  tau2_custom_*) VENV="$CACHE/venv-tau2-custom" ;;
  *)                 VENV="$CACHE/venv" ;;
esac
CAPEVOLVE_PY="$VENV/bin/python"
IDX="--index-url https://pypi.org/simple"
mkdir -p "$CACHE"

command -v uv >/dev/null || { echo "::error:: uv is required on the runner"; exit 1; }
[ -x "$CAPEVOLVE_PY" ] || uv venv --python 3.12 "$VENV"

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
  tau2)
    [ -d "$CACHE/tau2-bench/.git" ] || git clone --depth 1 https://github.com/sierra-research/tau2-bench "$CACHE/tau2-bench"
    uv pip install -p "$CAPEVOLVE_PY" -q $IDX -e "$CACHE/tau2-bench" ;;
  tau2_custom_direct|tau2_custom_blackbox)
    # A DIFFERENT tau2 build from the `tau2` leg above. Both arms are onboarded against
    # skillberry-ai/skillberry-benchmarks at a PINNED commit. ONE build for both arms is what keeps
    # a direct-vs-blackbox comparison meaningful;
    #
    # The pin is the SAME default the arms own setup.sh scripts use, so a CI number and a
    # local `bash examples/.../run.sh` number refer to the same benchmark code. 
    BENCH_REF="${BENCH_REF:-a3a83266008275e9d800fd709927fa3dc4f23ec5}"
    SB_DIR="$CACHE/skillberry-benchmarks"
    if [ ! -d "$SB_DIR/.git" ]; then
      git clone -q https://github.com/skillberry-ai/skillberry-benchmarks.git "$SB_DIR" || {
        echo "::error:: could not clone skillberry-ai/skillberry-benchmarks."
        echo "::error:: The repository is PUBLIC and needs no credentials, so this is almost"
        echo "::error:: always transient — network, DNS, or a GitHub blip. Re-run the job."
        echo "::error:: Without the checkout neither arm can run at all."
        exit 1; }
    fi
    git -C "$SB_DIR" fetch -q --all || echo "::warning:: fetch failed; using the cached checkout"
    git -C "$SB_DIR" checkout -q "$BENCH_REF" \
      || { echo "::error:: checkout $BENCH_REF failed in $SB_DIR"; exit 1; }
    uv pip install -p "$CAPEVOLVE_PY" -q $IDX -e "$SB_DIR/tau2/tau2-bench[skillberry]" \
      || { echo "::error:: pip install tau2-bench[skillberry] failed"; exit 1; }
    "$CAPEVOLVE_PY" -c "import tau2; print('tau2 (skillberry build) OK')"
    # run_suite.sh resolves the arm's `runner_repo_path` from this. It must be ABSOLUTE: the
    # arms' committed specs use a project-relative '../../vendor/skillberry-benchmarks', which
    # would resolve to nothing under ci/benchmarks/.work/.
    echo "skillberry-benchmarks @ $(git -C "$SB_DIR" rev-parse HEAD)"
    if [ "$BENCH" = "tau2_custom_blackbox" ]; then
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
      echo "SKILLBERRY_BENCH_DIR=$SB_DIR" >> "$GITHUB_ENV"
      # MUST reach the "Run suite" step: blackbox_env recomputes its vendor dir from the environment
      # in that process too, and a run that disagreed with setup about where the stack lives
      # would re-provision from scratch mid-leg.
      if [ -n "${SPA_VENDOR_DIR:-}" ]; then echo "SPA_VENDOR_DIR=$SPA_VENDOR_DIR" >> "$GITHUB_ENV"; fi
    fi
    export SKILLBERRY_BENCH_DIR="$SB_DIR" ;;
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
      # no_skill is full_verified's no-capability CONTROL, so it must read the SAME archive —
      # a control on different data is not a control.
      full_verified|no_skill) SB_VARIANT="verified_400" ;;
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
if command -v curl >/dev/null; then
  PF_AGENT="${AGENT_MODEL:-aws/gpt-oss-120b}"
  PF_OPTIMIZER="${OPTIMIZER_MODEL:-claude-opus-4-8}"
  # shellcheck source=ci/benchmarks/lib/resolve_provider.sh
  . "$LIB_DIR/resolve_provider.sh"

  case "$PF_AGENT" in
    rits/*) PF_AGENT_IS_RITS=1 ;;
    *)      PF_AGENT_IS_RITS=0 ;;
  esac
  case "$PF_OPTIMIZER" in
    rits/*) PF_OPTIMIZER_IS_RITS=1 ;;
    *)      PF_OPTIMIZER_IS_RITS=0 ;;
  esac

  # 1. ENTITLEMENT — is each SELECTED *gateway* model served to this key at all? Only
  # gateway-routed models are checkable this way; a "rits/*" model has no /models listing to
  # confirm against, so it is simply not passed to --require (its absence from the gateway's
  # list is expected, not a fault).
  if [ -n "${ANTHROPIC_BASE_URL:-}" ] && [ -n "${ANTHROPIC_AUTH_TOKEN:-}" ] \
      && { [ "$PF_AGENT_IS_RITS" = 0 ] || [ "$PF_OPTIMIZER_IS_RITS" = 0 ]; }; then
    # /models is an `llm_api_routes` call. The richer /model/info and /key/info are NOT: these
    # virtual keys are route-scoped and answer both with 403 "not allowed to call this route",
    # which is also the real reason the old preflight logged a mystery HTTP 403.
    models=/tmp/capevolve_models.$$.json
    mcode="$(curl -sS -m 30 -o "$models" -w '%{http_code}' \
      "$ANTHROPIC_BASE_URL/models" \
      -H "Authorization: Bearer $ANTHROPIC_AUTH_TOKEN" 2>/dev/null || echo 000)"
    if [ "$mcode" = "200" ]; then
      require_args=()
      [ "$PF_AGENT_IS_RITS" = 0 ] && require_args+=(--require "agent=$PF_AGENT")
      [ "$PF_OPTIMIZER_IS_RITS" = 0 ] && require_args+=(--require "optimizer=$PF_OPTIMIZER")
      if ! "$CAPEVOLVE_PY" "$LIB_DIR/check_models.py" "$models" "${require_args[@]}"; then
        rm -f "$models"; exit 1
      fi
    else
      echo "::warning:: gateway /models returned HTTP $mcode — cannot verify model entitlement"
    fi
    rm -f "$models"
  fi

  # 2. BUDGET/ENTITLEMENT at call time — one real completion per SELECTED model, against
  # whichever provider actually serves it. Listing a gateway model is necessary but not
  # sufficient (the team check happens at call time), and RITS has no listing step at all, so
  # this probe is the only check it gets.
  # `max_completion_tokens` (not `max_tokens`) is used because the Azure reasoning
  # deployments reject the latter outright, and a probe that 400s on its own parameters
  # would be a false alarm.
  probe_model() {
    local role="$1" model="$2"
    # Graceful skip, not a hard abort: resolve_provider's non-"rits/*" branch does a hard
    # `:?` on ANTHROPIC_BASE_URL/ANTHROPIC_AUTH_TOKEN, which would otherwise kill this WHOLE
    # script (set -uo pipefail; no outer `if` catches a `:?` failure) for a run that never
    # asked for the gateway at all — e.g. a local/laptop run of a RITS-only dispatch, or one
    # with the other role on RITS and this role's gateway secrets simply not exported. Before
    # this check existed, the only gate was `[ -n "${ANTHROPIC_BASE_URL:-}" ] && ... &&
    # command -v curl` around the ENTIRE preflight block above; narrowing that to
    # `command -v curl` (so RITS-only dispatches still get probed) reintroduced exactly the
    # failure mode it used to prevent for the non-RITS case.
    case "$model" in
      rits/*) : ;;
      *)
        if [ -z "${ANTHROPIC_BASE_URL:-}" ] || [ -z "${ANTHROPIC_AUTH_TOKEN:-}" ]; then
          echo "::warning:: ANTHROPIC_BASE_URL/ANTHROPIC_AUTH_TOKEN not set — skipping $role model preflight probe for '$model'"
          return 0
        fi
        ;;
    esac
    resolve_provider "$model"
    local probe="/tmp/capevolve_budget_probe.$$_${role}.json"
    local code
    code="$(curl -sS -m 60 -o "$probe" -w '%{http_code}' \
      "$RESOLVED_API_BASE/chat/completions" \
      -H "Authorization: Bearer $RESOLVED_API_KEY" -H 'Content-Type: application/json' \
      -d "{\"model\":\"$RESOLVED_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_completion_tokens\":16}" \
      2>/dev/null || echo 000)"
    if [ "$code" = "429" ] && grep -qi 'budget' "$probe" 2>/dev/null; then
      echo "::error:: $role model gateway ($RESOLVED_API_BASE) is OVER BUDGET (HTTP 429 budget_exceeded) — aborting."
      echo "::error:: every rollout would score 0.000 as INFRASTRUCTURE_ERROR. Raise/reset the gateway budget."
      head -c 300 "$probe" 2>/dev/null; echo; rm -f "$probe"; exit 1
    fi
    if grep -qi 'not allowed to access model' "$probe" 2>/dev/null; then
      echo "::error:: gateway REFUSED $role model '$model' at call time (HTTP $code):"
      echo "::error:: the key's team is not entitled to it, so every rollout would fail and the"
      echo "::error:: suite would publish a fake 0.000. Pick a model this key can call."
      head -c 600 "$probe" 2>/dev/null; echo; rm -f "$probe"; exit 1
    fi
    if [ "$code" != "200" ] && [ "$RESOLVED_API_BASE" = "${RITS_API_BASE:-}" ]; then
      echo "::error:: RITS probe for $role model '$model' failed (HTTP $code) against $RESOLVED_API_BASE:"
      echo "::error:: lite-rits may be down, or this model id is not in its scraped rits.json."
      head -c 600 "$probe" 2>/dev/null; echo; rm -f "$probe"; exit 1
    fi
    echo "gateway preflight: $role='$model' -> $RESOLVED_API_BASE; completion probe HTTP $code"
    rm -f "$probe"
  }
  # Run both probes concurrently — each hits a different role's endpoint (often a
  # different provider entirely, gateway vs. RITS) and neither depends on the other's
  # result, so the worst-case wall time is one 60s timeout instead of two. Backgrounding a
  # shell function still lets `exit 1` inside it end just that subshell; `wait "$pid"`
  # below recovers that as a normal nonzero status, so a probe failure still aborts this
  # script exactly as it did when the calls were sequential.
  probe_model agent "$PF_AGENT" & pid_agent=$!
  probe_model optimizer "$PF_OPTIMIZER" & pid_optimizer=$!
  fail=0
  wait "$pid_agent" || fail=1
  wait "$pid_optimizer" || fail=1
  [ "$fail" = 0 ] || exit 1
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
    echo "PATH=$HOME/.local/bin:$PATH"
  } >> "$GITHUB_ENV"
fi
echo "ci_setup done for $BENCH (venv: $VENV)"
