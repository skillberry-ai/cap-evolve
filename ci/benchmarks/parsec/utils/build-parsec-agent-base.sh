#!/usr/bin/env bash
# Rebuild the parsec-agent-base:latest container image.
#
# Usage:  bash ci/benchmarks/parsec/utils/build-parsec-agent-base.sh
#
# What this does. Runs `podman build` against the Dockerfile in
# ci/benchmarks/parsec/docker/parsec-agent-base/. Produces a local image tagged
# `localhost/parsec-agent-base:latest` — used by every shadowed parsec task
# (both tiers: see utils/patch-harbor-tasks.sh for v1 and
# utils/patch-harbor-tasks-v2.sh for v2, each of which rewrites task.toml's
# docker_image to this tag) so Harbor can pull it by tag without hitting a
# network registry.
#
# When to rerun.
#   * The Dockerfile changed.
#   * `podman image rm localhost/parsec-agent-base:latest` was run for any reason.
#   * A new Harbor release starts installing something we haven't pre-installed
#     inside the image, and we want to add it as another `dnf install` line.
#
# Docs: ci/benchmarks/parsec/README.md

set -euo pipefail

HERE="$(cd "$(dirname "$0")/../docker/parsec-agent-base" && pwd)"
IMAGE=localhost/parsec-agent-base:latest

if ! command -v podman >/dev/null 2>&1; then
    echo "podman not on PATH. Install via: brew install podman" >&2
    exit 1
fi

if ! podman machine list --format='{{.LastUp}}' 2>/dev/null | grep -q Current; then
    echo "podman machine is not running. Start it via: podman machine start" >&2
    exit 1
fi

echo "→ building $IMAGE from $HERE/Dockerfile"
podman build --tag "$IMAGE" "$HERE"

echo ""
echo "→ image summary"
podman image inspect "$IMAGE" --format \
  'id: {{.Id}}
size: {{.Size}} bytes
labels: {{range $k, $v := .Labels}}
  {{$k}} = {{$v}}{{end}}'

echo ""
echo "Done. Verify with: podman run --rm $IMAGE bash -lc 'curl --version | head -1; node --version; npm --version'"
