# Anti-patterns — skill smells and why they hurt

> Load this when a draft "feels off" or to review an edit before keeping it. Each
> item is a documented Agent Skills anti-pattern with the reason, so you fix the
> cause, not the symptom.

## Description / triggering
- **First-person or mixed point of view** ("I can help with…"). → Inconsistent POV
  hurts skill discovery. Use third person ("Processes…", "Exports…").
- **Vague description missing user keywords.** → The skill never triggers because
  the words the user actually types aren't in the only text the model sees
  pre-trigger. Add the literal keywords.
- **ALL-CAPS imperatives in the description** (`CRITICAL`, `ALWAYS`, `MUST`). → A
  yellow flag that *over*-triggers current models. Fix over-triggering with
  specificity, not volume.
- **Key use case buried late.** → The listing truncates at ~1,536 chars; trigger
  words past the cut are invisible. Front-load.

## Body
- **Narrating why at length instead of instructing.** → Every body line is a
  recurring per-session token cost. State what to do; give a rule's reason briefly.
- **A wall of ALL-CAPS MUST/NEVER rules.** → Today's models follow *reasoning*
  better than rigid rules; reframe as "do X because Y". Reserve emphasis for the
  one thing that genuinely breaks if ignored.
- **Body over budget (>500 lines / ~5k tokens).** → Move detail into `references/`;
  the body is paid for on every trigger, references only when read.
- **Overfitting to the eval tasks.** → Fiddly task-specific rules hurt a skill used
  many times. Prefer general patterns/metaphors.

## References / structure
- **Nested references** (a reference file pointing to another). → The agent may
  only partially read a file (e.g. `head -100`) and miss the pointer, yielding
  incomplete information. Keep every reference **one level deep**, linked directly
  from SKILL.md.
- **A reference with no pointer.** → SKILL.md must say what each file contains and
  *when* to load it, or the model won't know to open it.
- **Long reference with no table of contents** (>300 lines). → Hard to navigate /
  partially read; add an early TOC.
- **Broken links.** → A `(references/…)` / `(scripts/…)` link to a missing file
  wastes a load attempt.

## Scripts
- **Re-implementing the same helper in prose across runs.** → Bundle it as a script
  the skill executes; code is repeatable where prose is only likely.
- **Not stating execute-vs-read intent.** → The agent doesn't know whether to run
  the script (output-only token cost) or read it as reference. Say which.

## Process
- **Selecting an edit on the iteration examples.** → That is overfitting. Keep an
  edit only if it raises the objective on a held-out split and clears the gate.
- **Multiple edits at once.** → You can't attribute the score change. Make ONE
  targeted edit per iteration, then re-measure.
