#!/usr/bin/env bash
# Run an exp895 search ONLY if no other exp895 job of this user is on this host (podman state is per user per
# host: two of our podman jobs on one host corrupt each other; CCC_PODMAN_SETUP.md, memory "dedicated hosts").
# If the host is taken, exit 99 WITHOUT starting anything; the submitter turns exit 99 into a requeue (bsub -Q "99").
#
# The check is an atomic per-host LOCK, not a bjobs query. A bjobs check raced: jobs dispatched within the same
# second each saw the other as not-yet-running and both started (2026-10-22, 4 hosts). mkdir is atomic; the lock
# dir sits on the host-local /tmp and records the owning LSF job id, and a lock whose job is no longer RUN on this
# host is stale and is taken over.
#   Usage: lsf_exclusive_wrapper.sh <launcher.sh>      (SEED, R, NAME, ... passed through the environment)
set -uo pipefail
me="${LSB_JOBID:?must run under LSF}"; host="$(hostname -s)"
case "$host" in ccc-login*) echo "refusing to run on a login node" >&2; exit 2;; esac
LOCK="/tmp/exp895-host-lock-$(id -u)"

take() { mkdir "$LOCK" 2>/dev/null && echo "$me" > "$LOCK/owner"; }
if ! take; then
  owner=$(cat "$LOCK/owner" 2>/dev/null || echo "")
  # mkdir and writing the owner are two steps: an empty owner usually means its job is between them. Wait, re-read.
  for _ in 1 2 3 4 5; do [ -n "$owner" ] && break; sleep 2; owner=$(cat "$LOCK/owner" 2>/dev/null || echo ""); done
  if [ -n "$owner" ] && [ "$owner" != "$me" ] && \
     bjobs -noheader -o 'stat exec_host' "$owner" 2>/dev/null | awk -v h="$host" '($1=="RUN" || $1=="USUSP") && index($2,h)' | grep -q .; then
    echo "$(date -u +%FT%TZ) host $host is locked by running exp895 job $owner; requeueing $me" >&2
    exit 99
  fi
  # A lock younger than 5 min is never stale (2026-10-25): two jobs dispatched in the same second saw each other as
  # not-yet-RUN in bjobs, so the second one "reclaimed" the first one's fresh lock and both ran on cccxc542.
  age=$(( $(date +%s) - $(stat -c %Y "$LOCK" 2>/dev/null || date +%s) ))
  if [ "$age" -lt 300 ]; then
    echo "$(date -u +%FT%TZ) host $host has a fresh exp895 lock (${age}s, owner ${owner:-?}); requeueing $me" >&2
    exit 99
  fi
  # stale lock (its job finished, was killed, or never wrote an owner): reclaim it atomically
  rm -rf "$LOCK" && take || { echo "$(date -u +%FT%TZ) lost the lock race on $host; requeueing $me" >&2; exit 99; }
fi
trap 'rm -rf "$LOCK"' EXIT
# Belt and braces: jobs started before the lock existed (2026-10-22 06:38-06:43Z) hold no lock, so also refuse when
# bjobs shows any OTHER running exp895 job here. An older job is always visible to bjobs; only simultaneous
# dispatch raced, and the lock above covers that. If two new jobs see each other, both requeue, which is safe.
others=$(bjobs -noheader -w -u "$USER" 2>/dev/null | awk -v me="$me" -v h="$host" \
  '$1!=me && $3!="PEND" && $7 ~ /^exp895_/ && index($6, h) {print $1}')   # RUN and USUSP (frozen jobs keep their podman state)
if [ -n "$others" ]; then
  echo "$(date -u +%FT%TZ) host $host already runs exp895 job(s) $others; requeueing $me" >&2
  exit 99
fi
bash "$1"
