#!/usr/bin/env bash
# Peek into a LIVE blackbox trial's remote REPL (read-only): the names defined there, and the API-note
# keys installed from the candidate's tools/api_notes.json.
#
#   export AW_EVAL=/path/to/aw_eval
#   bash benchmarks/appworld/examples/react_agent/blackbox/repl_peek/repl_peek.sh            # the first live trial found
#   bash benchmarks/appworld/examples/react_agent/blackbox/repl_peek/repl_peek.sh 9101       # the trial on that port
#
# Each trial has its own AppWorld environment server on 127.0.0.1:91xx while it runs, and it accepts
# only its own task, so the task id is read from the adapter's episode spec files
# ($AW_EVAL/scratch/aw_bb_eps_*/<episode>.spec.json). Trials are short-lived: run this while a run is
# going. Every call is one interaction in a world that is being scored, so keep the code read-only.
# The REPL keeps AppWorld's code guard: eval, dunder attributes and help/pydoc are refused.
AW_EVAL="${AW_EVAL:-/tmp/aw_eval}"
PY="${AW_VENV:-$AW_EVAL/.venv}/bin/python"
SCRATCH="${AW_SCRATCH:-$AW_EVAL/scratch}"
WANT="${1:-}"

for port in $(ss -ltn | grep -oE "(127\.0\.0\.1|0\.0\.0\.0):91[0-9]{2}" | grep -oE "91[0-9]{2}$" | sort -u); do
  [ -n "$WANT" ] && [ "$port" != "$WANT" ] && continue
  # The newest episode spec that names this server: the trial running on it now.
  spec=$(grep -l "\"http://127.0.0.1:$port\"" $(ls -t "$SCRATCH"/aw_bb_eps_*/*.spec.json 2>/dev/null) 2>/dev/null | head -1)
  [ -z "$spec" ] && continue
  task=$("$PY" -c "import json, sys; print(json.load(open(sys.argv[1]))['task_id'])" "$spec")
  echo "== port $port, task $task"

  CODE='print("names:", sorted(n for n in dir() if not n.startswith("_")))
try:
    print("api notes:", sorted(_cap_api_notes))
except NameError:
    print("api notes: none")'

  "$PY" - "$port" "$task" "$CODE" <<'PYEOF'
import json, sys, urllib.request
port, task, code = sys.argv[1], sys.argv[2], sys.argv[3]
req = urllib.request.Request(f"http://127.0.0.1:{port}/execute", method="POST",
                             data=json.dumps({"task_id": task, "code": code}).encode(),
                             headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=30) as r:
    print(json.loads(r.read())["output"])
PYEOF
  exit 0
done
echo "no live trial found${WANT:+ on port $WANT}"
