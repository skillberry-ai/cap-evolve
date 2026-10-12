#!/usr/bin/env bash
# E26-nohist variant: only the proposer cwd + project (ro) + a COPY of rejected.jsonl + a per-invocation config dir are visible; the rest of the run dir (candidates, rollouts, events, other work dirs, earlier transcripts, frozen, metrics) is NOT mounted. Transcripts are copied out to $W/claude_cfg/projects after the call.
# Mount-namespace sandbox shim for the optimizer `claude` (Suite B, E10B). Rootless: unshare --user --map-root-user --mount.
# Inside: /home/dev is an EMPTY tmpfs except (rw) the run workdir $E10B_W, and (ro) the claude install, the tau2 venv, tau2 src/,
# wt-tau core+skills, and a data overlay $E10B_W/sbx_data (db.json + policy.md; for agent-optimize also a tasks.json FILTERED to opt+sel).
# Sealed tau2 test gold, protocol/, splits, ~/.claude, other runs and credentials are invisible. Env is allowlisted; the key is the metering tag in ANTHROPIC_API_KEY only.
set -euo pipefail
: "${E10B_W:?E10B_W (run workdir) required}"
W=$(readlink -f "$E10B_W"); B=/home/dev/projects2/campaign-scratch; WT=/home/dev/projects2/wt-tau
case "${ANTHROPIC_API_KEY:-}" in tag:*) ;; *) echo "shim: ANTHROPIC_API_KEY must be a tag: token" >&2; exit 97;; esac
ENVV=(); for v in $(compgen -e); do case "$v" in PATH|LANG|TERM|ANTHROPIC_BASE_URL|ANTHROPIC_API_KEY|ANTHROPIC_MODEL|BASH_*|CAPEVOLVE_*|TAU_*|TAU2_*|MAX_TOKENS|PYTHONPATH|PYTHONDONTWRITEBYTECODE|E10B_*|DISABLE_*) ENVV+=("$v=${!v}");; esac; done
ENVV+=("HOME=/tmp/home" "TMPDIR=/tmp/home/tmp" "CLAUDE_CONFIG_DIR=/home/dev/.cfg_nohist")
export SBX_W="$W" SBX_PWD="$PWD"
unshare --user --map-root-user --mount --net bash -c '
set -e
S=/tmp/sbxstage.$$; mkdir -p $S; mount -t tmpfs none $S
W="$SBX_W"; B='$B'; WT='$WT'
m() { mkdir -p "$S/$2"; mount --rbind "$1" "$S/$2"; }
mkdir -p "$W/claude_cfg/projects"; exec 9<"$W/claude_cfg/projects"          # real transcript dir, kept as fd 9 for copy-out
cp /home/dev/projects2/campaign-scratch/runs/E26/PROCESS.seed.md $S/process_seed.md; mkdir -p $S/w_cwd $S/w_proj $S/cfg; mount --rbind "$SBX_PWD" $S/w_cwd; mount --rbind "$W/.capevolve/project" $S/w_proj
for f in "$W"/claude_cfg/* ; do [ "$(basename "$f")" = projects ] || cp -a "$f" $S/cfg/ ; done
RJ="$W/.capevolve/run_main/rejected.jsonl"; if [ -f "$RJ" ]; then cp "$RJ" $S/rejected.jsonl; fi
m /home/dev/.local/share/claude cl; m /home/dev/.local/bin lb; m $B/bench/venv-tau2-8ebb749 venv; m $B/bench/src/tau2-8ebb749/src tsrc
m $W/sbx_data tdata; m $WT/core wtcore; m $B/baselines/gwbridge gwb; m $WT/skills wtskills; m $WT/docs/archive wtdocs; m $B/bench/local blocal
mount -t tmpfs none /home/dev
mkdir -p "$SBX_PWD" "$W/.capevolve/project"; mount --rbind $S/w_cwd "$SBX_PWD"; 
# carry-over scrub: a child of an ACCEPTED candidate starts from the snapshot of that candidate, which includes its filled PROCESS.md and DIAGNOSIS.json = history. Reset them.
cp $S/process_seed.md "$SBX_PWD/PROCESS.md"; rm -f "$SBX_PWD/DIAGNOSIS.json"
mount --rbind $S/w_proj "$W/.capevolve/project"
mount -o remount,bind,ro "$W/.capevolve/project" 2>/dev/null || true
mkdir -p /home/dev/.cfg_nohist; mount --rbind $S/cfg /home/dev/.cfg_nohist
if [ -f $S/rejected.jsonl ]; then mkdir -p "$W/.capevolve/run_main"; cp $S/rejected.jsonl "$W/.capevolve/run_main/rejected.jsonl"; fi
b() { mkdir -p "$2"; mount --rbind "$S/$1" "$2"; }
b cl /home/dev/.local/share/claude; b lb /home/dev/.local/bin; b venv $B/bench/venv-tau2-8ebb749; b tsrc $B/bench/src/tau2-8ebb749/src
b tdata $B/bench/src/tau2-8ebb749/data; b wtcore $WT/core; b gwb $B/baselines/gwbridge; b wtskills $WT/skills; b wtdocs $WT/docs/archive; b blocal $B/bench/local
for p in /home/dev/.local/share/claude /home/dev/.local/bin $B/bench/venv-tau2-8ebb749 $B/bench/src/tau2-8ebb749/src $B/bench/src/tau2-8ebb749/data $WT/core $WT/skills $WT/docs/archive $B/bench/local; do mount -o remount,bind,ro "$p"; done
SC="$W/.capevolve/project/seed_capability"; if [ -d "$SC" ]; then mount --bind "$SC" "$SC"; mount -o remount,bind,ro "$SC"; fi
mount -t tmpfs none /tmp; mount -t tmpfs none /var/tmp; mount -t tmpfs none /dev/shm 2>/dev/null || true
umount -l $S 2>/dev/null || true
mkdir -p /tmp/home/tmp
ip link set lo up 2>/dev/null || /usr/sbin/ip link set lo up
/usr/bin/python3 $B/baselines/gwbridge/gw_bridge.py inside $B/baselines/gwbridge/gw.sock 4111 >/dev/null 2>&1 &
FW=$!
for i in $(seq 1 40); do (echo > /dev/tcp/127.0.0.1/4111) 2>/dev/null && break; sleep 0.25; done
cd "$SBX_PWD"
set +e; env -i "$@" 9<&-; rc=$?; cp -a /home/dev/.cfg_nohist/projects/. /proc/self/fd/9/ 2>/dev/null; kill $FW 2>/dev/null; exit $rc' bash "${ENVV[@]}" "${SBX_EXEC:-/home/dev/.local/bin/claude}" "$@"
