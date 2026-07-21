#!/usr/bin/env bash
# arm-runner.sh — register THIS machine (on the IBM network) as an EPHEMERAL GitHub
# Actions runner for the benchmarks workflow, run ONE job, then exit. Re-run to re-arm.
#
# Why self-hosted: the model gateway (…vpc-int.res.ibm.com) is VPC-internal and is only
# reachable from a host already on the IBM network — GitHub-hosted runners cannot reach it.
#
# Prereqs: Docker running (swebench/skillsbench jobs); this host on the IBM network.
# A registration token is needed — either:
#   * set RUNNER_TOKEN=<token> (mint it on a repo-admin machine with:
#       gh api -X POST repos/<owner>/<repo>/actions/runners/registration-token --jq .token), or
#   * have `gh` authenticated (repo-admin) on THIS host.
#
# The runner package + its .credentials/_work live OUTSIDE the repo (default
# ~/.cache/capevolve-gh-runner) so nothing sensitive is ever committed.
set -euo pipefail

REPO_SLUG="${CAPEVOLVE_REPO:-skillberry-ai/cap-evolve}"
RUNNER_DIR="${RUNNER_DIR:-$HOME/.cache/capevolve-gh-runner}"
LABELS="${RUNNER_LABELS:-ibm-vpc}"
RUNNER_VERSION="${RUNNER_VERSION:-2.328.0}"

# Auto-detect the runner package for this host (skillberry-1 is expected to be linux-x64).
if [ -z "${RUNNER_ARCH:-}" ]; then
  case "$(uname -s)-$(uname -m)" in
    Linux-x86_64)  RUNNER_ARCH="linux-x64" ;;
    Linux-aarch64) RUNNER_ARCH="linux-arm64" ;;
    Darwin-arm64)  RUNNER_ARCH="osx-arm64" ;;
    Darwin-x86_64) RUNNER_ARCH="osx-x64" ;;
    *) echo "unknown platform $(uname -s)-$(uname -m); set RUNNER_ARCH" >&2; exit 1 ;;
  esac
fi
ARCH="$RUNNER_ARCH"

TOKEN="${RUNNER_TOKEN:-}"
if [ -z "$TOKEN" ]; then
  command -v gh >/dev/null || { echo "set RUNNER_TOKEN, or install+auth gh (repo admin)" >&2; exit 1; }
  echo "Requesting a registration token for $REPO_SLUG …"
  TOKEN="$(gh api -X POST "repos/$REPO_SLUG/actions/runners/registration-token" -q .token)"
fi
[ -n "$TOKEN" ] || { echo "could not get a registration token (need repo admin)" >&2; exit 1; }

mkdir -p "$RUNNER_DIR"; cd "$RUNNER_DIR"
if [ ! -x ./run.sh ]; then
  PKG="actions-runner-${ARCH}-${RUNNER_VERSION}.tar.gz"
  echo "Downloading runner $PKG …"
  curl -fsSL -o "$PKG" "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/${PKG}"
  tar xzf "$PKG"
fi

# (re)configure. Ephemeral by default (one job, then deregister); set RUNNER_EPHEMERAL=0
# for a persistent runner (e.g. to clear a multi-job matrix in one arming).
EPH="--ephemeral"; [ "${RUNNER_EPHEMERAL:-1}" = "0" ] && EPH=""
./config.sh remove --token "$TOKEN" >/dev/null 2>&1 || true
./config.sh --url "https://github.com/$REPO_SLUG" --token "$TOKEN" \
  --labels "$LABELS" --name "$(hostname -s)-capevolve" $EPH --unattended --replace

echo "Runner armed (labels: $LABELS${EPH:+, ephemeral}) — waiting for job(s)."
exec ./run.sh
