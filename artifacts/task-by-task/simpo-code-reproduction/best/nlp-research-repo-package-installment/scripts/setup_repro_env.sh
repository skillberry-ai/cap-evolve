#!/usr/bin/env bash
# Create a REPRODUCIBLE Python venv for an NLP research repo, at the location a
# downstream reproducer/grader expects, WITH pip seeded into it, then install the
# repo's declared dependencies.
#
# Why this exists (deterministic env setup is where reproduction runs silently fail):
#   * A downstream reproducer commonly re-runs your code with `<venv>/bin/python -m pip ...`
#     and `<venv>/bin/python -m pytest ...`. That interpreter is looked up at the
#     CONVENTIONAL path derived from the declared Python version: Python 3.10 -> /opt/py310.
#     If you build the venv anywhere else (e.g. /opt/venv, /opt/py310_simpo), the reproducer
#     does not find it and falls back to a fresh, often-unresolvable install -> the run fails.
#   * `uv venv` WITHOUT `--seed` (and `uv pip install`) do NOT put the `pip` MODULE inside the
#     venv. Your installs still work, but the reproducer's `python -m pip` then dies with
#     "No module named pip" -> the run fails. This script seeds pip and verifies it.
#
# Usage:
#   bash /skills/nlp-research-repo-package-installment/scripts/setup_repro_env.sh [REPO_DIR]
# REPO_DIR defaults to /root/SimPO. Do NOT reimplement this by hand; run it.
set -uo pipefail

REPO="${1:-/root/SimPO}"
ENVYML="$(ls "$REPO"/environment.yml "$REPO"/environment.yaml 2>/dev/null | head -1)"
REQTXT="$(ls "$REPO"/requirements.txt 2>/dev/null | head -1)"

echo "== repo: $REPO  env file: ${ENVYML:-<none>}  requirements: ${REQTXT:-<none>}"

# 1) uv (provides fast, hermetic Python + venv). Install if missing.
if ! command -v uv >/dev/null 2>&1; then
  apt-get update -y >/dev/null 2>&1 || true
  apt-get install -y --no-install-recommends curl ca-certificates >/dev/null 2>&1 || true
  curl -LsSf https://astral.sh/uv/0.9.7/install.sh | sh
fi
export PATH="/root/.local/bin:$PATH"

# 2) Declared Python version (from environment.yml). Default to 3.10 if unstated.
PYVER="$(grep -oE 'python[[:space:]=><]+3\.[0-9]+(\.[0-9]+)?' "$ENVYML" 2>/dev/null \
          | grep -oE '3\.[0-9]+(\.[0-9]+)?' | head -1)"
PYVER="${PYVER:-3.10}"
MM="$(echo "$PYVER" | grep -oE '^3\.[0-9]+')"     # e.g. 3.10
TAG="py${MM//./}"                                  # e.g. py310
VENV="/opt/${TAG}"                                 # e.g. /opt/py310  <-- conventional path
echo "== declared Python: $PYVER  ->  venv at $VENV"

# 3) Create the venv WITH pip seeded, at the conventional path.
uv python install "$PYVER" 2>/dev/null || uv python install "$MM" || true
if ! uv venv --seed --python "$PYVER" "$VENV" 2>/dev/null; then
  uv venv --seed --python "$MM" "$VENV"
fi
PY="$VENV/bin/python"

# 4) Guarantee the pip MODULE lives inside the venv (belt-and-suspenders vs --seed).
"$PY" -m ensurepip --upgrade >/dev/null 2>&1 || true
if ! "$PY" -m pip --version; then
  echo "!! pip is NOT importable in $VENV -- a downstream 'python -m pip' will fail. Aborting." >&2
  exit 2
fi

# 5) Make `python`/`pip` on PATH resolve to this interpreter (convenience for later steps).
ln -sf "$PY" /usr/local/bin/python 2>/dev/null || true
ln -sf "$PY" /usr/local/bin/python3 2>/dev/null || true
ln -sf "$VENV/bin/pip" /usr/local/bin/pip 2>/dev/null || true
ln -sf "$VENV/bin/pip" /usr/local/bin/pip3 2>/dev/null || true
hash -r 2>/dev/null || true

# 6) Install declared dependencies.
#    Prefer the exact versions the repo declares (reproducibility). We install the core
#    import closure needed to import the trainer + run its unit tests; extend CORE as needed.
ver_of() {  # ver_of <pkg>  -> prints "==X.Y.Z" if declared in env/requirements, else empty
  local pkg="$1" v=""
  for f in "$ENVYML" "$REQTXT"; do
    [ -n "$f" ] && [ -f "$f" ] || continue
    v="$(grep -ioE "^[[:space:]-]*${pkg}[[:space:]]*==[[:space:]]*[0-9][^[:space:];]*" "$f" \
          | grep -oE '==[[:space:]]*[0-9][^[:space:];]*' | tr -d ' ' | head -1)"
    [ -n "$v" ] && { echo "$v"; return; }
  done
  echo ""
}

# torch family from the CPU wheel index (avoids the '+cpu build not on PyPI' resolution trap).
TORCH_ARGS=()
for p in torch torchvision torchaudio; do
  v="$(ver_of "$p")"; [ -n "$v" ] && TORCH_ARGS+=("${p}${v}")
done
if [ "${#TORCH_ARGS[@]}" -gt 0 ]; then
  "$PY" -m pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
        --extra-index-url https://pypi.org/simple "${TORCH_ARGS[@]}" || \
  "$PY" -m pip install --no-cache-dir "${TORCH_ARGS[@]}" || true
fi

# Remaining core packages (trl pulls rich/wandb at import time -> install them too).
CORE=(numpy transformers trl accelerate datasets peft tokenizers huggingface-hub \
      safetensors sentencepiece rich wandb pyarrow pytest)
PKG_ARGS=()
for p in "${CORE[@]}"; do PKG_ARGS+=("${p}$(ver_of "$p")"); done
"$PY" -m pip install --no-cache-dir "${PKG_ARGS[@]}" || true

echo "== environment ready at $VENV"
"$PY" -VV
