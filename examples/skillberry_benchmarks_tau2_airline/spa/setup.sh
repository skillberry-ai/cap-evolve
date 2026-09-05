#!/usr/bin/env bash
# Onboard tau2-bench airline for the SPA arm and prepare it for optimization.
#
# This is the executable transcript of the cap-evolve INTAKE / implement-and-check phase
# for this example, driven by ../PROMPT.md: a coding agent following RUN.md does exactly
# these steps. Run it directly to reproduce in one command:
#
#   bash examples/skillberry_benchmarks_tau2_airline/spa/setup.sh
#   bash examples/skillberry_benchmarks_tau2_airline/spa/run.sh
#
# What the SPA arm needs that the direct arm does not: the Skillberry stack (Store + the
# Proxy-Agent that injects the candidate skill) and the benchmark's environment service.
# This script PROVISIONS the stack but does not start it — starting is a run's job, per
# the intervention skill: a run that provisions on the operator's behalf is the anti-pattern.
set -uo pipefail

EX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$EX_DIR/../../.." && pwd)"
# The pinned Skillberry build of tau2 — its runner already carries what SPA mode needs
# (context headers on the agent's LLM calls, the proxy-side trajectory merged into tau2's
# own, a disconnect at session end) and still exposes the plain airline domain. ONE build
# for both arms is what keeps a later direct-vs-spa comparison meaningful.
BENCH_REPO="https://github.com/skillberry-ai/skillberry-benchmarks.git"
BENCH_REF="${BENCH_REF:-a3a83266008275e9d800fd709927fa3dc4f23ec5}"
BENCH_DIR="$REPO/vendor/skillberry-benchmarks"
TAU2_DIR="$BENCH_DIR/tau2/tau2-bench"
VENV="${VENV:-$REPO/.venv}"
case "$VENV" in /*) ;; *) VENV="$REPO/$VENV" ;; esac
PY="$VENV/bin/python"
PYTHON="${PYTHON:-python3}"
PIP_INDEX="${PIP_INDEX:-https://pypi.org/simple}"
# Its OWN base, not the shared .capevolve: the two arms are separate onboardings, and a
# shared project dir means one arm's seed/spec silently overwrites the other's — which
# delivers candidates one way while the record says the other. Runs land here too, so
# .capevolve-spa/run_* never mixes with the direct arm's. (.gitignore covers .capevolve*/.)
BASE="${BASE:-$REPO/.capevolve-spa}"
PROJECT="${PROJECT:-$BASE/project}"
say(){ printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }
die(){ printf '\n\033[1;31mSETUP FAILED: %s\033[0m\n' "$*" >&2; exit 1; }

WITH_DASHBOARD="${WITH_DASHBOARD:-1}"
for arg in "$@"; do
  case "$arg" in
    --dashboard)    WITH_DASHBOARD=1 ;;
    --no-dashboard) WITH_DASHBOARD=0 ;;
    -h|--help) echo "usage: setup.sh [--dashboard|--no-dashboard]  (default: --dashboard)"; exit 0 ;;
    *) echo "unknown option: $arg  (use --dashboard | --no-dashboard)" >&2; exit 2 ;;
  esac
done

say "1/5  Install cap-evolve (Python venv + core CLI)"
[ -x "$PY" ] || "$PYTHON" -m venv "$VENV" \
  || die "could not create venv with '$PYTHON' — tau2-bench needs python >=3.12,<3.14; pass PYTHON=/path/to/python3.12"
"$PY" -m pip install -q --index-url "$PIP_INDEX" --upgrade pip
"$PY" -m pip install -q --index-url "$PIP_INDEX" -e "$REPO/core" || die "pip install ./core failed"
"$VENV/bin/cap-evolve" version || die "cap-evolve CLI not available"
if [ "$WITH_DASHBOARD" = "1" ]; then
  "$PY" -m pip install -q --index-url "$PIP_INDEX" -e "$REPO/dashboard/backend" \
    && echo "  dashboard server installed (live capybara UI: cap-evolve run --dashboard auto)" \
    || echo "  (optional) dashboard server not installed — run still works with --dashboard off"
else
  echo "  dashboard install SKIPPED (--no-dashboard) — run with: CAPEVOLVE_DASHBOARD=off bash run.sh"
fi

say "2/5  INTAKE (a) — install the benchmark at its PINNED commit"
# Pinned, not latest main: the recorded results and the SPA-aware airline domain both
# belong to this commit. A moving checkout makes a rerun incomparable to the record.
if [ ! -d "$BENCH_DIR/.git" ]; then
  echo "  cloning skillberry-benchmarks -> $BENCH_DIR"
  git clone -q "$BENCH_REPO" "$BENCH_DIR" || die "git clone skillberry-benchmarks failed"
