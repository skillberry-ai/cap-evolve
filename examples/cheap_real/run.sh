#!/usr/bin/env bash
# cheap_real — the "step 2" rung: a REAL LLM run in minutes, for $0 (local) or cents.
#
# Usage: cd <repo-root> && bash examples/cheap_real/run.sh
#
# Programmatic entry point (this is the contract #133's quickstart calls). Every knob
# is an env var with a default; the last object on stdout is the run's summary JSON:
#
#   CHEAP_REAL_MODEL      litellm model string        (default ollama/llama3.2:3b — free, local)
#   CHEAP_REAL_API_BASE   endpoint for that model     (default http://localhost:11434 for an
#                                                      ollama/ MODEL; UNSET for any other, so a
#                                                      hosted model keeps its provider default)
#   CHEAP_REAL_OPTIMIZER  who proposes the edit       (default mock — zero-API/$0)
#   CHEAP_REAL_OPT_MODEL  optimizer/proposer model    (default "" — mock needs none)
#   CHEAP_REAL_WORKDIR    where to run                (default a fresh mktemp dir)
#   CHEAP_REAL_MAX_USD    hard $ stop                 (default from capevolve.yaml: 3.0)
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
# API_BASE only for a LOCAL model. `model_config.py:95` reads the GENERIC `API_BASE`
# before any provider special-casing, so exporting it unconditionally pointed a hosted
# MODEL at localhost:11434 — a second silent all-zeros trap on the hosted path.
case "$MODEL" in
  ollama/*) export API_BASE="${CHEAP_REAL_API_BASE:-http://localhost:11434}" ;;
  *) if [ -n "${CHEAP_REAL_API_BASE:-}" ]; then export API_BASE="$CHEAP_REAL_API_BASE"; else unset API_BASE; fi ;;
esac
export SCORING=exact
# The bundled adapter forwards `seed=` so distinct trials are independent draws, but
# Anthropic rejects it (`UnsupportedParamsError`) — and the adapter turns that into
# reward 0.0, i.e. the whole hosted rung silently scored 0. litellm honours this env var
# by dropping kwargs the provider does not support (`litellm/__init__.py:227`).
# A warning inside the adapter would not have saved us: per #251 the optimizer's stderr
# is discarded on success by three separate layers, so the only signal was the reward.
export LITELLM_DROP_PARAMS=1

# Preflight, because the adapter turns a failed model call into `error:` + reward 0.0 —
# correct behavior (infra noise must not be optimized against), but it means a missing
# dep, a stopped Ollama or an unroutable hosted model yields a clean-looking run whose
# every number is 0.0. A real run must be distinguishable from a broken one BEFORE
# anything is spent, on EVERY documented variant — the hosted path was uncovered and
# that is exactly where the bug shipped. The endpoint is never echoed: since #134 a
# non-default base URL is confidential, and neither is any credential.
#
# The whole block is redirected to stderr: it is progress/diagnostic output (#116), and
# litellm writes some of its own error banners straight to stdout, which would otherwise
# land in the caller's JSON stream.
{ "$PY" - "$REPO/templates/adapters" <<'PRE'
import os, sys, urllib.error, urllib.request
try:
    import litellm  # noqa: F401
except ImportError:
    sys.exit("cheap_real preflight: litellm is not importable by this interpreter. "
             "`pip install litellm`, or point CHEAP_REAL_PYTHON at one that has it.")
MODEL = os.environ.get("MODEL", "")
if MODEL.startswith("ollama/"):
    base, model = os.environ["API_BASE"].rstrip("/"), MODEL.split("/", 1)[1]
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
else:
    # Hosted: one real 1-token completion through the SAME wiring the adapter uses
    # (model_config.llm_kwargs() + the seed kwarg), so a rejected param, a missing
    # credential or a bad model name fails here instead of scoring 0.0 thirty times.
    # Costs a fraction of a cent — far less than a full silently-dead run.
    sys.path.insert(0, sys.argv[1])
    import model_config
    try:
        litellm.completion(model=MODEL, messages=[{"role": "user", "content": "ping"}],
                           max_tokens=1, seed=0, **model_config.llm_kwargs())
    except Exception as e:  # noqa: BLE001 — any failure here means the run would be 0.0
        msg = str(e)
        for secret in (os.environ.get("API_BASE"), os.environ.get("ANTHROPIC_BASE_URL"),
                       os.environ.get("API_KEY"), os.environ.get("ANTHROPIC_API_KEY"),
                       os.environ.get("ANTHROPIC_AUTH_TOKEN"), os.environ.get("OPENAI_API_KEY")):
            if secret:
                msg = msg.replace(secret, "<withheld>")
        sys.exit(f"cheap_real preflight: the hosted model {MODEL!r} did not answer a "
                 f"1-token probe ({type(e).__name__}). Every rollout would score 0.0. "
                 f"Check the model name and its credential; endpoint/keys withheld "
                 f"(see docs/TROUBLESHOOTING.md). Detail: {msg[:300]}")
print("cheap_real preflight: OK", file=sys.stderr)
PRE
} >&2

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
# ABSOLUTE, deliberately — this is the workaround for #252. cli.py resolves a relative
# `optimizer_instructions_file` against ITS OWN cwd and then against a cwd-relative
# `.capevolve/project`, neither of which is this run's project dir when the workdir is
# elsewhere. A relative path there silently falls back to the GENERIC template — the
# optimizer then gets tau2-flavored "edit the tool code" advice for a project that has
# no tools, and proposes a prompt for the wrong task entirely. Observed; not
# hypothetical. Worse (per #252): pipeline_selftest.py:73 resolves the SAME key
# project-relative and *reports a problem*, so `cap-evolve check` passes what
# `cap-evolve run` silently ignores. An absolute path satisfies both resolvers.
out.append(f"optimizer_instructions_file: {p.parent / 'INSTRUCTIONS.md'}\n")
p.write_text("".join(out), encoding="utf-8")
SED
fi

# Progress goes to STDERR, per #116's convention, so ALL of stdout is parseable JSON.
echo "Working directory: $D" >&2
echo "Runner model: $MODEL   Optimizer: $OPT" >&2

# The last-object filter is what makes the contract hold unconditionally. `cap-evolve run`
# prints a SECOND object on stdout when the dashboard mode is `auto` (#217: cli.py:205-207
# prints the launch status there instead of stderr), so a caller who sets
# CAPEVOLVE_DASHBOARD=auto would otherwise get two objects and a broken parse. The `off`
# default alone is not the guard — this filter is. Delete it when #217 lands.
"$PY" -m cap_evolve.cli run \
  --spec    "$D/.capevolve/project/capevolve.yaml" \
  --project "$D/.capevolve/project" \
  --run-ts  cheap \
  ${CHEAP_REAL_MAX_USD:+--max-usd "$CHEAP_REAL_MAX_USD"} \
  --dashboard "${CAPEVOLVE_DASHBOARD:-off}" \
  | "$PY" -c '
import json, sys
text, dec, i, last = sys.stdin.read(), json.JSONDecoder(), 0, None
while i < len(text):
    try:
        last, i = dec.raw_decode(text, i)
    except ValueError:
        i += 1
if last is not None:
    print(json.dumps(last, indent=2))
'
