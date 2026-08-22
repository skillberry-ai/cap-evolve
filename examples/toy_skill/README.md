# Example: toy_skill (zero-API, deterministic, capability = a skill package)

`toy_calc` proves the pipeline on a system prompt. This one proves it on a **skill
package**, and specifically on the part of a package prose cannot fix: the tasks are
arithmetic written the way people write it (`3 plus 4`, `1,200 + 5`), the seed skill
only *asks* for normalization in its body, and the deterministic stand-in agent gets
those wrong until a bundled `scripts/normalize.py` exists for it to run.

So the score can only rise by adding **code** to the package — the determinism lever
the `skill-package` capability pushes — and the accepted candidate's diff contains a
script, not just SKILL.md prose.

## Files
- `adapter.py` — a `CapabilityAdapter`: 10 arithmetic tasks, a stand-in agent that
  runs `scripts/normalize.py` when the SKILL.md points at it, and an exact-match scorer.
- `seed_capability/SKILL.md` — a valid seed skill with no bundled scripts.
- `mock_script.json` — the deterministic edit the `mock` optimizer applies: it CREATES
  `scripts/normalize.py` (with a `--self-check`) and adds the pointer line to SKILL.md.

## Run it
```bash
REPO=$PWD                       # cap-evolve repo root
export CAPEVOLVE_CORE=$REPO/core PYTHONPATH=$REPO/core CAPEVOLVE_SKILLS_DIR=$REPO/skills
export CAPEVOLVE_TOY_DATA=$REPO/examples/toy_skill
export CAPEVOLVE_MOCK_SCRIPT=$REPO/examples/toy_skill/mock_script.json

D=/tmp/toyskill; mkdir -p $D/.capevolve/project/adapters
cp $REPO/examples/toy_skill/adapter.py $D/.capevolve/project/adapters/
cp -R $REPO/examples/toy_skill/seed_capability $D/seed_capability
cp $REPO/examples/toy_skill/capevolve.yaml $D/.capevolve/project/capevolve.yaml

python3 -m cap_evolve.cli run --spec $D/.capevolve/project/capevolve.yaml \
    --project $D/.capevolve/project --run-ts demo
cap-evolve diff --best --run $D/.capevolve/runs/demo     # shows scripts/normalize.py
```

The candidate is validated by `skills/capabilities/skill-package/scripts/abstract.py`
before any rollout is paid for — including running the new script's `--self-check` —
so a candidate that ships broken code is never scored.
