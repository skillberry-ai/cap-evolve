#!/usr/bin/env bash
# Onboard tau2-bench airline for the blackbox arm and prepare it for optimization.
#
# This is the executable transcript of the cap-evolve INTAKE / implement-and-check phase
# for this example, driven by ../PROMPT.md: a coding agent following RUN.md does exactly
# these steps. Run it directly to reproduce in one command:
#
#   bash examples/tau2_airline/blackbox/setup.sh
#   bash examples/tau2_airline/blackbox/run.sh
#
# What the blackbox arm needs that the direct arm does not: the Skillberry stack (Store + the
# Proxy-Agent that injects the candidate skill) and the benchmark's environment service.
# This script PROVISIONS the stack but does not start it — starting is a run's job, per
# the intervention skill: a run that provisions on the operator's behalf is the anti-pattern.
set -uo pipefail

EX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$EX_DIR/../../.." && pwd)"
# VANILLA upstream tau2, installed UNMODIFIED. Everything blackbox mode needs that stock tau2
# does not do — context headers on the agent's LLM calls, the two trajectory merges, the vMCP
# disconnect, the arm's domain — is applied from OUTSIDE by adapters/tau2_tailoring.py at
# apply() time. A benchmark edited to suit the intervention stops being comparable to anyone
# else's numbers, including our own earlier ones.
BENCH_REPO="https://github.com/sierra-research/tau2-bench.git"
# LATEST MAIN, and the resolved commit is RECORDED (below) rather than pinned — the convention
# PROMPT.md states. The benchmark owns the policy the agent reads, the task set and the reward
# checks, so a number that cannot name its commit cannot be compared to another.
BENCH_REF="${BENCH_REF:-main}"
BENCH_DIR="$REPO/vendor/tau2-bench"
TAU2_DIR="$BENCH_DIR"
VENV="${VENV:-$REPO/.venv}"
case "$VENV" in /*) ;; *) VENV="$REPO/$VENV" ;; esac
PY="$VENV/bin/python"
PYTHON="${PYTHON:-python3}"
PIP_INDEX="${PIP_INDEX:-https://pypi.org/simple}"
# Its OWN base, not the shared .capevolve: the two arms are separate onboardings, and a
# shared project dir means one arm's seed/spec silently overwrites the other's — which
# delivers candidates one way while the record says the other. Runs land here too, so
# .capevolve-blackbox/run_* never mixes with the direct arm's. (.gitignore covers .capevolve*/.)
BASE="${BASE:-$REPO/.capevolve-blackbox}"
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
  echo "  cloning tau2-bench (vanilla) -> $BENCH_DIR"
  git clone -q "$BENCH_REPO" "$BENCH_DIR" || die "git clone tau2-bench failed"
fi
git -C "$BENCH_DIR" fetch -q --all || die "git fetch tau2-bench failed"
git -C "$BENCH_DIR" checkout -q "$BENCH_REF" || die "checkout $BENCH_REF failed"
[ -d "$TAU2_DIR" ] || die "expected tau2-bench at $TAU2_DIR — is $BENCH_REF the right pin?"
# `websockets` is NOT optional despite living in tau2's [voice] extra: tau2's data_model
# imports its voice stack UNCONDITIONALLY, so a base install cannot even `import tau2`.
# Installing all of [voice] would drag in livekit, boto3 and google-cloud-aiplatform.
"$PY" -m pip install -q --index-url "$PIP_INDEX" -e "$TAU2_DIR" "websockets>=13.0" \
  || die "pip install tau2-bench failed"
BENCH_SHA="$(git -C "$BENCH_DIR" rev-parse HEAD)"
if ! _tau2_err="$("$PY" -c "import tau2" 2>&1)"; then
  printf '%s\n' "$_tau2_err" | tail -5 >&2
  die "tau2 import failed after install (real error above)"
