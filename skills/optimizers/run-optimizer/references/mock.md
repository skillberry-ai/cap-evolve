# mock optimizer

Deterministic, zero-API edit proposer for tests and CI. Runs the shipped
`scripts/_mock_apply.py` (never a network CLI), so it is the offline guarantee
the e2e proof slice relies on.

- **Install / auth:** none.
- **Edit script:** `CAPEVOLVE_MOCK_SCRIPT` env var, or `mock_script.json` in the
  workdir (or its parent), of the form
  `{ "edits": [ { "file": "prompt.txt", "op": "ensure_contains", "text": "..." } ] }`.
- **Ops:** `ensure_contains` (idempotent append), `append`, `set`.
- With no script present it makes no edits and exits 0 (candidate == parent).