fi
git -C "$BENCH_DIR" fetch -q --all || die "git fetch skillberry-benchmarks failed"
git -C "$BENCH_DIR" checkout -q "$BENCH_REF" || die "checkout $BENCH_REF failed"
[ -d "$TAU2_DIR" ] || die "expected tau2-bench at $TAU2_DIR — is $BENCH_REF the right pin?"
# The [skillberry] extra is what pulls the proxy-aware runner bits. Without it the
# airline_skillberry domain is missing and every rollout dies at env construction.
"$PY" -m pip install -q --index-url "$PIP_INDEX" -e "$TAU2_DIR[skillberry]" \
  || die "pip install tau2-bench[skillberry] failed"
BENCH_SHA="$(git -C "$BENCH_DIR" rev-parse HEAD)"
"$PY" -c "import tau2" >/dev/null 2>&1 || die "tau2 import failed after install"
# Warn, never die: this only introspects the registry to catch a missing [skillberry]
# extra early. tau2's registry API is not ours, so a shape change must not block setup —
# `cap-evolve check` and the first rollout are the authoritative gates.
"$PY" - <<'PYEOF' || true
DOMAIN = "airline_skillberry"
try:
    from tau2.registry import registry
    names = []
    for attr in ("get_domains", "domains", "get_info"):
        got = getattr(registry, attr, None)
        got = got() if callable(got) else got
        if isinstance(got, dict):
            got = got.get("domains", [])
        if got:
            names = [str(x) for x in got]
            break
    if not names:
        print(f"  (could not introspect registered domains; {DOMAIN} unverified)")
    elif DOMAIN in names:
        print(f"  {DOMAIN} domain registered")
    else:
        print(f"  WARNING: {DOMAIN} NOT registered (saw: {names}) — is the [skillberry] extra installed?")
except Exception as e:  # noqa: BLE001
    print(f"  (domain check skipped: {type(e).__name__})")
PYEOF
echo "  tau2-bench (skillberry build) installed @ $BENCH_SHA"

say "3/5  INTAKE (b) — provision the Skillberry stack (Store + Proxy-Agent)"
# PROVISION ONLY: clone + venv + install both services, idempotently. Starting them is
# run.sh's job. The pins live in spa_env (store tag + agent commit), env-overridable via
# SKILLBERRY_STORE_REF / SKILLBERRY_AGENT_REF for a bisect.
CAPEVOLVE_SKILLS_DIR="$REPO/skills" "$PY" - <<'PYEOF' || die "Skillberry stack provisioning failed"
import json, sys
sys.path.insert(0, "skills/interventions/llm-proxies/spa/scripts")
import spa_env
out = spa_env.provision()
print("  " + json.dumps(out))
print(f"  store ref {spa_env.STORE_REF} @ {spa_env.store_dir()}")
print(f"  agent ref {spa_env.AGENT_REF[:7]} @ {spa_env.agent_dir()}")
PYEOF

say "4/5  Wire the project (adapter + gateway + seed + spec)"
"$PY" "$REPO/skills/phases/intake/scripts/run.py" --base "$BASE" --workdir "$REPO" --force >/dev/null \
  || die "intake scaffold failed"
mkdir -p "$PROJECT/adapters"
cp "$EX_DIR/adapters/adapter.py" "$EX_DIR/adapters/gateway.py" "$PROJECT/adapters/"
# The seed is TWO things: my_skill/ (the capability the optimizer edits) and
# primitive_tools/ (the FROZEN substrate, protected by the spec). Copy both.
rm -rf "$PROJECT/seed_capability"; cp -R "$EX_DIR/seed_capability" "$PROJECT/seed_capability"
mkdir -p "$PROJECT/optimizer"; cp "$EX_DIR/optimizer/INSTRUCTIONS.md" "$PROJECT/optimizer/"
cp "$EX_DIR/capevolve.yaml" "$EX_DIR/capevolve.smoke.yaml" \
   "$EX_DIR/split_ids.json" "$EX_DIR/split_ids_task9.json" "$EX_DIR/smoke_split.json" "$PROJECT/"
echo "  project scaffolded + integration wired at $PROJECT"

say "5/5  Hard gate — cap-evolve check (credentials + adapter contract)"
# The gateway needs a base URL AND a key; either missing 401s/404s every rollout, which
# reads as a bad capability rather than a bad config.
for v in OPENAI_BASE_URL OPENAI_API_KEY; do
  if [ -z "${!v:-}" ] && ! grep -q "^$v=" "$REPO/.env" 2>/dev/null; then
    echo "  WARNING: $v not set and not in $REPO/.env — the run needs it (user simulator + judge)."
  fi
done
PYTHONPATH="$PROJECT/adapters" CAPEVOLVE_SKILLS_DIR="$REPO/skills" \
  "$VENV/bin/cap-evolve" check "$PROJECT" || die "cap-evolve check did not pass"

printf '\n\033[1;32mREADY.\033[0m  Next:\n  bash %s/run.sh              # full run (2 iters · task 9 · 5 trials)\n  bash %s/run.sh --smoke      # cheap smoke over the same stack\n' "$EX_DIR" "$EX_DIR"
