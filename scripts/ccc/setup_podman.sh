#!/bin/bash
#
# Podman setup for CCC.
#
# Usage:
#   source <path-to-cap-evolve>/scripts/ccc/setup_podman.sh
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
# STORAGE_BASE="/dccstor/<your-project>/<your-user>/.podman-$(hostname)"
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
_patched_marker="$STORAGE_BASE/.patched-ubuntu24-v5"
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
        build-essential \
    && rm -rf /var/lib/apt/lists/*
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
unset -f _service_alive _dbus_alive 2>/dev/null || true
