#!/bin/bash
#
# Podman setup for CCC.
#
# Must be SOURCED from bash (not executed, not sh) — it exports
# PATH/DOCKER_HOST/XDG_RUNTIME_DIR into the calling shell, and uses
# bash-only parameter expansion.
#
# Usage:
#   source scripts/ccc/setup_podman.sh
#
# Or run once to create ~/.config/containers/storage.conf, then just export
# XDG_RUNTIME_DIR yourself in later shells.
#
# What this does:
#   - Writes ~/.config/containers/storage.conf pointing runroot/graphroot at
#     host-local /tmp paths (so different LSF hosts don't corrupt each other).
#   - Exports XDG_RUNTIME_DIR to a writable /tmp path (the default
#     /run/user/$UID isn't writable for us on CCC).
#   - Creates the directories if missing.
#
# Notes:
#   - Storage lives on /tmp -> host-local. Image pulls don't survive host
#     changes. If image pulls become a bottleneck, switch STORAGE_BASE to a
#     GPFS path suffixed with $(hostname) (see below).
#   - You may still see a subuid/subgid warning on first run. Simple
#     containers work; images that need user namespaces require CCC admins
#     to add you to /etc/subuid and /etc/subgid. Ping @ccc_admins in that
#     case.
#   - Workaround when admin help is unavailable: we set
#     ignore_chown_errors="true" under [storage.options.overlay]. Podman
#     then skips lchown calls it can't perform during image unpack; files
#     that "should" be owned by UID 42 (e.g. /etc/gshadow) land as root
#     instead. Fine for most tasks; tasks that verify file ownership inside
#     the container will still break.

_uid="$(id -u)"

# Host-local storage. Safe for concurrent podman on the same host (podman
# serializes internally), never shared across hosts.
STORAGE_BASE="/tmp/podman-${_uid}"
RUN_BASE="/tmp/podman-run-${_uid}"

# Alternative for GPFS-backed image cache (uncomment and comment the two
# lines above). Pays a per-host directory but images persist per host.
# STORAGE_BASE="/path/to/shared/fs/.podman-$(hostname)"
# RUN_BASE="/tmp/podman-run-${_uid}"

mkdir -p "$STORAGE_BASE" "$RUN_BASE"
chmod 700 "$STORAGE_BASE" "$RUN_BASE"

# Write storage.conf if missing OR if it doesn't match the paths we want.
CONF_DIR="$HOME/.config/containers"
CONF_FILE="$CONF_DIR/storage.conf"
mkdir -p "$CONF_DIR"

_desired=$(cat <<EOF
# Managed by setup_podman.sh. Edit STORAGE_BASE/RUN_BASE in that script,
# not here.
[storage]
driver = "overlay"
runroot = "$RUN_BASE"
graphroot = "$STORAGE_BASE"

[storage.options.overlay]
# Workaround for missing /etc/subuid entry on CCC: skip lchown calls that
# would need UIDs outside our single-UID user namespace. Without this,
# ubuntu:24.04 (and every SkillsBench task image built on it) fails to
# unpack because it wants UID 42 to own /etc/gshadow.
ignore_chown_errors = "true"
EOF
)

if [ ! -f "$CONF_FILE" ] || ! diff -q <(printf '%s\n' "$_desired") "$CONF_FILE" >/dev/null 2>&1; then
    # Back up a pre-existing file once — it may be hand-maintained, and this
    # is otherwise a silent destructive overwrite.
    if [ -f "$CONF_FILE" ] && [ ! -f "$CONF_FILE.bak" ]; then
        cp -p "$CONF_FILE" "$CONF_FILE.bak"
        echo "[setup_podman] backed up existing storage.conf -> $CONF_FILE.bak"
    fi
    printf '%s\n' "$_desired" > "$CONF_FILE"
    echo "[setup_podman] wrote $CONF_FILE"
fi

export XDG_RUNTIME_DIR="$RUN_BASE"

# Shim `docker` in userspace: /usr/bin/docker (podman-docker shim) prints
# "Emulate Docker CLI using podman. Create /etc/containers/nodocker to
# quiet msg." to STDOUT on every invocation. Tools that capture the stdout
# of `docker`-run commands (e.g. bench probing the container's `pwd`) end
# up with that string embedded in their result, which then gets passed as
# an argument to subsequent execs and breaks them. Our shim goes to podman
# directly with no chatty prefix. We can't `touch /etc/containers/nodocker`
# on CCC without root.
_docker_shim="$HOME/.local/bin/docker"
if [ ! -x "$_docker_shim" ]; then
    mkdir -p "$HOME/.local/bin"
    cat > "$_docker_shim" <<'DOCKER_SHIM'
