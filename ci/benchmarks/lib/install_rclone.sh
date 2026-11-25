#!/usr/bin/env bash
# Install a pinned rclone into a user-writable prefix on the runner, for backup_run.sh's staging
# upload. Idempotent: does nothing when that version is already there. No sudo, no package manager.
#
#   install_rclone.sh            installs to $RCLONE_PREFIX/bin (default $HOME/.local/bin)
#
# The release is pinned by version AND by the sha256 of its zip, taken from the release's own
# SHA256SUMS (https://downloads.rclone.org/v<version>/SHA256SUMS). A download whose hash differs is
# refused. To move to a newer release, change RCLONE_VERSION and both hashes together, from that file.
#
# Exit status: 0 when rclone $RCLONE_VERSION is installed (or already was); 1 otherwise, with a
# ::warning:: — the caller treats a missing rclone as "staging failed, keep the capture on the runner".
set -uo pipefail

RCLONE_VERSION="1.76.0"
declare -A SHA256=(
  [amd64]="b00f00b3266c3764413afe599d3ec316f6f43b3e0ea8a0bc1d186d2133e46df7"
  [arm64]="ee169016675e23a69d77240565133ff7dbc9b33d16fa8f7053d4af39f1eaeb78"
)
PREFIX="${RCLONE_PREFIX:-$HOME/.local}"
BIN="$PREFIX/bin/rclone"
PY="${PY:-python3}"
BASE_URL="${RCLONE_BASE_URL:-https://downloads.rclone.org}"

warn() { echo "::warning::install_rclone: $*"; exit 1; }

if [ -x "$BIN" ] && "$BIN" version 2>/dev/null | head -1 | grep -qxF "rclone v$RCLONE_VERSION"; then
  echo "install_rclone: rclone v$RCLONE_VERSION already at $BIN"; exit 0
fi

case "$(uname -s)-$(uname -m)" in
  Linux-x86_64)          arch=amd64 ;;
  Linux-aarch64|Linux-arm64) arch=arm64 ;;
  *) warn "no pinned rclone build for $(uname -s)-$(uname -m)" ;;
esac
zip="rclone-v$RCLONE_VERSION-linux-$arch.zip"
tmp="$(mktemp -d)" || warn "cannot create a temp dir"
trap 'rm -rf "$tmp"' EXIT

curl -fsSL -m 300 --retry 3 -o "$tmp/$zip" "$BASE_URL/v$RCLONE_VERSION/$zip" || warn "download of $zip failed"
got="$(sha256sum "$tmp/$zip" 2>/dev/null | awk '{print $1}')"
[ "$got" = "${SHA256[$arch]}" ] || warn "$zip has sha256 $got, expected ${SHA256[$arch]}; not installed"

# unzip may be missing on the runner; Python's zipfile is always there.
"$PY" - "$tmp/$zip" "$tmp/rclone" "rclone-v$RCLONE_VERSION-linux-$arch/rclone" <<'PY' || warn "cannot unpack $zip"
import shutil, sys, zipfile
src, dst, member = sys.argv[1:]
with zipfile.ZipFile(src) as z, z.open(member) as f, open(dst, "wb") as out:
    shutil.copyfileobj(f, out)
PY
mkdir -p "$PREFIX/bin" || warn "cannot create $PREFIX/bin"
chmod 0755 "$tmp/rclone" && mv -f "$tmp/rclone" "$BIN" || warn "cannot install $BIN"
"$BIN" version 2>/dev/null | head -1 | grep -qxF "rclone v$RCLONE_VERSION" || warn "$BIN does not run"
echo "install_rclone: installed rclone v$RCLONE_VERSION at $BIN"
