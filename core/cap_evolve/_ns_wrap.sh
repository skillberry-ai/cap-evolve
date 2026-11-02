#!/usr/bin/env bash
# Run one optimizer command in a private mount namespace (cap_evolve/isolation.py, mode "namespace").
#
#   CE_ISO_HIDE=<paths, one per line> CE_ISO_EXPOSE=<paths> CE_ISO_WORK=<workdir> _ns_wrap.sh CMD ARGS...
#
# Each hidden directory becomes an empty tmpfs; an exposed path under it is bound back read-only and
# the working dir under it read-write. Each hidden file is covered by an empty file. The command then
# runs in a nested user namespace as the calling user, so it cannot unmount any of this, and
# /proc/<pid>/root of processes outside is refused. Needs Linux with unprivileged user namespaces.
set -euo pipefail
[ $# -gt 0 ] || { echo "_ns_wrap.sh: no command" >&2; exit 2; }
UID_="$(id -u)"; GID_="$(id -g)"
BASE="$(mktemp -d "${TMPDIR:-/tmp}/ce_iso.XXXXXX")"
# exact clean-up: the files this script made, then its (now empty) dirs
cleanup() { rm -f "$BASE/empty" "$BASE/inner.sh"; for d in "$BASE"/stage*; do [ -d "$d" ] && rmdir "$d"; done; rmdir "$BASE"; } 2>/dev/null
trap cleanup EXIT
: > "$BASE/empty"

INNER="$BASE/inner.sh"
cat > "$INNER" <<'EOF'
set -euo pipefail
under() { case "$1/" in "$2"/*) return 0 ;; esac; return 1; }   # is $1 at or below $2?
mapfile -t HIDE < <(printf '%s\n' "$CE_ISO_HIDE" | sed '/^$/d' | awk '{print length, $0}' | sort -n | cut -d' ' -f2-)
mapfile -t EXPOSE < <(printf '%s\n' "${CE_ISO_EXPOSE:-}" | sed '/^$/d')
for h in "${HIDE[@]}"; do
  if under "$(readlink -m "$BASE")" "$(readlink -m "$h")"; then
    echo "_ns_wrap.sh: TMPDIR ($BASE) is inside hidden path $h; set TMPDIR elsewhere" >&2; exit 3
  fi
done
done_dirs=()
i=0
for h in "${HIDE[@]}"; do
  h="$(readlink -m "$h")"
  skip=0; for d in "${done_dirs[@]+"${done_dirs[@]}"}"; do under "$h" "$d" && skip=1; done
  [ "$skip" = 1 ] && continue
  if [ -d "$h" ]; then
    i=$((i + 1)); s="$BASE/stage$i"; mkdir "$s"
    mount --bind "$h" "$s"
    mount -t tmpfs -o mode=755 tmpfs "$h"
    for e in "${EXPOSE[@]+"${EXPOSE[@]}"}"; do
      e="$(readlink -m "$e")"; under "$e" "$h" || continue; [ -e "$s/${e#"$h"/}" ] || continue
      rel="${e#"$h"/}"
      if [ -d "$s/$rel" ]; then mkdir -p "$h/$rel"; else mkdir -p "$(dirname "$h/$rel")"; : > "$h/$rel"; fi
      mount --bind "$s/$rel" "$h/$rel"; mount -o remount,bind,ro "$h/$rel"
    done
    if under "$CE_ISO_WORK" "$h"; then
      rel="${CE_ISO_WORK#"$h"/}"; [ "$CE_ISO_WORK" = "$h" ] && rel=""
      mkdir -p "$h/$rel"; mount --bind "$s/$rel" "$h/$rel"
    fi
    umount -l "$s"
    done_dirs+=("$h")
  elif [ -f "$h" ]; then
    mount --bind "$BASE/empty" "$h"
  fi
done
cd "$CE_ISO_WORK"
exec unshare -U --map-user="$UID_" --map-group="$GID_" "$@"
EOF

UID_="$UID_" GID_="$GID_" BASE="$BASE" unshare -rm --propagation private bash "$INNER" "$@"
