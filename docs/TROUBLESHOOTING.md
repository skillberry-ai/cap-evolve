# Troubleshooting

Fixes for the most common install and run failures. If none of these match, open an issue
with the exact command and output.

## Install

**`cap-evolve: command not found`** — the core isn't installed in the active env. Activate
your venv and `pip install ./core`, then `cap-evolve version`. (The toy example works
without installing, because `run.sh` sets `PYTHONPATH=$REPO/core`.)

**`pip install ./core` fails with an auth/index error** — your default pip index requires
auth. Append `--index-url https://pypi.org/simple` (cap-evolve-core has zero runtime deps,
so nothing else is fetched).

**Python too old** — cap-evolve needs **3.10+**. Check with `python3 --version`.

## Toy example

**`bash examples/toy_calc/run.sh` doesn't print `test_reward 1.0`** — re-run from the
**repo root** (the script resolves paths relative to itself but expects the repo layout).
It prints its working directory; the `dashboard.html` and `report.md` are written there.
The same result is asserted by `python -m pytest core/tests/test_e2e_slice.py -q`.

## Real runs

**`cap-evolve check` is not green (`{"ok": false}`)** — this is the hard gate doing its job.
The report names what's wrong: an unimplemented adapter method (still an `IMPLEMENT ME`
stub), empty/unstable `tasks(split)`, or a non-deterministic `score()`. Fix the adapter,
re-run `cap-evolve check .capevolve/project`. Don't proceed until it prints `{"ok": true}`.
See [`ADAPTER_CONTRACT.md`](ADAPTER_CONTRACT.md).

**`examples/tau2_airline/run.sh` (or `skillsbench/run.sh`) fails immediately** — they call
`$REPO/.venv/bin/cap-evolve` and assume `setup.sh` already created that venv and installed
core. Run the example's `setup.sh` **first**.

**Missing credentials at runtime** — real runs need the optimizer CLI credentials (e.g. a
logged-in Claude Code session or `ANTHROPIC_API_KEY`) and the runner model credentials in a
repo-root `.env` (`OPENAI_API_KEY`, `RITS_API_KEY` + `RITS_API_URL`, `WATSONX_*`, or an
`ANTHROPIC_BASE_URL` gateway). See [`INSTALL.md`](INSTALL.md#credentials-only-for-real-runs).

**RITS calls fail** — set both `RITS_API_KEY` and `RITS_API_URL`; the tau2 example passes
them per-call (no litellm monkeypatch, no tau2 fork). Check your endpoint and concurrency
knob (`TAU2_MAX_CONCURRENCY`).

**SkillsBench: Docker / benchflow errors** — Docker must be running; install the CLI with
`uv tool install benchflow` and provide gateway creds (`ANTHROPIC_BASE_URL`,
`ANTHROPIC_AUTH_TOKEN`). Start with `bash examples/skillsbench/smoke.sh` (1 task).

**`TestSealError` / "test already scored"** — the sealed test split is scored exactly once
per run, by design. Start a fresh run dir to finalize again. See [`HONEST_EVAL.md`](HONEST_EVAL.md).

**Run interrupted (crash, timeout, pod eviction) — how do I continue it?** Re-run the same
`cap-evolve run` command with `--resume` (and `--run-ts <ts>` to name the run; without it the
latest run under the base is reused). It reopens the run dir instead of failing with
`FileExistsError`, skips the baseline if it already ran, and picks the loop up at iteration
N+1 from the current best — completed rollouts, accepted candidates, optimizer spend, and the
git history are all preserved. If the interrupted run had already finalized (test seal burned),
resume skips finalize and just regenerates the report, so the held-out number is never scored
twice. To keep climbing past the original budget, pass a larger `--max-iterations` (or other
budget flag) alongside `--resume` — explicit budget flags extend the resumed run.

**A gain was rejected by the gate** — expected when the val improvement is within noise
(Δ ≤ k·SE). Lower `k_se`, add trials (`num_trials`) to shrink SE, or accept that the edit
didn't beat baseline significantly. On a small held-out val the gate will correctly refuse
gains it cannot distinguish from noise.

## Dashboard

**Dashboard won't launch** — install it: `pip install ./dashboard/backend`, then
`cap-evolve dashboard --base .capevolve --port 7878`. No backend? Open the static
`dashboard.html` written into any run dir, or serve a committed export:
`cd examples/tau2_airline/run_full/ui && python3 -m http.server 8000`.
