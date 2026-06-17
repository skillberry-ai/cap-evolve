# using-cap-evolve — routing reference

## Contents
- The state machine
- Relationship to `orchestrate`
- Session-start injection (the additionalContext JSON shape)

## The state machine
`scripts/run.py resolve_state(base)` is a deterministic function of the on-disk
project dir. It never mutates anything.

| state | detected by | next command |
|---|---|---|
| `fresh` | no `.capevolve/project/`, or no `capevolve.yaml` | `/cap-evolve:intake` |
| `scaffolded` | `capevolve.yaml` present, `cap-evolve check` not green (or core absent) | `/cap-evolve:implement-and-check` |
| `ready` | `cap-evolve check` green, no run yet | `/cap-evolve:baseline` (or `cap-evolve run`) |
| `running` | a `run_*` dir exists, `splits.json.test_used` false | `/cap-evolve:report` / continue loop |
| `finalized` | `splits.json.test_used` true | `/cap-evolve:report` |

The check is best-effort: if `cap_evolve` is not importable in the router's
environment, `resolve_state` returns `scaffolded` (conservative) rather than
claiming `ready` — it never asserts green it cannot prove.

## Relationship to `orchestrate`
- **`using-cap-evolve`** is the *router*: a thin, read-only front door that decides
  the next step from where the user is. It is the natural session-start trigger.
- **`orchestrate`** is the *driver*: once you are `ready`, it sequences every phase
  end to end with the hard gate and stop rules. The router points at it (or at the
  standalone chain); it does not duplicate its logic.

Both declare `needs: [project]` / `provides: [report]` and pass manifest DAG
validation, so the wiring is checked structurally like any other phase.

## Session-start injection (additionalContext)
The plugin's `SessionStart` hook (`hooks/inject_router.py`) injects a short pointer
to this router as `additionalContext` when the cwd looks like a cap-evolve project.
The hook prints this JSON envelope on stdout (exit 0):

```json
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "cap-evolve is installed. When the user asks to OPTIMIZE ... load /cap-evolve:using-cap-evolve first ..."
  }
}
```

This is **best-effort context, not enforcement** — it nudges the model to use the
router instead of improvising. The honesty invariants are enforced separately by
the `PreToolUse` deny hook and the `Stop`/`SubagentStop` green-check hook, plus
core (split seal, val-only gate). On unrelated projects the hook prints nothing.
