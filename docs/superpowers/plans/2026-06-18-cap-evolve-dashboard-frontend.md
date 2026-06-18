# cap-evolve Dashboard — Frontend Shell & Core Views (Plan 2 of 5)

> **For agentic workers:** built inline this session (subagent dispatch budget-blocked). Verification gate per task = `npm run build` (tsc + vite) passes AND targeted Vitest unit tests pass. Steps use checkbox syntax.

**Goal:** A capybara-branded, dark-OLED, animated React dashboard that reads the Plan 1 backend: a Hub of all runs, a single-run Overview (KPI strip + cumulative-best chart), a Lineage (best-path spine) view, and a live SSE client — establishing the shell, theme, motion system, and data layer that Plan 3 extends with the remaining explainability tabs.

**Architecture:** Vite + React + TypeScript SPA under `agent-capo/dashboard/frontend/`. Talks to the FastAPI backend at `/api/*` (dev: Vite proxy to `127.0.0.1:7878`; prod: served by the backend's static mount). State via TanStack Query (polling/caching) + a small SSE hook for live runs. Charts via Recharts; lineage spine hand-built SVG. Animation via Framer Motion behind a global reduced-motion guard.

**Tech Stack:** React 18/19, TypeScript, Vite, Tailwind CSS v3.4 (+ tailwindcss-animate), shadcn-style UI primitives (sourced/refined via 21st.dev MCP), Recharts, Framer Motion, TanStack Query, React Router, Vitest + Testing Library, lucide-react icons.

## Global Constraints
- Dark Mode (OLED) primary; semantic color tokens (CSS vars), never raw hex in components.
- Blue `#3B82F6`/`#1E40AF` data & primary; amber `#D97706` champion/best; green=accepted/improved, red=rejected/regressed — always paired with icon/shape, never color-alone.
- Type: Fira Sans (UI) + Fira Code (numbers/scores/diffs, tabular figures).
- Motion tokens from spec §4a: micro 120ms / standard 200ms / entrance 280ms / complex ≤400ms; exits ~65% of enter; ease-out enter, ease-in exit; spring (stiffness ~260, damping ~24) for "grow" elements; animate transform/opacity only; stagger 30–50ms. **Global `prefers-reduced-motion` guard** disables transforms/springs/continuous pulses; data readable with motion off. Max 1–2 hero animations per view; continuous motion only for live-spine pulse + loaders. Skeletons (not spinners) for waits >300ms.
- No emoji as structural icons — SVG/lucide only. Touch targets ≥44px. Responsive 375/768/1024/1440.
- Data contract = the Plan 1 API exactly (`/api/runs`, `/api/runs/{id}` → `{run_id,path,graph,summary}`, `/api/runs/{id}/stream` SSE events `snapshot|event|done|idle`, etc.). No backend changes in this plan.

## File Structure
```
dashboard/frontend/
  package.json, vite.config.ts, tsconfig*.json, index.html, postcss/tailwind config
  src/
    main.tsx, App.tsx                 # router + providers
    index.css                          # theme tokens, fonts, base
    lib/api.ts                         # typed fetch wrappers
    lib/types.ts                       # RunSummary, RunDetail, GraphNode, ...
    lib/format.ts                      # pct/delta/usd/number formatters (tested)
    lib/bestCurve.ts                   # cumulative-best series from nodes (tested)
    lib/useRunStream.ts                # SSE hook (snapshot+event reducer, tested reducer)
    lib/motion.ts                      # variants + reduced-motion guard
    components/
      Capybara.tsx                     # logo SVG (idle/pulse)
      ui/{button,card,badge,skeleton,tabs}.tsx   # shadcn-style primitives
      KpiStrip.tsx, KpiCard.tsx
      BestCurveChart.tsx               # cumulative-best stair + scatter (Recharts)
      LineageTree.tsx                  # best-path spine (SVG)
      StatusBadge.tsx, AppShell.tsx
    routes/{Hub.tsx, RunDeepDive.tsx}  # RunDeepDive: Overview + Lineage tabs (others stubbed for Plan 3)
    test/  *.test.ts(x)
```

## Tasks

### Task 1: Scaffold + theme + brand + verification gate
- Vite react-ts scaffold in `dashboard/frontend/`; add Tailwind v3.4 (+animate), Recharts, framer-motion, @tanstack/react-query, react-router-dom, lucide-react, vitest, @testing-library/react, jsdom.
- `index.css`: dark-OLED semantic tokens (CSS vars), Fira Sans/Code, base styles.
- `vite.config.ts`: dev proxy `/api` → `http://127.0.0.1:7878`; build `outDir: dist` (matches backend `resolve_static_dir`).
- `Capybara.tsx` logo (inline SVG, duotone, `state: idle|live` prop; pulse animation gated by reduced-motion).
- Vitest wired; one trivial passing test.
- **Gate:** `npm run build` passes; `npm run test` passes; commit.

### Task 2: Data layer — types, api, formatters (TDD)
- `lib/types.ts` mirrors backend shapes. `lib/api.ts` typed wrappers (`getRuns`, `getRun`, `getRollouts`, `getDiff`, `getCompare`).
- `lib/format.ts`: `pct`, `signedPct`, `usd`, `compactNum`, `duration` — **unit tested** (table of cases).
- `lib/bestCurve.ts`: `cumulativeBest(nodes)` → `[{iteration,best}]` (stair) — **unit tested** incl. empty + nulls.
- **Gate:** vitest green; `npm run build`; commit.

### Task 3: App shell + Hub
- `AppShell` (sidebar ≥1024px / top bar on mobile, capybara brand, theme).
- `Hub`: TanStack Query `getRuns`; run cards/table (StatusBadge live●/done/failed, algorithm, best, Δ, iterations, cost, date); sort by date; multi-select → "Compare" CTA (routes to Plan 3 compare, button present); skeleton loading; empty state; staggered card entrance (reduced-motion safe). Live runs pinned with pulsing badge.
- **Gate:** `npm run build`; a Testing-Library test rendering Hub with mocked fetch shows a run row; commit.

### Task 4: Run Overview — KPI strip + cumulative-best chart + live SSE
- `RunDeepDive` route with shadcn Tabs (Overview, Lineage now; Phases/Trajectories/Iterations/Memory/Insights stubbed "coming in Plan 3").
- `useRunStream` SSE hook: opens `/api/runs/{id}/stream`, applies `snapshot` then merges `event`s; **reducer unit-tested**; falls back to query data if EventSource unsupported.
- `KpiStrip`: best/baseline/Δabs/Δ%, test reward + pass^k, accepted/rejected/failed/seed, frontier, wall-clock, cost split, tokens, iterations. Count-up on change; delta chip flash (reduced-motion safe).
- `BestCurveChart`: Recharts scatter of per-iteration val + amber cumulative-best stair line; champion ★; animated draw respecting reduced-motion; tooltip with exact values; table fallback.
- **Gate:** `npm run build`; vitest for the SSE reducer; commit.

### Task 5: Lineage — best-path spine
- `LineageTree`: hand-built SVG; nodes laid out by iteration; best-path rendered as a flat amber spine, off-spine candidates hang below with L-connectors; accepted green / rejected dim / seed neutral; hover tooltip (id, Δ vs parent, reason); click selects. Spring grow-in + connector draw, reduced-motion → instant. Layout fn (`layoutLineage(graph)`) **unit-tested** (spine = path to best_id; child offsets).
- **Gate:** `npm run build`; vitest for layout; commit.

## Verification
- Each task: `npm run build` (tsc + vite) must pass, plus its named Vitest tests.
- Final: run backend (`cap-evolve-dashboard --base .demo/.agentcapo`) + `npm run dev`, confirm Hub lists `run_demo`, Overview KPIs + curve render, Lineage shows the 4-node graph. (Manual smoke — note in ledger.)

## Out of scope (Plan 3+)
Phases timeline, Trajectories, Iterations/diffs viewer, Memory, Insights/dead-ends/narrative, Compare page internals, pipeline auto-start, legacy HTML upgrade.
