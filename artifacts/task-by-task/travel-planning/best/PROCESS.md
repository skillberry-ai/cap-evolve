# PROCESS — what I did this iteration (explainability; REQUIRED)

## Ranked issue list (clusters by # failing tasks × trials, biggest first)
| rank | cluster | tasks | shared root cause | tag | change class |
| --- | --- | --- | --- | --- | --- |
| 1 | empty attraction on departure/return travel days | travel-planning (4/10 trials failed) | Agent leaves `attraction: "-"` ONLY on travel days involving the departure city — Day 1 "from <origin> to X" and the final "from X to <origin>" day. `test_attractions_non_empty` asserts EVERY day's attraction is non-empty and != "-". Only failing test. | BEHAVIORAL/DELIVERY (guidance never reaches the agent) | SCRIPT + DESCRIPTION (search-attractions) |

Diagnosis evidence (this iteration's `./trajectories/`, champion cand_0002):
- Extracted the written itinerary from all 10 trials. Empty-attraction days are EXCLUSIVELY
  departure-city travel days: t1[1] t2[1] t3[1,7] t9[1,7] failed; t0,t4,t5,t6,t7,t8 passed.
  Passing runs fill Day 1 with real *departure-city* POIs (Minnehaha Falls, Mall of America,
  Minneapolis Sculpture Garden) — the dataset HAS them (20 Minneapolis rows). So the fillable
  data exists; failing runs simply never query the origin city and leave the day "-".
- **Delivery root cause (the key finding):** in ALL 4 failing trials the agent NEVER launched
  the search-attractions skill and NEVER read `search-attractions/SKILL.md` — it discovers the
  skill via `find` and runs/reads `search_attractions.py` directly. So cand_0002's SKILL.md
  fixer instruction + the every-day prose never entered context. But ALL 10 trials (pass AND
  fail) construct the `Attractions` class (every trace prints "Attractions loaded."). That
  `__init__` is the ONE code path guaranteed to execute in 100% of trajectories — the correct
  place to deliver the rule, right when the agent is gathering attractions.
- This is why prose-only (cand_0001) plateaued and the SKILL.md-gated fixer (cand_0002) only
  fired 1/10 (t0): both live in a file the failing runs never read. BEHAVIORAL/DELIVERY gap.

## Changes made this iteration (one row per edit)
| cluster | edit class | file | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | SCRIPT (delivery) | search-attractions/scripts/search_attractions.py | Print a one-time `ITINERARY REMINDER` in `Attractions.__init__` (guarded by a class flag) — fires in 100% of trajectories (CLI or import). It states EVERY day incl. departure/return/"from A to B" travel days needs a real attraction, to query the departure/return city too, and to run fill_attractions.py as a final net. No data/return-value change. Generalizes: no city/route literal — "departure/return city" is generic. | Yes — the DataFrame/string the agent parses is byte-identical; only extra stdout. Passing runs write identical JSON (verified). |
| 1 | SCRIPT (read channel) | search-attractions/scripts/search_attractions.py (module docstring) | Same rule + fixer command added to the top-of-file docstring, so runs that READ the .py (t1) instead of executing see it too. | Yes — comment only; no behavior change. |
| 1 | DESCRIPTION | search-attractions/SKILL.md frontmatter | Front-load the travel-day/departure-return-city case into the always-injected `description` (the one skill text guaranteed in context even without launching). Third-person, no all-caps. | Yes — description only steers when this skill is relevant; other skills' selection unchanged. |

Kept from cand_0002 (unchanged, still valid): fill_attractions.py fixer + SKILL.md "Required
final step" body + every-day prose. They backstop when the agent DOES read SKILL.md/runs the
fixer; the new reminder now delivers the same intent through the channel failing runs use.

## Verify-the-fix (ran on the ACTUAL failing inputs)
- Ran `search_attractions.py --city Cleveland` and an import + double-construct against the real
  bundled attractions.csv: reminder prints exactly ONCE (class-flag guard), then the unchanged
  attraction table; `run()` still returns a DataFrame. Data output identical to before → passing
  runs unaffected.
- Fixer still valid: `fill_attractions.py` imports cleanly; fill_plan on a reconstructed failing
  plan (Day1 "from Minneapolis to Cincinnati"="-", Day7 "from Cincinnati to Minneapolis"="-")
  → Day1 filled with Cincinnati POIs, Day7 with Minneapolis POIs. So if the agent now runs it
  (reminder names the command), the "-" days are repaired deterministically.
- Blast radius: only search-attractions touched. The other 5 skills (cities/driving/accommodations/
  restaurants/flights) and every other verifier test (budget, transport, meals, pet-friendly,
  structure) are untouched — the reminder/description only concern the attraction field.

## Process & features used
- Subagents / worktrees: none — single failing cluster (one task, one failing test). Serial
  trajectory analysis (per-trial itinerary extraction + channel-usage audit) + direct dataset
  verification was sufficient and cheaper than fan-out.
- Prior iterations read: cand_0001 (prose, ACCEPTED→0.20) and cand_0002 (fixer+body, ACCEPTED→
  0.60). Both improvements live in SKILL.md, which failing runs never read — hence the plateau.
  This iteration switches LEVER from "put guidance in SKILL.md" to "deliver guidance through the
  script the agent actually executes (Attractions.__init__)".

## Good things to PRESERVE
- The `Attractions.__init__` itinerary reminder (guaranteed-delivery channel) + docstring pointer.
- cand_0002's fill_attractions.py fixer + its SKILL.md "Required final step" section.
- cand_0001's every-day attraction prose.

## Deliberately skipped
- All other skills: every verifier test they touch already PASSES; editing them is speculative
  and risks regression (fails SAFE). Only search-attractions is in the failing cluster.
- Did NOT add yet another SKILL.md prose paragraph as the fix (cand_0001/cand_0002 RESULTs show
  SKILL.md guidance is not reliably read by failing runs — refuted lever).
- Deployed artifact here is the travel-search skills, NOT docx/pptx/xlsx/pdf from the generic
  INSTRUCTIONS boilerplate — I edited the actual deployed skills.
