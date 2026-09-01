# PROCESS — what I did this iteration (explainability)

## Ranked issue list (clusters by # failing trials × recoverable score, biggest first)
| rank | cluster | tasks/trials | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | `test_checkout_fast` fails (~920ms vs <800ms) | react-performance-debugging, 4/10 trials (t1,t6,t7,t9) | Agent reads the `/api/checkout` POST route but wrongly concludes it is "already optimal" because it uses `Promise.all`. It misses the HIDDEN waterfall: `const [user,config]=await Promise.all([...]); const profile=await fetchProfile(user.id)` gates `profile` behind the slower, unrelated `config` (delays: user=400, config=600, profile=300 → 900ms; correct = user then parallel(config,profile) = 700ms). Every trial that edited the checkout route PASSED; every trial that didn't FAILED. | KNOWLEDGE + BEHAVIORAL | SCRIPT (auditor) + BODY (misconception + vanilla fix) |

Only ONE failing cluster exists in this iteration's trajectories — all 4 failures are the identical `test_checkout_fast` assertion. The other 10 verifier tests pass in every trial.

## Changes made this iteration
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | SCRIPT | `react-best-practices/scripts/audit-waterfalls.mjs` (new) | Static auditor that scans `app/api/**` + server files and flags HIDDEN-WATERFALL (dependent call awaited after a `Promise.all` it only partially uses), SEQUENTIAL-WATERFALL, and BLOCKING-SIDE-EFFECT, with file+line. Mechanically surfaces the exact residual waterfall the agent rationalized away. General pattern detection — no filenames/values hardcoded. | Yes — advisory (exit 0). Zero false positives on the correctly-fixed checkout/products versions (verified); passing trials already fix these routes. |
| 1 | BODY | `react-best-practices/SKILL.md` | Added "Audit EVERY API route" section: run the auditor over ALL routes incl. POST routes page loads never hit; "Promise.all does not mean optimal"; await only the true dependency. Execute-intent pointer to the script. | Yes — additive section; does not alter any existing rule the agent already follows. |
| 1 | BODY | `react-best-practices/AGENTS.md` §1.2 | Added a plain-Promise "Correct" fix (no `better-all` dependency, which the app doesn't have) + a "Common misconception" callout busting "it depends on user so it must wait". | Yes — additive; keeps the existing better-all example. |
| 1 | REFERENCE | `react-best-practices/rules/async-dependencies.md` | Mirrored the plain-Promise fix + misconception into the drill-in rule file. | Yes — additive. |

## Verify-the-fix (trace → what the fix now does on those exact inputs)
- Ran the auditor on the real `/api/checkout` source (from t0 trace): flags `[HIDDEN-WATERFALL] profile ... waits for {config} for no reason` — the precise miss in t1/t6/t9 where the agent said "checkout already parallelizes correctly, no change needed."
- Ran it on original `/api/products` and homepage `page.tsx`: flags SEQUENTIAL-WATERFALL + BLOCKING-SIDE-EFFECT (routes agents already fix). Ran it on the correctly-fixed checkout/products (from passing traces) and a single-await component: ZERO findings → no false positives that could push a passing route onto a worse path.
- `node --check` passes; runnable with plain `node` (no ts-node/deps).

## Process & features used
- Serial (single failing cluster, one task in all splits) — no need to fan out subagents. Diagnosed by extracting per-trial edited-file sets + agent reasoning from `./trajectories/*.json` and per-trial `verifier/pytest-output.txt` under `bench_jobs/`.
- Prior iterations: none (this is the seed iteration; LEDGER/RUNMAP empty).

## Good things to PRESERVE
- The auditor + "Promise.all ≠ optimal" guidance. Every trial that touched checkout passed; the ONLY lever needed is making the agent reliably recognize + fix the hidden waterfall.

## Deliberately skipped (cluster + why)
- `browser-testing/SKILL.md` references `detect-flicker.ts` which does not exist (dead link). NOT tied to any failing verifier test (no CLS/flicker test in this task's suite) — editing it would be a speculative change to a skill path only exercised by passing behavior, violating REAL/SAFE. Left untouched.
