# cap-evolve Dashboard — Explainability Views (Plan 3 of 5)

> Built inline this session. Gate per task: backend = pytest; frontend = `npm run build` + named vitest.

**Goal:** Make the optimization process fully explainable in the UI — Phases timeline, Trajectories (traces + tool usage), Iterations (diff viewer), Memory (history / rejected / scratchpad), Insights (what-helped / dead-ends / narrative), and the Compare page — all reading the Plan 1 backend (plus a small read-only memory endpoint added here).

**Architecture:** Extends the Plan 2 frontend tabs (currently stubbed) and adds two read-only backend endpoints for data the reducer doesn't surface (history/rejected memory, candidate scratch files). No engine changes.

**Tech Stack:** same as Plan 2 (React/TS/Tailwind/Recharts/Framer Motion) + FastAPI backend.

## Global Constraints
- Same as Plans 1–2. Read-only; reuse `redact()`; semantic tokens; reduced-motion safe; color never sole signal; tabular figures for numbers.
- Data shapes (verified in `.demo/.agentcapo/run_demo`): `history.jsonl` = `{candidate_id, summary, val}`; `rejected.jsonl` = `{candidate_id, summary, reason, val}`; candidate dir holds `INSTRUCTIONS.md, MEMORY.md, STATE.md, prompt.txt`; rollout = `{input, rollout:{output,trace,tool_calls,error,...}, score:{reward,feedback,...}}`.

## Tasks

### Task 1 (backend): memory + candidate-file endpoints
- Create `capevolve_dashboard/memory.py`: `read_memory(run_path)->{history:[...], rejected:[...]}` (parse the two jsonl, redacted); `list_candidate_files(run_path, cid)->[{name, text}]` for `*.md`/`*.txt` in `candidates/<cid>/` (redacted, name-sanitized).
- Routes (through `resolve_run`): `GET /api/runs/{id}/memory`, `GET /api/runs/{id}/candidate/{cid}/files`.
- Tests in `tests/test_memory_api.py`: history/rejected parsed; candidate files returned; unknown run → 404; traversal `cid` rejected.
- **Gate:** `python3 -m pytest` green; commit.

### Task 2 (FE): Phases timeline
- `lib/phases.ts`: `derivePhases(detail)` → ordered `[{key,label,status:'done'|'active'|'pending',detail,metrics}]` from summary/graph (intake✓, implement-and-check✓ gate, baseline=baseline_val+splits, algorithm=iterations/accepted, finalize=test sealed reveal, report=this dashboard). **Unit-tested.**
- `components/PhasesTimeline.tsx`: horizontal stepper, completed fill, active shimmer, per-phase metrics; wire into RunDeepDive "Phases" tab (enable it).
- **Gate:** build + vitest; commit.

### Task 3 (FE): Trajectories
- `components/Trajectories.tsx`: `useQuery` rollouts (split selector val/test); table sorted worst-first (reward asc) with pass/fail icon + feedback; row click → drawer fetching `/rollout/{file}` showing input, output, trace, and **tool-calls used** (names + counts); empty/loading states. Enable "Trajectories" tab.
- **Gate:** build + a vitest rendering a mocked rollout list; commit.

### Task 4 (FE): Iterations diff viewer
- `components/IterationsDiff.tsx`: candidate selector (accepted+rejected from graph, with Δ vs parent); `useQuery` `/diff/{cid}`; render unified diff rows (add green / del red / ctx muted / hunk header), per-file +N/−N. Empty state when no snapshots. Enable "Iterations" tab.
- **Gate:** build; commit.

### Task 5 (FE): Memory tab
- `components/MemoryPanel.tsx`: `useQuery` `/memory`; two columns — accepted **History** (summary, val) and **Rejected** (summary, reason, val); candidate selector → `useQuery` `/candidate/{cid}/files` showing MEMORY.md/STATE.md/INSTRUCTIONS.md/prompt.txt in mono. Enable "Memory" tab.
- **Gate:** build; commit.

### Task 6 (FE): Insights
- `lib/insights.ts`: from graph+memory derive **what helped** (accepted nodes by Δ desc), **dead-ends** (rejected reasons deduped with ×count), **tool usage** (aggregate tool_calls across rollouts — needs rollouts query), gate-warnings/diagnoses passthrough, and a generated **narrative** string. Unit-test the dedupe + tool aggregation.
- `components/Insights.tsx`: cards for each; enable "Insights" tab.
- **Gate:** build + vitest; commit.

### Task 7 (FE): Compare page
- Replace `ComparePlaceholder` with `Compare.tsx`: `useQuery` `/compare?ids=`; summary table (algorithm/baseline/best/Δ/test/cost/iters) + overlaid best-so-far multi-line (Recharts) keyed by run; per-run color; remove/add runs. Route `/compare`.
- **Gate:** build + a vitest rendering a mocked compare payload; commit.

## Verification
Final integrated smoke: backend on demo + built frontend; click each tab, confirm Phases/Trajectories/Iterations/Memory/Insights render against `run_demo` and Compare works with `?ids=run_demo`.

## Out of scope (Plans 4–5)
Pipeline auto-start/CLI wiring; legacy single-file HTML upgrade.
