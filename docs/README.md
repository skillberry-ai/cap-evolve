# docs

The design record for the parsec experiments: what was decided and why, not how to run
anything. The code these documents describe — adapters, scoring, the CCC/podman stack —
lives on `parsec-intake_v4` and deliberately did not move here; this tree holds only the
narrative around it, per this branch's own scope (see the root [`README.md`](../README.md)).

`specs/` are design documents written before the work they describe; `plans/` are the
implementation plans that carried a design out, task by task.

| file | what it is |
|---|---|
| [`specs/2026-09-09-parsec-v4-intake-design.md`](specs/2026-09-09-parsec-v4-intake-design.md) | the original v4 intake design — task set, target, scoring |
| [`specs/2026-09-17-parsec-v4-task-by-task-optimization-design.md`](specs/2026-09-17-parsec-v4-task-by-task-optimization-design.md) | design for the T-arm (task-by-task) optimization approach |
| [`specs/2026-09-21-parsec-v4-experiment-plan-design.md`](specs/2026-09-21-parsec-v4-experiment-plan-design.md) | the multi-arm (T/C/G) experiment plan; this is the `SPEC` constant [`scripts/build_v4_t_results_json.py`](../scripts/build_v4_t_results_json.py) names |
| [`specs/2026-09-22-parsec-v4-ccc-handoff.md`](specs/2026-09-22-parsec-v4-ccc-handoff.md) | handoff design for porting v4 onto the CCC/LSF cluster |
| [`plans/2026-09-17-parsec-v4-task-by-task-optimization.md`](plans/2026-09-17-parsec-v4-task-by-task-optimization.md) | implementation plan carrying out the T-arm design above |
| [`plans/2026-09-21-parsec-v4-results-pr.md`](plans/2026-09-21-parsec-v4-results-pr.md) | implementation plan that built this branch's original (pre-arm-split) v4 results tree |
| [`plans/2026-09-23-parsec-v4-ccc-port.md`](plans/2026-09-23-parsec-v4-ccc-port.md) | implementation plan carrying out the CCC-port design above |
| [`HANDOFF.md`](HANDOFF.md) | the session handoff written at the start of v4 intake, before any v4 work had run |
