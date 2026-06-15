## What & why
<!-- What does this change and why? Link any issue. -->

## Checklist
- [ ] `python -m pytest core/tests -q` passes
- [ ] `python skills/_registry/build_manifest.py skills` is clean (no errors)
- [ ] Any new/changed skill's `scripts/check.py` is green
- [ ] Honesty invariants untouched (gate on val, test sealed) — or explained
- [ ] Docs updated (README/skill SKILL.md) if behavior changed
