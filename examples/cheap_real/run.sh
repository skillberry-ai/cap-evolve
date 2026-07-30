#!/usr/bin/env bash
# cheap_real — the "step 2" rung: a REAL LLM run in minutes, for $0 (local) or cents.
#
# Usage: cd <repo-root> && bash examples/cheap_real/run.sh
#
# Programmatic entry point (this is the contract #133's quickstart calls). Every knob
# is an env var with a default; the last object on stdout is the run's summary JSON:
#
#   CHEAP_REAL_MODEL      litellm model string        (default ollama/llama3.2:3b — free, local)
#   CHEAP_REAL_API_BASE   endpoint for that model     (default http://localhost:11434)
#   CHEAP_REAL_OPTIMIZER  who proposes the edit       (default mock — zero-API/$0)
#   CHEAP_REAL_OPT_MODEL  optimizer/proposer model    (default "" — mock needs none)
#   CHEAP_REAL_WORKDIR    where to run                (default a fresh mktemp dir)
#   CHEAP_REAL_MAX_USD    hard $ stop                 (default from capevolve.yaml: 2.0)
#   CHEAP_REAL_PYTHON     interpreter                 (default python3 — must have litellm)
#
# The three rungs, and how to get each (costs + derivation in docs/GETTING_STARTED.md):
#   free   ollama + mock optimizer   — the default below
#   cheap  ollama + a real agent     — CHEAP_REAL_OPTIMIZER=claude-code
#   hosted a hosted runner model     — CHEAP_REAL_MODEL=claude-haiku-4-5 (+ its credential)
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
EX="$REPO/examples/cheap_real"
PY="${CHEAP_REAL_PYTHON:-python3}"

export CAPEVOLVE_CORE="$REPO/core"
export PYTHONPATH="$REPO/core"
export CAPEVOLVE_SKILLS_DIR="$REPO/skills"
export CAPEVOLVE_MOCK_SCRIPT="$EX/mock_script.json"

# The runner's model wiring. `model_config.py` (copied in below) reads these; the
# provider-agnostic MODEL= switch is the whole point — no adapter edit to change model.
export MODEL="${CHEAP_REAL_MODEL:-ollama/llama3.2:3b}"
export API_BASE="${CHEAP_REAL_API_BASE:-http://localhost:11434}"
export SCORING=exact

# Preflight, because the adapter turns a failed model call into `error:` + reward 0.0 —
# correct behavior (infra noise must not be optimized against), but it means a missing
# dep or a stopped Ollama yields a clean-looking run whose every number is 0.0. A real
# run must be distinguishable from a broken one BEFORE anything is spent. The endpoint
# is never echoed: since #134 a non-default base URL is confidential.
"$PY" - <<'PRE'
import os, sys, urllib.error, urllib.request
try:
    import litellm  # noqa: F401
except ImportError:
    sys.exit("cheap_real preflight: litellm is not importable by this interpreter. "
             "`pip install litellm`, or point CHEAP_REAL_PYTHON at one that has it.")
if os.environ.get("MODEL", "").startswith("ollama/"):
    base, model = os.environ["API_BASE"].rstrip("/"), os.environ["MODEL"].split("/", 1)[1]
    try:
        with urllib.request.urlopen(base + "/api/tags", timeout=5) as r:
            names = {m.get("name", "") for m in __import__("json").load(r).get("models", [])}
    except (urllib.error.URLError, OSError, ValueError) as e:
        sys.exit(f"cheap_real preflight: the local Ollama endpoint did not answer "
                 f"({type(e).__name__}). Start it (`ollama serve`) or set CHEAP_REAL_MODEL "
                 f"to a hosted model. Endpoint withheld (see docs/TROUBLESHOOTING.md).")
    if model not in names and f"{model}:latest" not in names:
        sys.exit(f"cheap_real preflight: Ollama is up but does not have {model!r}. "
                 f"Run `ollama pull {model}` (~2 GB), or set CHEAP_REAL_MODEL.")
print("cheap_real preflight: OK")
PRE

D="${CHEAP_REAL_WORKDIR:-$(mktemp -d -t cheap_real.XXXXXX)}"
mkdir -p "$D/.capevolve/project/adapters"
# Reuse the bundled generic template verbatim — this example adds NO adapter code.
# Both files land in adapters/ and the dataset inside the project dir, deliberately:
# #142/#197's guard can only hash paths under the project dir, and `adapters/` +
# the spec's `dataset_source` are two of its layout DEFAULTS. So every file the
# grader depends on is protected without the preset declaring `protected_paths` —
# which is what lets it omit that key (an empty list is now a hard error).
cp "$REPO/templates/adapters/jsonl_litellm/adapter.py" "$D/.capevolve/project/adapters/"
cp "$REPO/templates/adapters/model_config.py"          "$D/.capevolve/project/adapters/"
cp "$EX/tasks.jsonl"    "$D/.capevolve/project/tasks.jsonl"
cp -R "$EX/capability" "$D/.capevolve/project/seed_capability"
cp "$EX/capevolve.yaml" "$D/.capevolve/project/capevolve.yaml"
export TASKS_FILE="$D/.capevolve/project/tasks.jsonl"

OPT="${CHEAP_REAL_OPTIMIZER:-mock}"
if [ "$OPT" != "mock" ]; then
  # Flip the two optimizer keys in place; everything else in the preset is unchanged.
  cp "$EX/optimizer_INSTRUCTIONS.md" "$D/.capevolve/project/INSTRUCTIONS.md"
  "$PY" - "$D/.capevolve/project/capevolve.yaml" "$OPT" "${CHEAP_REAL_OPT_MODEL:-}" <<'SED'
import pathlib, sys
p = pathlib.Path(sys.argv[1]); opt, model = sys.argv[2], sys.argv[3]
out = []
for line in p.read_text(encoding="utf-8").splitlines(True):
    if line.startswith("optimizer_skill:"):
        line = f"optimizer_skill: {opt}\n"
    elif model and line.startswith(("optimizer_model:", "proposer_model:")):
        line = f"{line.split(':', 1)[0]}: {model}\n"
    elif line.startswith("optimizer_instructions_file:"):
        continue
    out.append(line)
# ABSOLUTE, deliberately: cli.py resolves a relative `optimizer_instructions_file`
# against ITS OWN cwd and then against a cwd-relative `.capevolve/project`, neither of
# which is this run's project dir when the workdir is elsewhere. A relative path there
# silently falls back to the GENERIC template — the optimizer then gets tau2-flavored
# "edit the tool code" advice for a project that has no tools, and proposes a prompt
# for the wrong task entirely. Observed; not hypothetical.
out.append(f"optimizer_instructions_file: {p.parent / 'INSTRUCTIONS.md'}\n")
p.write_text("".join(out), encoding="utf-8")
SED
fi

echo "Working directory: $D"
echo "Runner model: $MODEL   Optimizer: $OPT"
exec "$PY" -m cap_evolve.cli run \
  --spec    "$D/.capevolve/project/capevolve.yaml" \
  --project "$D/.capevolve/project" \
  --run-ts  cheap \
  ${CHEAP_REAL_MAX_USD:+--max-usd "$CHEAP_REAL_MAX_USD"} \
  --dashboard "${CAPEVOLVE_DASHBOARD:-off}"
