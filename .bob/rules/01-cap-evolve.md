# cap-evolve: rules for Bob Shell

Bob Shell reads this file on every run in this repository, including the
`fix-with-bob` issue automation. Read `CONTRIBUTING.md` too: its house rules apply.

## Repository layout

- `core/cap_evolve/`: the optimization loop (splits, gate, seal, harness) and
  `dashboard.py`, whose `reduce_run` builds the run payload for the dashboard.
  Core has zero runtime dependencies. Every core change needs a test in `core/tests/`.
- `skills/`: self-contained skills. Each `scripts/run.py` prints one JSON object to stdout.
- `dashboard/backend/`: FastAPI server and `export_static.py` (the static export
  published to GitHub Pages).
- `dashboard/frontend/`: React + TypeScript + Vite single-page app.
  - Components are in `src/components/`, routes in `src/routes/`, API types in
    `src/lib/types.ts`, tests (vitest) in `src/test/`.
  - Run tabs are registered in `buildTabs()` in `src/routes/RunDeepDive.tsx` and
    are gated on the run's `capabilities`.
  - Use the theme tokens in `src/index.css` (`--primary`, `--accepted`,
    `--rejected`, `--failed`, `--seed`, ...) for every color, in both light and dark themes.
  - `dashboard/frontend/dist/` is committed. After any change under
    `dashboard/frontend/src/`, run `npm run build` and keep the new `dist/` files.
    CI fails when `dist/` is stale.

## Commands (the same ones CI runs)

```bash
pip install -e "./core[dev]" -e "./dashboard/backend[dev]"
python -m pytest core/tests -q
python -m pytest dashboard/backend/tests -q
python skills/_registry/lint_skills.py skills
cd dashboard/frontend && npm ci && npm run build && npm test
```

## Finish the work

- Deliver the whole issue in one PR. A "suggested PR order" in an issue is the
  order to work in, not a place to stop. Do not leave parts for a later PR.
- Every change to `core/cap_evolve/`, `skills/*/*/scripts/`,
  `dashboard/backend/capevolve_dashboard/` or `dashboard/frontend/src/` needs a
  new or updated test in `core/tests/`, `dashboard/backend/tests/` or
  `dashboard/frontend/src/test/`. The automation fails the change otherwise.

## Issues that describe a UI

- A dashboard or UI issue is resolved only when the UI exists in
  `dashboard/frontend/src/` and is reachable from the app. Backend data alone is
  not enough.
- When the issue links a proof of concept (for example a gist with a
  self-contained HTML file), download it and build the same views and
  interactions as React components that reuse the existing ones (`GatePanel`,
  `TaskMatrix`, `DiffRows`, `LineageTree`, ...).
- Add the data the UI needs to `reduce_run`, so the live API and the static
  export get it without extra endpoints.
- Add a vitest test for each new component, and a pytest test for each new
  field in `reduce_run`.

## Writing style

Comments, docs, commit text and PR text use plain, simple English. Say what
the code does and why. Do not use idioms or marketing words.
