# cap-evolve Dashboard — Design Spec

**Date:** 2026-06-18
**Status:** Approved (design); pending implementation plan
**Owner:** Osher Elhadad

## 1. Goal

Make the cap-evolve dashboard the clearest, most navigable, and most *explainable*
view of a capability-optimization run. It must:

- Carry a distinct **🦫 capybara brand** in an **evolve / optimization / auto-improvement** theme.
- Show **far more metrics & statistics** than today.
- **Fully explain the optimization process**: every phase, what happened in each, the
  trajectories, the per-iteration changes, the memory, what helped and what didn't,
  what the agent used and didn't use.
- Borrow proven ideas from the `evo` repo (best-path spine, dead-ends panel, narrative
  summary, frontier strategies, pareto-per-task, per-task diagnoses).
- Be **created automatically by the pipeline** — by default the live UI starts at the
  beginning of `cap-evolve run` so the whole evolution is watchable in real time, and
  the **last (report) phase** guarantees the dashboard exists and is opened.

## 2. Background — current state (what exists today)

- **Engine:** `cap-evolve run` is a thin sequencer (`core/cap_evolve/cli.py:_cmd_run`)
  that runs phases as subprocesses in order:
  `intake → implement-and-check → baseline → algorithm(hill-climb│gepa│skillopt) → finalize → report`.
- **Run data (source of truth):** each run writes a run dir (`core/cap_evolve/rundir.py`)
  containing `events.jsonl` (append-only audit log — the source of truth),
  `baseline.json`, `final.json`, `splits.json`, `state.json`, `history.jsonl`,
  `rejected.jsonl`, per-task `rollouts/<split>/<task>__<cand>__t<k>.json`,
  per-candidate snapshots in `candidates/<id>/` (incl. `MEMORY.md`, `STATE.md`,
  `INSTRUCTIONS.md`), and a `.git/` iteration store (one commit per iteration).
- **Existing dashboard:** `core/cap_evolve/dashboard.py` (~931 lines) generates a
  **single self-contained `dashboard.html`** (stdlib-only: inline CSS + vanilla JS +
  inline SVG, no deps, opens from `file://`). `reduce_run(run_dir)` folds the run dir
  into `{graph, summary}`; `render_html()` injects it as a JSON island; `render_ansi()`
  prints a terminal report. It is auto-generated **in the report phase**
  (`skills/phases/report/scripts/run.py:69-75`, on by default, `--no-dashboard` to skip).
- **Metrics already computed** (`core/cap_evolve/types.py`, `loop.py`): per-task `Score`
  (`reward`, `feedback`, `stderr`, `trial_rewards`); `SplitResult`
  (`reward`, `stderr`, `pass_k`, `pass_at_k`, `per_task`, `cost_usd`, `tokens`, `seconds`);
  `Spent` budget (iterations, usd, runner/optimizer seconds, tokens).

### Ideas borrowed from `evo` (`evo/plugins/evo/...`)

- **Best-path-as-spine** lineage layout (`static/app.js buildVisibleRows`).
- **Cumulative-best stair** over raw scatter (`report.py _running_best`).
- **"What Not To Try"** deduped dead-end hypotheses with ×counts (`scratchpad.py`).
- **Per-task failure rows + co-located diagnosis annotations**, worst-first.
- **Auto-generated narrative "Scratchpad"** (`scratchpad.py`) — the whole run as readable markdown.
- **Frontier strategies** as first-class explained concepts (`frontier_strategies.py`).
- **Pareto-per-task specialists** — candidates that win some task even if mediocre overall.
- **Delta-from-parent** everywhere, colored by metric direction.

## 3. Decisions (locked during brainstorming)

| Decision | Choice |
|---|---|
| Frontend | **New React app**: React + Vite + TypeScript + Tailwind + **shadcn/ui** (components via **21st.dev MCP**), charts via **Recharts** + a few hand-built SVG views, animation via **Framer Motion** (see §4a) |
| Backend / data delivery | **Live server + real-time monitoring**: **FastAPI** serving run-dir data + **SSE** live updates (polling fallback) |
| Run scope | **Hub** (list all runs) → **single-run deep-dive** → **cross-run compare** |
| Live timing | **Auto-start at pipeline START by default** (watch the whole evolution); configurable; report phase guarantees creation/open. If user doesn't specify → UI on by default |
| Legacy single-file HTML | **Keep as headless/offline fallback AND improve it** (brand + theme + as much expanded metrics/explainability as the zero-dep constraint allows) |
| Chart lib | **Recharts** (recommended) + hand-built SVG for lineage spine & heatmap |