#!/bin/sh
exec podman "$@"
DOCKER_SHIM
    chmod +x "$_docker_shim"
fi
# Always PREPEND: if $HOME/.local/bin was already in PATH but after /usr/bin,
# our shim wouldn't win the docker lookup. Strip any prior occurrence, then
# prepend so our shim always resolves first.
_new_path=":$PATH:"
_new_path="${_new_path//:$HOME\/.local\/bin:/:}"
_new_path="${_new_path#:}"; _new_path="${_new_path%:}"
export PATH="$HOME/.local/bin:$_new_path"
unset _new_path

# Private DBus session bus. Aardvark-dns (podman's built-in DNS resolver,
# invoked by netavark when a container joins a bridge network) tries to
# talk to a session bus. On compute nodes there's no systemd user
# session, so `/run/user/$UID/bus` doesn't exist and container startup
# fails with "aardvark-dns failed to start: Failed to connect to bus".
# Fix: start our own dbus-daemon and export DBUS_SESSION_BUS_ADDRESS.
_dbus_sock="$RUN_BASE/dbus.sock"
_dbus_pidfile="$RUN_BASE/dbus.pid"
_dbus_alive() {
    [ -S "$_dbus_sock" ] && [ -f "$_dbus_pidfile" ] && \
        kill -0 "$(cat "$_dbus_pidfile")" 2>/dev/null
}
if ! _dbus_alive; then
    pkill -u "$(id -u)" -f "dbus-daemon.*$_dbus_sock" 2>/dev/null || true
    sleep 0.2
    rm -f "$_dbus_sock"
    if command -v dbus-daemon >/dev/null 2>&1; then
        dbus-daemon --session --address="unix:path=$_dbus_sock" --fork \
            --print-pid > "$_dbus_pidfile" 2>"$RUN_BASE/dbus.log"
        for _i in 1 2 3 4 5; do
            [ -S "$_dbus_sock" ] && break
            sleep 0.3
        done
    else
        echo "[setup_podman] WARN: dbus-daemon not found; container DNS may fail"
    fi
fi
export DBUS_SESSION_BUS_ADDRESS="unix:path=$_dbus_sock"

# Rootless podman socket for `docker compose` (and any other Docker API
# client) to talk to. On login nodes systemd user sessions manage this via
# `podman.socket`; on compute nodes there's no systemd user session, so we
# start `podman system service` ourselves as a background process.
#
# Idempotence: SQLite backend can't handle multiple podman services
# writing to the same graphroot — a socket file left behind by a
# previously-killed service passes `-S` but the service is dead. Check
# BOTH socket exists AND a service process is alive; kill all instances
# and start exactly one otherwise.
_sock="$RUN_BASE/podman.sock"
_pidfile="$RUN_BASE/podman-service.pid"
_service_alive() {
    [ -S "$_sock" ] && [ -f "$_pidfile" ] && kill -0 "$(cat "$_pidfile")" 2>/dev/null
}
if ! _service_alive; then
    # Reap any zombie services that leaked from prior sessions before we
    # start a new one, otherwise a stale one holds the DB and the new
    # service's writes fail with "readonly database".
    pkill -u "$(id -u)" -f "^podman system service .*$_sock" 2>/dev/null || true
    sleep 0.2
    rm -f "$_sock"
    nohup podman system service --time=0 "unix://$_sock" \
        >"$RUN_BASE/podman-service.log" 2>&1 &
    echo $! > "$_pidfile"
    disown 2>/dev/null || true
    for _i in 1 2 3 4 5; do
        [ -S "$_sock" ] && break
        sleep 0.3
    done
fi
export DOCKER_HOST="unix://$_sock"

