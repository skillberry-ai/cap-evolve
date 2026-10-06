# parsec-agent-base:latest — a ubi9-based image ready for Harbor's claude-code CLI.
#
# Purpose. Harbor's claude-code agent installer runs `yum install -y curl procps-ng`
# inside whatever image the task declares. Parsec's harbor-tasks declare bare
# `registry.access.redhat.com/ubi9/ubi:latest`, and vanilla ubi9 ships `curl-minimal`
# which conflicts with `curl` from the ubi-baseos repo — the yum install fails, the
# container exits, no trajectory is recorded. We build this image once, up front,
# with the conflict pre-resolved via `--allowerasing` and with node/npm baked in so
# Harbor's per-container `npm install -g @anthropic-ai/claude-code` runs against a
# warm system.
#
# Both tiers use it: the v1 (smoke/pilot) and v2 shadow patchers each rewrite every
# task.toml's docker_image to `localhost/parsec-agent-base:latest`, so this image must
# exist locally before either tier can run.
#
# Rebuild:  bash ci/benchmarks/parsec/utils/build-parsec-agent-base.sh
# Docs:     ci/benchmarks/parsec/README.md

FROM registry.access.redhat.com/ubi9/ubi:latest

# 1. Resolve the curl / curl-minimal conflict, then install the tools Harbor's
#    claude-code installer expects. `--allowerasing` lets curl replace curl-minimal
#    without requiring the installer to know that trick. `install_weak_deps=False`
#    keeps the image lean.
RUN dnf install -y --allowerasing curl bash procps-ng \
 && dnf install -y --setopt=install_weak_deps=False nodejs npm \
 && dnf clean all \
 && rm -rf /var/cache/dnf

# 2. Harbor's Trial code uploads the task's environment/ to /workspace and the agent
#    runs there. Parsec's task.toml already declares workdir = "/workspace" but a
#    default here keeps things consistent for direct `podman run` debugging.
WORKDIR /workspace

# 3. Sanity — surfaces the versions to `podman inspect` so we can tell at a glance
#    which build of the base image is running.
LABEL org.parsec.agent-base.built-for="cap-evolve parsec-intake pilot" \
      org.parsec.agent-base.node-required-by="Harbor claude-code CLI installer"