## 4. Brand & Theme — "watch capability evolve"

- **Logo:** custom **capybara SVG mark** sitting atop an ascending fitness curve / stair
  (echoes the cumulative-best chart). Variants: mono + duotone for light/dark, favicon,
  and an animated "pulse" while a run is live. **No emoji as structural icons** — use SVG
  (Lucide/Heroicons) throughout.
- **Mode:** **Dark Mode (OLED)** primary (engine recommendation for data-dense dev tools);
  optional light theme. Both themes designed together; contrast verified independently.
- **Motion = evolution:** candidates grow into the lineage with a gentle spring; best-path
  spine glows amber; accepted pulse green, rejected dim. Respect `prefers-reduced-motion`.
- **Palette (semantic tokens, not raw hex in components):** deep-black/midnight surfaces;
  **blue** (`#3B82F6` / `#1E40AF`) data & primary; **amber** (`#D97706`) champion/best;
  green = accepted/improved, red = rejected/regressed — always paired with icon/shape
  (never color-alone).
- **Type:** **Fira Sans** (UI) + **Fira Code** (scores, diffs, tabular figures so numeric
  columns don't jitter).

## 4a. Motion, Animation & Polish (the "amazing" bar)

Motion is **meaningful, not decorative** — every animation expresses a cause→effect
in the evolution process. Library: **Framer Motion** (`motion`) for React + CSS
transitions; charts animate via Recharts' built-in animation. **Tokens are global**
(one easing/duration scale, shared rhythm) so the whole app feels unified.

**Motion tokens**
- Durations: micro `120ms`, standard `200ms`, entrance `280ms`, complex ≤ `400ms`.
  **Exits are ~65% of enter** (snappier dismissal).
- Easing: **ease-out** entering, **ease-in** exiting; **spring** (`stiffness ~260,
  damping ~24`) for elements that "grow" (lineage nodes, candidate dots, cards).
- Animate **`transform`/`opacity` only** (GPU-friendly; never width/height/top/left).
- **Stagger** list/grid/heatmap entrance by 30–50ms per item.

**Signature, on-theme animations (the evolution story)**
- **Cumulative-best curve draws in** on load via `stroke-dashoffset` (the fitness
  line "grows"); the champion **★ twinkles** once when it becomes best.
- **Live candidate arrival (SSE):** a new scatter dot **springs in** (scale 0.6→1)
  and settles; **accepted** → green ripple pulse; **rejected** → quick dim/fade to muted.
- **Lineage tree:** new nodes **grow from their parent** (origin-anchored spring) and
  the **connector path draws** from parent to child; the **best-path spine glows amber**
  with a slow, subtle pulse (the one allowed continuous animation — disabled on reduced-motion).
- **KPI strip:** numbers **count-up** (tween) on change; the delta chip **flashes**
  green/red then settles; the **live badge** has a soft pulsing dot.
- **Phases timeline:** the active phase **shimmers**; completed phases fill with a
  left-to-right wipe; a connecting progress line advances as the pipeline proceeds.
- **Heatmap:** cells **stagger-reveal**; a cell flips pass↔fail with a crossfade.
- **Capybara logo:** gentle idle "breathing"; switches to a **pulse** state while a run
  is live; on the hero it subtly **climbs the fitness curve**.

**Navigation & continuity**
- Tab changes **crossfade + small directional slide** (forward = up/left, back =
  down/right); **shared-element transition** from a Hub run-card into its deep-dive header.
- Modals/sheets **scale+fade from their trigger**; backdrop scrim 40–60%.
- Press feedback: subtle scale `0.97` on cards/buttons; hover transitions 150–300ms.

**Discipline & accessibility (non-negotiable)**
- **`prefers-reduced-motion`**: a global guard disables transforms/springs/continuous
  pulses and the curve-draw, falling back to instant or simple opacity. Data is fully
  readable with motion off.
- **Max 1–2 hero animations per view** — no animate-everything; continuous motion is
  reserved for the live-spine pulse and loading indicators only.
- **Loading = skeleton shimmer** (not blocking spinners) for waits > 300ms; charts show
  a shimmer placeholder, never an empty axis frame.
- **Animations are interruptible** and never block input; chart entrance respects
  reduced-motion and data renders immediately underneath.

## 5. Architecture

```
cap-evolve run ──► run_<ts>/  (events.jsonl, baseline/final.json, splits.json,
                   │           rollouts/, candidates/, history/rejected.jsonl, .git/)
                   │           SOURCE OF TRUTH — no new persistence required
                   ▼
        ┌───────────────────────────────────────────────┐
        │ FastAPI backend  (agent-capo/dashboard/backend) │
        │  reuses cap_evolve.dashboard.reduce_run()       │  ← single-sourced data contract
        │  tails events.jsonl for live updates            │
        │  GET /api/runs                  (hub list)      │
        │  GET /api/runs/{id}             (full reduced)  │
        │  GET /api/runs/{id}/stream      (SSE live)      │
        │  GET /api/runs/{id}/rollouts/.. (trajectories)  │
        │  GET /api/runs/{id}/diff/{cand} (git diff)      │
        │  GET /api/compare?ids=a,b,..    (compare)       │
        │  serves built React assets                      │
        └───────────────────────────────────────────────┘
                   ▲ fetch + EventSource (SSE)
        ┌───────────────────────────────────────────────┐
        │ React + Vite + TS + Tailwind + shadcn/ui        │
        │ (21st.dev MCP for components) + Recharts         │
        └───────────────────────────────────────────────┘
```

**Principles**

- **Core stays clean.** The dashboard app is a **new optional package** at
  `agent-capo/dashboard/` (own `backend/`, `frontend/`, deps). The stdlib-only **core**
  (`core/cap_evolve/`) is not given new third-party dependencies.
- **Single-sourced data contract.** Backend **reuses `reduce_run()`** so the React app,
  the SSE stream, and the legacy HTML all describe a run identically. Live updates come
  from **tailing the append-only `events.jsonl`** (no schema change).
- **SSE** for live (one-way, auto-reconnect, simpler than WebSocket); **polling fallback**.
- **Idempotent server.** Launch reuses an already-running instance on the chosen port.

## 6. Information Architecture / Navigation

- **Hub (`/`)** — all runs as cards/table: status chip (live ●/done/failed), algorithm,
  best score, Δ vs baseline, iterations, cost, date. Sort/filter; **multi-select → Compare**.
  Live runs pinned on top with a pulsing badge. Empty state with guidance when no runs.
- **Run deep-dive (`/runs/:id`)** — adaptive nav (sidebar ≥1024px, top-tabs on mobile),
  **sticky KPI strip** always visible, current location highlighted, breadcrumbs,
  deep-linkable tabs/candidates:
  1. **Overview** — KPI strip + cumulative-best chart + phase status summary
  2. **Phases** — full pipeline timeline (§8)
  3. **Lineage** — best-path-as-spine tree
  4. **Trajectories** — per-task rollouts, traces, tool-calls
  5. **Iterations** — per-candidate diffs & deltas
  6. **Memory** — accepted history, rejected memory, optimizer scratchpad
  7. **Insights** — what helped/didn't, tool usage, dead-ends, narrative summary
- **Compare (`/compare?ids=`)** — runs side-by-side: best/baseline/Δ, score-over-iteration
  overlay, cost/tokens, algorithm, per-task win matrix.

## 7. Metrics & Statistics (expanded)

**KPI strip:** best val · baseline val · **Δ abs + Δ%** · sealed-test reward +
**pass^k / pass@k** · accepted / rejected / failed / seed counts · frontier size ·
wall-clock · **cost split (optimizer vs runner)** · tokens · iterations ·
**$ per +1% improvement** · stall counter.

**Charts / views:**
- Cumulative-best stair over per-iteration scatter (champion ★, record-holder rings, hover tooltips).
- tasks×iterations pass/fail **heatmap** (rows worst-first, per-cell feedback on hover).
- cost / tokens / latency over time.
- **cost-vs-score frontier** scatter.
- score distribution.
- **pass@k vs pass^k** (capability vs reliability).
- **per-task win-rate**.
- **Pareto-per-task specialists** (which branch is the only one solving task X).
- **tool-usage frequency** (used vs available-but-unused).
- **time-per-phase** breakdown.

All charts: legends, tooltips on hover/tap, accessible palettes (not red/green only),
empty/loading/error states, `prefers-reduced-motion` honored, a text/table alternative
for screen readers.

## 8. Explainability (core requirement)

- **Phases timeline** — `intake → implement-and-check → baseline → algorithm → finalize → report`.
  Each phase a panel: what it did, duration, status, artifacts produced, key outputs
  (e.g. baseline → seed val + split sizes; finalize → the one-time sealed-test reveal;
  implement-and-check → the `{"ok": true}` gate result).
- **Trajectories** — per task / per trial: input, model output vs target, full **trace**,
  **tool-calls the agent used** (and which available tools it did *not* use), score,
  feedback. Sorted worst-first with co-located diagnosis annotations.
- **Per-iteration changes** — git-backed unified/split **diff vs parent** for each
  candidate, `+N/−N` stats, the candidate's hypothesis/summary, and its Δ.
- **Memory** — accepted **History** (`history.jsonl`), **Rejected Memory**
  (`rejected.jsonl`, "do-not-re-propose" + reasons), and optimizer **STATE.md / MEMORY.md**
  scratchpad snapshots across iterations.
- **What helped / what didn't** — **"What Not To Try"** deduped dead-ends (×count);
  accept/reject reasons; gate warnings & diagnose/optimizer_error stream;
  **delta-from-parent** color-coded everywhere.
- **Agent usage** — tool-call inventory: invoked vs available-but-unused, frequency,
  correlation with score.
- **Narrative summary** — auto-generated readable "story of the run" (inspired by evo's
  Scratchpad): tree + frontier + dead-ends + notes.

## 9. Pipeline Integration (auto-creation)

- **Default = auto-start at pipeline START.** `cap-evolve run` launches the dashboard
  server (idempotent), opens the browser, and the user watches the evolution live. Hook:
  `core/cap_evolve/cli.py:_cmd_run` (after the check gate / around baseline).
- **Last phase guarantees it.** The **report** phase
  (`skills/phases/report/scripts/run.py`) ensures the server is up, finalizes data, and
  pins/opens the final view — so "the dashboard is created automatically in the last
  phase" holds even when early-start is disabled.
- **Configurable** via spec/flag: `dashboard: auto | report-only | off`
  (plus `--dashboard / --no-dashboard`, `--dashboard-port`). Unspecified → **UI on**.
- **Fallback intact.** The improved stdlib single-file `dashboard.html` is still written
  (CI/offline/headless); `--no-dashboard` still skips. The dashboard must never break the
  report (existing try/except contract preserved).

## 10. Legacy single-file HTML — keep AND improve

Within the **zero-dependency** constraint (inline CSS/JS/SVG, opens from `file://`):
add the **capybara logo + evolve theme**, expand the **KPI strip**, add the
**phases timeline**, the **"What Not To Try" dead-ends panel**, and the
**narrative summary**. It remains the headless/offline/CI artifact and the data fallback.

## 11. Layout / where it lives

```
agent-capo/
  core/cap_evolve/dashboard.py        # legacy single-file (improved); reduce_run reused by backend
  dashboard/
    backend/                          # FastAPI app (SSE, run-dir API), reuses reduce_run
    frontend/                         # Vite + React + TS + Tailwind + shadcn/ui + Recharts
    README.md
  skills/phases/report/scripts/run.py # last-phase hook: ensure server up + open final view
  core/cap_evolve/cli.py              # _cmd_run: auto-start server at pipeline start (default)
```

- One-time `npm install && npm run build`; backend serves built assets.
- New `cap-evolve dashboard` CLI subcommand to launch/focus the server manually.

## 12. Accessibility & quality bar (must-haves)

- Contrast ≥ 4.5:1 (text), focus rings visible, full keyboard nav, aria-labels on
  icon-only buttons, color never the sole signal.
- Charts have table/text alternatives and keyboard-reachable tooltips.
- Touch targets ≥ 44px; responsive at 375 / 768 / 1024 / 1440.
- Animations 150–300ms, `transform`/`opacity` only, `prefers-reduced-motion` respected.
- Loading = skeletons (not blocking spinners); explicit empty + error states with retry.

## 13. Out of scope (YAGNI)

- Auth / multi-user / hosted deployment (local developer tool only).
- Persisting any new run data — the dashboard is strictly a *view* over existing artifacts.
- Editing runs from the UI (read-only).

## 14. Open implementation choices (to settle in the plan)

- SSE event granularity (per-event vs debounced snapshots) and reconnect/backfill strategy.
- Whether the FastAPI server is a long-lived daemon (fixed port, lists all runs) vs
  per-invocation — recommend **long-lived, fixed default port, idempotent**.
- 21st.dev component selection per view (done during implementation via MCP).
