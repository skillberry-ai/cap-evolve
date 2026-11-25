# Looking into a live trial's REPL (blackbox runs)

In a blackbox run, every trial (one episode) gets its own AppWorld environment server: the remote REPL
the agent's code runs in. It listens on `127.0.0.1`, on a port from `AW_ENV_PORTS` (default
`9100-9399`), only while that trial runs. The candidate's `tools/` are loaded there before step 1, so
it is where you can see them in use.

## The quick way

```bash
export AW_EVAL=/path/to/aw_eval
bash benchmarks/appworld/examples/react_agent/blackbox/repl_peek/repl_peek.sh          # the first live trial it finds
bash benchmarks/appworld/examples/react_agent/blackbox/repl_peek/repl_peek.sh 9101     # the trial on port 9101
```

It prints the names defined in that REPL (the candidate's helpers, AppWorld's own `apis` / `requester`,
and the agent's variables so far) and the keys of the installed API notes.

## Finding a port and its task by hand

1. **The open ports** of the running trials:
   ```bash
   ss -ltn | grep -oE "127\.0\.0\.1:91[0-9]{2}"
   ```
2. **The task on a port.** A server accepts only its own task id (another one gets HTTP 400). The
   adapter writes each episode's spec to `$AW_EVAL/scratch/aw_bb_eps_*/<episode>.spec.json`; the newest
   one naming the port is the trial on it now:
   ```bash
   PORT=9101
   grep -l "\"http://127.0.0.1:$PORT\"" $(ls -t $AW_EVAL/scratch/aw_bb_eps_*/*.spec.json) | head -1 \
     | xargs python3 -c "import json, sys; d = json.load(open(sys.argv[1])); print(d['task_id'])"
   ```
3. **Run read-only code in it:**
   ```bash
   curl -s -X POST http://127.0.0.1:$PORT/execute -H 'Content-Type: application/json' \
     -d '{"task_id": "<TASK_ID>", "code": "print(sorted(n for n in dir() if not n.startswith(\"_\")))"}'
   ```
   The answer is `{"output": "<what the code printed>"}`.

## Keep in mind

- **Trials are short-lived:** a port can close, or move to the next trial, between two commands. Read
  the port and the task right before the call.
- **Read-only only:** every call is one interaction in a world that is being scored. Never call an app
  API that changes state.
- **AppWorld's code guard applies:** `eval`, dunder attributes (`__doc__`) and `help` / `pydoc` are
  refused, so you see names, not a helper's source. The source is in the candidate's own files,
  `<run>/work/cand_NNNN/tools/helpers.py` and `tools/api_notes.json`, or in the `repl_code` field of
  any episode spec, which is exactly what was run in the REPL.