fi
# Prove the TAILORING registers the arm against this vanilla checkout — the single most
# valuable check here, because it is what replaces the forked build. Warn rather than die: the
# authoritative gates are `cap-evolve check` below and the first rollout.
# The single most valuable check in this script: prove the TAILORING registers this arm against
# the VANILLA checkout just installed. REQUIRED, not a probe — the arm cannot work without it, and
# the previous version swallowed every failure into a "skipped" note, so a misplaced module or a
# moved tau2 seam printed a cosmetic line and setup carried on reporting success.
# The dir is passed in ABSOLUTE via the environment: the heredoc is quoted (no shell expansion),
# and a relative path silently resolved against whatever cwd the caller happened to be in.
TAILORING_DIR="$EX_DIR/adapters" CAPEVOLVE_SKILLS_DIR="$REPO/skills" "$PY" - <<'PYEOF' \
  || die "the tailoring could not register against this tau2 (see the error above)"
import os
import sys

sys.path.insert(0, os.environ["TAILORING_DIR"])
import tau2_tailoring as T                       # a MISSING module here is a wiring bug

T.install(); T.install()                          # idempotent: every phase re-loads the adapter
from tau2.registry import registry

if T.DOMAIN not in registry.get_domains():
    sys.exit(f"  tailoring did not register the domain {T.DOMAIN}")
if registry.get_agent_factory(T.AGENT_NAME) is None:
    sys.exit(f"  tailoring did not register the agent factory {T.AGENT_NAME}")
print(f"  tailoring registered {T.DOMAIN} + {T.AGENT_NAME}")
for n in T.verify()["notes"]:                     # raises SeamError, naming the seam, on drift
    print("  seam:", n)
PYEOF
echo "  tau2-bench (VANILLA) installed @ $BENCH_SHA  <- record this commit"

say "3/5  INTAKE (b) — provision the Skillberry stack (Store + Proxy-Agent)"
# PROVISION ONLY: clone + venv + install both services, idempotently. Starting them is
# run.sh's job. The pins live in blackbox_env (store tag + agent commit), env-overridable via
# SKILLBERRY_STORE_REF / SKILLBERRY_AGENT_REF for a bisect.
CAPEVOLVE_SKILLS_DIR="$REPO/skills" "$PY" - <<'PYEOF' || die "Skillberry stack provisioning failed"
import json, os, sys
sys.path.insert(0, os.path.join(os.environ["CAPEVOLVE_SKILLS_DIR"],
                               "interventions", "llm-proxies", "blackbox", "scripts"))
import blackbox_env
out = blackbox_env.provision()
print("  " + json.dumps(out))
print(f"  store ref {blackbox_env.STORE_REF} @ {blackbox_env.store_dir()}")
print(f"  agent ref {blackbox_env.AGENT_REF[:7]} @ {blackbox_env.agent_dir()}")
PYEOF

say "4/5  Wire the project (adapter + gateway + seed + spec)"
"$PY" "$REPO/skills/phases/intake/scripts/run.py" --base "$BASE" --workdir "$REPO" --force >/dev/null \
  || die "intake scaffold failed"
mkdir -p "$PROJECT/adapters"
cp "$EX_DIR/adapters/adapter.py" "$EX_DIR/adapters/gateway.py" \
   "$EX_DIR/adapters/tau2_tailoring.py" "$PROJECT/adapters/"
# The seed is TWO things: my_skill/ (the capability the optimizer edits) and
# primitive_tools/ (the FROZEN substrate, protected by the spec). Copy both.
rm -rf "$PROJECT/seed_capability"; cp -R "$EX_DIR/seed_capability" "$PROJECT/seed_capability"
mkdir -p "$PROJECT/optimizer"; cp "$EX_DIR/optimizer/INSTRUCTIONS.md" "$PROJECT/optimizer/"
cp "$EX_DIR/capevolve.yaml" "$EX_DIR/capevolve.smoke.yaml" \
   "$EX_DIR/split_ids.json" "$EX_DIR/smoke_split.json" "$PROJECT/"
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

printf '\n\033[1;32mREADY.\033[0m  Next:\n  bash %s/run.sh              # full run (run.sh prints the scale + cost first)\n  bash %s/run.sh --smoke      # cheap smoke over the same stack\n' "$EX_DIR" "$EX_DIR"
printf '\nNote: the current blackbox mode version does not support running with `cap-evolve run`.\n'
