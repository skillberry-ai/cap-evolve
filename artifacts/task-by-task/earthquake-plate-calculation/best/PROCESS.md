# PROCESS — what I did this iteration (explainability; REQUIRED)

## Ranked issue list (clusters by # failing tasks × trials, biggest first)
| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | CRS-recentering breaks distance | earthquake-plate-calculation (1/10 trials: t3) | Agent "recenters" the projection to a custom central meridian (`lon_0=180`) to "handle" the antimeridian instead of using canonical EPSG:4087 (lon_0=0). Recentering shifts every distance → 3873.93 vs gold 3878.27 → `test_distance_within_tolerance` fails (±0.01 km). | KNOWLEDGE / BEHAVIORAL | BODY (geospatial-analysis SKILL.md) |

Only ONE failure cluster exists (single skill, single flaky task, single failed test, single root cause). 9/10 trials already pass with plain EPSG:4087; t3 is the lone over-engineering tail.

## Changes made this iteration
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | BODY | geospatial-analysis/SKILL.md (Critical Rule block) | Added an explicit rule: use `to_crs("EPSG:4087")` with default params; do NOT build a custom PROJ string, set a custom `lon_0`, or recenter the CRS to handle the antimeridian — geopandas `.distance()` already handles boundary-spanning geometry. General rule about using named metric CRS as-is, no task literals. | Yes — the 9 passing trials already use plain EPSG:4087; this reinforces that exact path. |
| 1 | BODY | geospatial-analysis/SKILL.md (Distance Calculations code) | Inline comment at `METRIC_CRS = "EPSG:4087"`: "use as-is — do NOT recenter (no custom lon_0/PROJ string)." Point-of-action reminder. | Yes — additive comment, no behavior change for correct runs. |
| 1 | BODY | geospatial-analysis/SKILL.md (Common Pitfalls table) | Extended the "Antimeridian issues" row to also flag recentering the CRS (custom `lon_0`) as a pitfall; keep default EPSG:4087. | Yes — additive, restates the dominant correct behavior. |

## Verify-the-fix
- t3 trace's OWN stdout printed both computations: `naive EPSG:4087 (lon_0=0) = 3878.265897` (== gold 3878.27) and `recentered lon_0=180 = 3873.93` (the value it wrongly chose → assertion `3873.93 != 3878.27 within 0.01 delta`). Forbidding recentering leaves only the canonical EPSG:4087 path, which equals the gold. All 9 passing trials already produced 3878.27 with plain EPSG:4087, so the edit cannot regress them.

## Process & features used
- Subagents / worktrees: serial — a single skill and a single, cleanly-isolated failure cluster made fan-out unnecessary; diagnosis was a direct read of the 10 trajectories' scores + t3's stdout.
- Prior iterations read: none exist (this is the first iteration; LEDGER/RUNMAP show baseline only).

## Good things to PRESERVE
- The canonical-EPSG:4087-as-is guidance. Do NOT reintroduce any "recenter the projection to handle the antimeridian" advice — it is exactly what fails the tolerance test.

## Deliberately skipped
- The `unary_union` DeprecationWarning in traces — cosmetic warning, does not affect the result; no test asserts on it.
- No new script added: the agent already computes the correct value in 9/10 runs; the failure is choosing the wrong variant, not an inability to compute. A prose rule that removes the wrong variant is the minimal, safe fix; a script would risk overfitting the task-specific filtering logic against a ±0.01 km tolerance.
