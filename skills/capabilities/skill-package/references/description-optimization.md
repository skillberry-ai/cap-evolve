# Description optimization — the trigger-tuning playbook

> The `description` is the **only** thing loaded before a skill triggers, so it is
> the single highest-leverage edit. This file is the depth behind lever 1 in
> `SKILL.md`. Load it when fixing under/over-triggering.

## What a good description does
A description is read by the model to decide, among 100+ skills, whether THIS one
applies to the current task. It must:

1. **Be third person.** "Processes Excel files and generates reports", not "I can
   help you with Excel". Inconsistent point-of-view causes discovery problems.
2. **State WHAT it does AND WHEN to use it.** The when-to-use information lives in
   the description, not the body — the body is not loaded until after the decision.
3. **Use the keywords a user would naturally say.** If users say "export", "CSV",
   "download a table", those words belong in the description. Missing keywords are
   the most common cause of a skill that never triggers.
4. **Front-load the key use case.** The listing truncates `description +
   when_to_use` at ~1,536 chars; the most important trigger words must come first.

## Diagnosing the failure direction
- **Under-trigger** (didn't fire when it should have) → the description is too
  vague or missing keywords. Enumerate the phrasings and contexts that should fire
  it, including when the user doesn't name the skill. Claude tends to under-trigger,
  so it is fine to be slightly **pushy**: "Use when the user mentions X, Y, or Z,
  even if they don't say 'skill'."
- **Over-trigger** (fired when it shouldn't have) → make the description **more
  specific** and name the **near-miss cases it does NOT cover**. Do **not** reach
  for ALL-CAPS — `CRITICAL`/`ALWAYS`/`MUST` *increase* over-triggering on current
  models.

## Selecting a description honestly (don't overfit)
1. Assemble a held-out set: **should-trigger** prompts and **should-NOT-trigger**
   prompts, the latter including **near-miss negatives** (prompts that look close
   but must not fire).
2. Propose candidate descriptions.
3. Measure trigger-rate on the held-out set (and downstream task success on the
   objective).
4. **Keep the candidate that scores best on the held-out set**, not on the
   iteration examples. (skill-creator splits its eval queries and selects by the
   held-out/test score — the same train/val/test discipline cap-evolve enforces.)

Caveat: **trivial single-step tasks may not trigger any skill** regardless of
wording — don't chase those as triggering failures.

## Quick checklist
- [ ] Third person, no "I"/"you can help".
- [ ] Says what AND when.
- [ ] Contains the literal keywords users say.
- [ ] Key use case in the first ~1 sentence (survives the 1,536 truncation).
- [ ] No ALL-CAPS imperatives unless under-triggering is the measured problem.
- [ ] ≤1024 chars, no XML tags.
