# Inputs for <skill-name>

This file is the contract for what the skill consumes. The using-agent reads it
and, for every **NEEDED** input that is missing, **asks the user** before doing
anything else — quoting the path, how to retrieve it, and the alternatives.
Never invent a NEEDED input.

## NEEDED  (the skill cannot proceed without these)

- **<input_key>**: <what it is, in one line>
  - where: `<expected path, e.g. examples/<bench>/tasks.jsonl>`
  - how to get it: `<command or steps to produce it>`
  - options: `<alternative forms — a file | a directory | a callable in adapters/>`

## RECOMMENDED  (improve results; degrade gracefully if absent)

- **<input_key>**: <what it is>
  - where: `<path>`
  - how to get it: `<command>`
  - default if absent: `<the fallback behavior + a note that it was skipped>`

## Notes
- Paths are relative to the repo root unless absolute.
- Anything the agent fills here should be written back so the run is reproducible.