# Second subuid workaround: apt inside the container tries to drop
# privileges to the `_apt` user (UID 42). With no /etc/subuid entry, that
# setuid fails and `apt-get install` dies. Fix: shadow the ubuntu:24.04
# base image locally with an /etc/apt config that tells apt to stay as
# root. Any downstream FROM ubuntu:24.04 inherits this and Just Works.
_patched_marker="$STORAGE_BASE/.patched-ubuntu24-v7"
# v7 (2026-08-21): pre-install uv/uvx to /root/.local/bin AT BUILD TIME so
#   the verifier's `source $HOME/.local/bin/env` and `uvx` calls succeed
#   even if the compute node can't reach https://astral.sh at test time.
#   TAR_OPTIONS=--no-same-owner remains as a belt-and-braces fallback.
# v6 (2026-08-21): add TAR_OPTIONS=--no-same-owner and pre-install uv/uvx
#   to /usr/local/bin. First attempt at unblocking 8+ SkillsBench tasks
#   whose verifier scripts install uv at test time and hit `tar: Cannot
#   change ownership to uid 1001, gid 117: Invalid argument`. Did NOT
#   fix the failure because the verifier hardcodes $HOME/.local/bin/env
#   as its "source" target and calls its own `curl | sh` — which fails
#   silently on compute nodes without outbound access to astral.sh.
if [ ! -f "$_patched_marker" ]; then
    _patch_dockerfile=$(mktemp /tmp/patched-ubuntu.XXXXXX.Dockerfile)
    cat > "$_patch_dockerfile" <<'DOCKERFILE'
FROM docker.io/library/ubuntu:24.04
# 1) apt itself tries to drop privileges to `_apt` (UID 42); without a
#    subuid mapping we can only be UID 0. Tell apt to stay as root.
RUN echo 'APT::Sandbox::User "root";' > /etc/apt/apt.conf.d/00-rootless
# 2) Skip Recommends so we don't drag in build-essential, libgd3,
#    libc-devtools, fontconfig-config — their postinst scripts do
#    chown/adduser to non-root UIDs and fail without subuid.
RUN echo 'APT::Install-Recommends "false";' >> /etc/apt/apt.conf.d/00-rootless
# 3) The MOST COMMON downstream failure: package postinst scripts do
#    `chown fontconfig:root /var/cache/fontconfig` or similar, which
#    fails with "Invalid argument" in our single-UID user namespace.
#    Wrap chown/chgrp to swallow ownership errors — the file itself is
#    created fine, only the ownership call fails. Same for useradd's
#    setgid step (via wrapping the binary or by pre-creating users). We
#    wrap chown+chgrp; useradd/groupadd typically also fail-open with
#    warnings that dpkg accepts.
RUN set -e; \
    for bin in /usr/bin/chown /usr/bin/chgrp \
               /usr/sbin/useradd /usr/sbin/groupadd \
               /usr/sbin/usermod /usr/sbin/groupmod \
               /usr/sbin/adduser /usr/sbin/addgroup \
               /usr/sbin/dpkg-statoverride /usr/bin/dpkg-statoverride; do \
        [ -x "$bin" ] || continue; \
        mv "$bin" "${bin}.real"; \
        printf '%s\n' '#!/bin/sh' "${bin}.real \"\$@\" 2>/dev/null || :" > "$bin"; \
        chmod +x "$bin"; \
    done
