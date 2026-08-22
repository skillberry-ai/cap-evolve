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

## Selecting a description honestly — run the loop, don't eyeball it
A trigger decision is stochastic, so one sample per query is noise and hand-judging
drifts between candidates. `scripts/trigger_eval.py` makes it deterministic:

```bash
python scripts/trigger_eval.py --eval-set trigger_eval.json --skill <skill_dir> \
    --judge-cmd '<a shell command that answers YES/NO on stdout>' \
    --description "<candidate description>" --trials 3
# -> {"train_score": .., "heldout_score": .., "per_query": [..], "select_on": "heldout_score"}
```

1. Write ~20 realistic queries — 8-10 **should-trigger** (varied phrasing, including
   cases where the user never names the skill) and 8-10 **should-NOT-trigger**, whose
   value is in the **near-misses**: same keywords, different actual need. An obviously
   irrelevant negative tests nothing. Save as
   `[{"query": "...", "should_trigger": true}, ...]`.
2. The script splits 60/40 by seed and runs each query `--trials 3` times, so the
   score is a rate rather than a coin flip.
3. Propose candidate descriptions and re-score each one with `--description`.
4. **Keep the candidate with the best `heldout_score`** — never the train score. Same
   discipline as cap-evolve's val/test seal, for the same reason.

Queries must be substantive: a trivial one-step request ("read file X") won't trigger
any skill regardless of description quality, so it measures nothing.

Caveat: **trivial single-step tasks may not trigger any skill** regardless of
wording — don't chase those as triggering failures.

## Quick checklist
- [ ] Third person, no "I"/"you can help".
- [ ] Says what AND when.
- [ ] Contains the literal keywords users say.
- [ ] Key use case in the first ~1 sentence (survives the 1,536 truncation).
- [ ] No ALL-CAPS imperatives unless under-triggering is the measured problem.
- [ ] ≤1024 chars, no XML tags.
