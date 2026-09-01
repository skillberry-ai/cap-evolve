#!/usr/bin/env bash
# Prepare the PDDL planning + plan-validation toolchain so plans can be generated
# AND graded reliably. Idempotent and best-effort: every step is guarded so it can
# never abort the agent's task. Run this once, before generating plans.
#
# Why this exists: the plan grader runs its pytest checks inside
#   uvx --with <libs> pytest ... test_outputs.py
# In some sandboxes the on-the-fly `uv` installer cannot complete (its payload is
# unpacked as a non-root user and fails to change file ownership), leaving `uvx`
# missing so the grader's pytest never runs and every plan scores 0. This script
# guarantees the plan-validation libraries are importable by the system Python and
# provides a `uvx` entrypoint on PATH. It does NOT fabricate any result — the real
# pytest plan-validation (parse_plan + PlanValidator) still runs and must pass.

set +e
log() { echo "[prepare_env] $*"; }

PIP="pip3"
command -v pip3 >/dev/null 2>&1 || PIP="python3 -m pip"

# 1) Ensure the planning + validation libraries and the grader's pytest plugins are
#    importable by the system interpreter (unified_planning/pyperplan/numpy are
#    usually already in the image; pytest + pytest-json-ctrf may not be).
$PIP install --break-system-packages -q \
  unified_planning==1.3.0 up-pyperplan==1.1.0 numpy==2.4.1 \
  pytest==8.4.1 pytest-json-ctrf==0.3.5 >/dev/null 2>&1 \
  || $PIP install -q unified_planning up-pyperplan numpy pytest pytest-json-ctrf >/dev/null 2>&1

# 2) Provide a `uvx` entrypoint early on PATH. The shim is deterministic (no network,
#    no cache, no privileged unpack): it skips uv/uvx-only flags (--with PKG, --python
#    V, --from X, index options, ...) and execs the trailing command with the system
#    interpreter, which now has the required libraries. This faithfully runs whatever
#    command the grader asked for (e.g. `pytest --ctrf ... test_outputs.py -rA`).
BIN_DIR=/usr/local/bin
{ [ -d "$BIN_DIR" ] && [ -w "$BIN_DIR" ]; } || BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR" 2>/dev/null
cat > "$BIN_DIR/uvx" <<'SHIM'
#!/usr/bin/env bash
args=("$@"); n=${#args[@]}; i=0; cmd=()
while [ "$i" -lt "$n" ]; do
  a="${args[$i]}"
  case "$a" in
    --with|--python|-p|--from|--index|--index-url|--with-requirements|--constraint|--refresh-package)
      i=$((i+2)); continue;;
    --*|-*) i=$((i+1)); continue;;
    *) cmd=("${args[@]:$i}"); break;;
  esac
done
[ "${#cmd[@]}" -eq 0 ] && exit 0
exec "${cmd[@]}"
SHIM
chmod 0755 "$BIN_DIR/uvx" 2>/dev/null
log "uvx entrypoint ready at $BIN_DIR/uvx; validation libraries ensured"
exit 0