# 4) Pre-install what most SkillsBench Dockerfiles ask for. Downstream
#    `apt-get install python3 python3-pip curl poppler-utils` finds the
#    common ones present and only fetches deltas. build-essential is
#    heavy (~500 MB) but multiple tasks need it; better to pay once here
#    than on every rollout's image build.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3 python3-pip curl \
        poppler-utils \
        build-essential ca-certificates \
    && rm -rf /var/lib/apt/lists/*
# 5) TAR_OPTIONS=--no-same-owner (SkillsBench verifier fix, 2026-08-21).
#    Many SkillsBench verifiers install `uv` at test time by extracting
#    a tarball whose entries carry uid=1001/gid=117 (uv's original build
#    user). Rootless podman with a single-UID user namespace cannot map
#    to those uids, so `tar xf` fails with "Cannot change ownership".
#    GNU tar honors TAR_OPTIONS globally; setting it in /etc/environment
#    plus /etc/profile.d makes every login and non-login shell inherit
#    the flag. This unblocks any downstream tarball extraction.
RUN echo 'TAR_OPTIONS="--no-same-owner"' >> /etc/environment && \
    printf '%s\n' 'export TAR_OPTIONS="--no-same-owner"' \
        > /etc/profile.d/tar-no-same-owner.sh && \
    chmod +x /etc/profile.d/tar-no-same-owner.sh
ENV TAR_OPTIONS=--no-same-owner
# 6) Pre-install uv/uvx to BOTH /usr/local/bin (system-wide) and
#    /root/.local/bin (SkillsBench-verifier-expected location).
#    (SkillsBench verifier fix, 2026-08-21 v7 revision.)
#
#    Many SkillsBench verifier test.sh scripts hardcode this pattern:
#        curl -LsSf https://astral.sh/uv/<ver>/install.sh | sh > /dev/null 2>&1
#        source $HOME/.local/bin/env
#        uvx --with pytest ...
#    On CCC compute nodes:
#      (a) The verifier's `curl` step frequently FAILS silently — either
#          the compute node has no outbound access to astral.sh, or the
#          tar-extract hits "Cannot change ownership to uid 1001, gid 117"
#          in rootless podman's single-UID user namespace. Both fail
#          because of `> /dev/null 2>&1`.
#      (b) When (a) fails, $HOME/.local/bin/env doesn't exist, `source`
#          errors out, and `uvx: command not found`.
#      (c) Even if uv is on system PATH (/usr/local/bin), verifier's
#          `source $HOME/.local/bin/env` STILL fails, and PATH-lookup for
#          `uvx` happens BEFORE (not after) source, so system uv isn't
#          reached.
#
#    Fix: bake the exact files the verifier expects at build time. The
#    astral install.sh honors HOME to pick its dest dir, so setting
#    HOME=/root during the RUN puts uv, uvx, and (crucially) the `env`
#    activation script at /root/.local/bin/. Then the verifier's
#    hardcoded `source $HOME/.local/bin/env` succeeds without needing
#    network access at test time.
#
#    We ALSO install to /usr/local/bin as belt-and-braces (verifier for
#    tasks that expect system-level uvx). Both install steps are
#    non-fatal — TAR_OPTIONS above still allows verifier's own install
#    to succeed if the compute node has network reach.
# Pinned: an unpinned installer makes image contents drift silently between
# rebuilds, and the SkillsBench verifiers this unblocks pin uv themselves
# (see CCC_PODMAN_SETUP.md §C.1). Bump UV_VERSION deliberately.
ARG UV_VERSION=0.9.7
RUN curl -LsSf "https://astral.sh/uv/${UV_VERSION}/install.sh" | \
    env UV_INSTALL_DIR=/usr/local/bin UV_UNMANAGED_INSTALL=1 sh || \
    echo "warn: uv preinstall to /usr/local/bin failed; verifier fallback via /root/.local/bin"
RUN curl -LsSf "https://astral.sh/uv/${UV_VERSION}/install.sh" | env HOME=/root sh || \
    echo "warn: uv preinstall to /root/.local/bin failed; verifier will attempt its own install"
DOCKERFILE
    # Force the tag off any pre-existing local image before rebuilding.
    podman rmi -f docker.io/library/ubuntu:24.04 >/dev/null 2>&1 || true
    if podman build \
        -t docker.io/library/ubuntu:24.04 \
        -f "$_patch_dockerfile" \
        "$(dirname "$_patch_dockerfile")" >"$RUN_BASE/patched-ubuntu-build.log" 2>&1; then
        touch "$_patched_marker"
        echo "[setup_podman] patched ubuntu:24.04 for apt-in-rootless (log: $RUN_BASE/patched-ubuntu-build.log)"
    else
        echo "[setup_podman] WARN: could not pre-patch ubuntu:24.04; container builds may fail on apt (log: $RUN_BASE/patched-ubuntu-build.log)"
    fi
    rm -f "$_patch_dockerfile"
fi

# Sanity summary (previously interactive-only; now always emitted so batch
# runs get a non-empty setup.log for post-mortem).
echo "[setup_podman] XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR"
echo "[setup_podman] graphroot=$STORAGE_BASE"
echo "[setup_podman] DOCKER_HOST=$DOCKER_HOST"
echo "[setup_podman] DBUS_SESSION_BUS_ADDRESS=$DBUS_SESSION_BUS_ADDRESS"
echo "[setup_podman] PATH first entry: $(echo "$PATH" | cut -d: -f1)"
echo "[setup_podman] try: podman info | head -30"

unset _uid _desired _sock _i _patched_marker _patch_dockerfile _pidfile
unset _dbus_sock _dbus_pidfile _docker_shim
# These four have generic names and this script is sourced into a shell the
# user keeps working in — don't leave them behind.
unset STORAGE_BASE RUN_BASE CONF_DIR CONF_FILE
unset -f _service_alive _dbus_alive 2>/dev/null || true
