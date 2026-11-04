# PROCESS — what I did this iteration (explainability; REQUIRED)

## HEADLINE — read this before anything else

**cand_0003 was not a failed edit. It was a working edit with a leaky guard, and the run is
produced a **perfect answer** — including the exact `22:00` → `06:00` midnight-crossing

as "did nothing". That reading is wrong, and it is the most important thing in this handover:
cand_0003 **moved the distribution from a pinned-wrong answer to a bimodal one with a correct
mode**. This iteration keeps its text and closes the specific leak that cost the other 3.

| rank | cluster | tasks | shared root cause | tag (KNOWLEDGE / BEHAVIORAL / CAPABILITY-GAP) | planned change class |
| --- | --- | --- | --- | --- | --- |


Ground truth: `start_time` = 22:00 UTC day 20778, `end_time` = 06:00 UTC day 20779 (crosses midnight).

|---|---|---|---|---|---|---|

Three facts follow, and they set the whole strategy:
   and the behaviour it asks for is achievable.**
   independently — so cand_0003's derive-by-addition ban **did land**. The residual error is
   a single-step remainder slip, nothing to do with derived endpoints.
   guard was SILENT on both. Verified by computation.

Diagnosis chain across the run: wrong-arithmetic (cand_0001's theory, refuted) →
derived-endpoint (cand_0003's theory, **fixed**) → **remainder slip with no detecting check**
(this iteration).

## Changes made this iteration (one row per edit)
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| A | KNOWLEDGE | `icinga_agent.md` — **Step C (the actual fix)** | Multiply back: `days×86400 + hour×3600 + minute×60 == original epoch?` An *equality on a number already in front of the agent*, not a plausibility judgement — which is why it catches an error the agent otherwise cannot see. Difference diagnoses the slip (multiple of 3600 ⇒ hour off; ±86400 ⇒ day off). | Yes — silent on the correct answer, verified below |
| A | KNOWLEDGE | `shared_context.md` — one bullet | cand_0003's bullet plus the multiply-back check, as the genuinely domain-general half (epoch fields exist in job times, provision records, cost partitions). Still *one* bullet: cand_0001 put ~75 lines here for zero behavioural change, so size in this file is a refuted lever. | Yes — additive, no existing rule altered |

## Verify-the-fix (the trace it targets → what the check now does on those exact inputs)
- **FIRES on s1** (agent's own numbers 10:00, day 20778): `20778×86400 + 10×3600 = 1795255200` vs epoch `1795298400` → differ by **−43200 (−12 h)** → not equal → agent is told to redo Step A.
- **FIRES on s2 and s3** (02:00, day 20778): `20778×86400 + 2×3600 = 1795226400` vs `1795298400` → differ by **−72000 (−20 h)** → not equal → redo Step A.
- **SILENT on the correct start** (22:00, day 20778): reconstructs to `1795298400`, exactly equal → no false alarm.
- **SILENT on the correct end** (06:00, day 20779): reconstructs to `1795327200`, exactly equal → no false alarm.
- **Contrast — cand_0003's day-count guard on the same two failures:** distinct days = 1, dates written = 1 → **SILENT**. That is exactly the hole being closed, and the reason this is a different edit rather than a re-wording.
- Both directions were computed in Python against the agent's *own printed intermediate

### Safety checks (mechanical, re-run against the final files)
- All 14 `forbidden.none_of` substrings, case-insensitive, against both edited files: **0 hits**. (The matcher has no polarity guard, so prose that *denies* the window-as-duration reading can itself trip it; the text keeps the window span and the mute figure on separate nouns.)
- Task literals — all three epochs, `18000`, host, service, author, change number, downtime GUID, both graded strings `22:00`/`06:00`, both task dates, task phrasing: **0 hits**.

### Generalization test (restate with no task-specific noun)
*When a result gives a time as a large epoch integer, convert each one independently via
staged subtraction, then verify by reconstructing the epoch from your answer and comparing
is right.* No entity from this task appears. The general half lives in `shared_context.md`,
the downtime-specific procedure in `icinga_agent.md`.

## Process & features used
- **Subagents / worktrees / parallel features used (or: "serial fallback because …"):** none —
  serial, deliberately, and consistent with cand_0001 and cand_0003. One task, one tool call
  directions — precisely what fan-out degrades through summarization. The run brief pushes
  fan-out hard, but fan-out is a breadth tool and this run has no breadth. Recorded in
  `FRAMEWORK_IMPROVEMENTS.md`.
- **Prior iterations I read + what I learned:**
    span cross-check is provably silent here (both spans are 8 h).
  - `prior_iterations/cand_0002` — byte-identical to `seed` (I re-diffed all 8 files and
    that it is the sole candidate in this run that has ever produced a correct answer.
  - `RUNMAP.md` / `LEDGER.md` / `INSIGHTS.md` / `META_INSIGHTS.md` — all read in full.

## Good things to PRESERVE (do not let a future iteration undo these)
- **cand_0003's `icinga_agent.md` text is the only thing in this run that has ever produced a
- The derive-by-addition ban and the "overnight windows are legitimate, do not normalise"
- The separation of the window span from the mute figure onto different nouns. The forbidden
  fact is an unpolarised substring match, so merging them — even to deny the wrong reading —
- Step C, the reconstruction check, if it works: it is the only check tried in this run that
  fires on the observed failures and stays silent on the correct answer.

## Deliberately skipped (cluster + why)
- **Re-wording cand_0001's `shared_context.md` block** — refuted: ~75 lines, zero behavioural change. The diagnosis was wrong, not the wording.
- **A span cross-check** — refuted by computation: agent span 8 h == true span 8 h, silent on every failure in this run. Never re-propose.
- **cand_0003's day-count check as the *primary* guard** — now measured as insufficient: silent on all 3 of its own failures. Kept only as a secondary signal inside the midnight-crossing paragraph.
- **The other 5 domain agent files** (aap2, babylon, cost, ocpv, security) — not in this task's prompt footprint.

## Escalation (real capability gap, cannot be fixed in this phase)
No tool converts an epoch to a UTC timestamp and there is no code layer in this phase, so the
agent is structurally forced into mental 10-digit date arithmetic. Every tool call in every
error *self-detectable*, which is the strongest prompt-only move available, but prose cannot
make it impossible. A deterministic epoch → ISO-8601 helper, or `query_icinga` returning
derived `start_time_utc`/`end_time_utc` alongside each epoch, would eliminate the class
outright. Carried from cand_0001 and cand_0003, and now at its sharpest: with the procedural
bug fixed, the *entire* remaining gap is one modular-arithmetic step on a large integer — the
most mechanical, most automatable failure imaginable, and the least appropriate thing to ask a
language model to do by hand.
