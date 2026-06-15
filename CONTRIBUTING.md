# Contributing to agent-capo

Thanks for helping! agent-capo is designed so that extending it almost never means
touching core — you add a self-contained skill.

## Dev setup
```bash
git clone <repo> agent-capo && cd agent-capo
pip install -e ./core        # or: export AGENT_CAPO_CORE=$PWD/core
python -m pytest core/tests -q          # 28 tests, zero API cost
python skills/_registry/build_manifest.py skills   # rebuild the registry
```

## Add a capability / algorithm / optimizer (the 3-step pattern)
1. `cp -R templates/skill skills/<component>/<your-skill>` where `<component>` is
   `capabilities`, `algorithms`, `optimizers`, or `phases`.
2. Fill `SKILL.md` (frontmatter: `name` ≤64 chars `[a-z0-9-]`, a "Use when…"
   `description` ≤1024 chars, `component`, `needs`/`provides`, `sources`), and `scripts/{abstract,check,run}.py`. Add `references/*.md`,
   `prompt/PROMPT.md`, or `inputs/INPUTS.md` ONLY if they carry real content —
   never ship the empty template placeholders. Cite real sources.
3. `python skills/_registry/build_manifest.py skills` then
   `python skills/<component>/<your-skill>/scripts/check.py` — must print
   `"ok": true`.

See [docs/EXTENDING.md](docs/EXTENDING.md) for the token vocabulary and wiring.

## House rules (don't regress)
- **Honesty lives only in `core/agent_capo`** — never fork splits/gate/seal
  into a skill. Gate on val, seal test, report variance.
- **Skills stay host-agnostic.** `scripts/run.py` must print a single JSON object
  to stdout (the contract), and must not depend on a specific agent host.
- **Zero runtime deps in core.** Optional features go behind extras.
- Add a test for any core change (`core/tests/`). Run `python -m compileall core skills`.

## Quality bar for skills
- SKILL.md body under ~500 lines (it is the primary doc); references one level deep with a TOC if long, and only when filled.
- A real `check.py` smoke test (not just an import) that fails on stubs and on
  non-determinism.
- Ground claims in cited papers/repos/docs.

## Reporting bugs / ideas
Open an issue with a minimal repro (a tiny adapter + `acapo check` output is ideal).
The roadmap in [docs/ROADMAP.md](docs/ROADMAP.md) lists prioritized work.
