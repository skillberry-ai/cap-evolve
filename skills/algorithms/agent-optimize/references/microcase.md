# Micro-tests — TDD-style, before any rollout is spent

A candidate claims to fix a diagnosed defect via a specific MECHANISM (a guard, a call-shape
change, a different tool selected). That claim is checkable in seconds, deterministically, on the
one call or turn where the defect lives — no LLM judge, no multi-turn episode, no rollout. This
adopts Harbor/Terminal-Bench's task shape (`task.yaml` + fixture/environment + a `tests/` dir that
asserts pass/fail and writes a reward without an LLM judge), scoped down from "a whole task" to
"the one call or turn the defect lives in" (#434 section 3, #436).

## Schema

```
$R/microcases/<cluster_id>/
  case.yaml       # {id, cluster_id, source_task_ids, source_rollout, timeout_s,
                  #  expects: guard_fires|call_shape|tool_selected, assert: {metric, op, value}}
  fixture/          # extracted VERBATIM from the diagnosed rollout — never invented
  reproduce.py      # replays the fixture against the candidate directly — one tool call
                    # or one narrow unit, never a full multi-turn episode, no LLM
  assert.py         # deterministic pass/fail against case.yaml's `assert` spec, exit 0/1
```

`reproduce.py`/`assert.py` are necessarily project-specific (they know the candidate's tool
module) — `microcase.py` cannot write them for you, only scaffold the fixture and the case
metadata from a REAL diagnosed rollout, so the one project-aware step (how to instantiate the
minimal state the fixture's calls need) is the only thing left to fill in.

## Authoring a case from a diagnosed cluster

```bash
python "$A/microcase.py" gen \
    --rollout "$R/rollouts/val/<task>__<tag>__t<k>.json" \
    --cluster-id <the diagnose.py cluster's id> --expects guard_fires \
    --description "<one line: what the mechanism must do>" \
    --assert-metric <field-name-in-reproduce.py's-result> --assert-op "<=" --assert-value 1 \
    --out "$R/microcases/<cluster_id>"
```

This extracts every tool call in the rollout's trace verbatim into `fixture/calls.json` and
scaffolds `case.yaml` + a `reproduce.py` stub with a marked TODO. Finish the TODO once per
cluster (construct the minimal state the fixture's calls need, replay them against the
candidate's own tool module, write the observed field(s) `assert.py` will check) — every
candidate that later targets the same cluster reuses the finished case for free.

## Running it

```bash
python "$A/microcase.py" run-all --cases-dir "$R/microcases" --project "$P" --candidate "$R/work/$TAG"
```

Three outcomes, not two — this is the same "missing data is not a zero" discipline
`taskeval.py`'s `infra` counter already applies:

* `pass` — the mechanism fires as claimed.
* `fail` — it provably does not. `micro_test_fail: true` in the summary →
  `commit.py --decision reject --reject-basis micro_test_fail`, no screen, no full val paid.
* `error` — `reproduce.py` hit an environment gap (a missing project dependency, not a
  candidate defect) or its own contract was violated. Fix the case before trusting either a
  pass or a fail measured while it was erroring.

A candidate with no applicable micro-case skips this step; it is a filter, not a requirement, and
`run-all` never touches the run dir's budget or state — a micro-test cannot itself accept anything,
only kill cheaply before a rollout is spent.

## Worked example

`skills/algorithms/agent-optimize/scripts/microcase.py`'s own docstring and
`core/tests/test_microcase.py` carry a full worked example grounded in a real diagnosed run: a
duplicate ledger write from re-issuing the same mutating call twice on one record. The seed fails
the case in ~0.15s (2 entries instead of 1); a candidate carrying the real accepted merge-guard
mechanism passes it — before either was ever run through a task rollout.
