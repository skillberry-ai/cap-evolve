# Edit-design lessons (measured; shapes transfer, numbers do not)

Audit the measurement first: does feedback name the defect or only the tool? Does a helper fail silently
(bare except)? Did the rollout run, or is a 0.0 missing data? Repair scorers before crediting a failure.

Form by failure type:
- rule exists, skipped under pressure: prohibition + the symptom preceding it; restating makes it worse.
- right tool, wrong call shape: a positive recipe (the correct call, parts in order); don't-lists add output.
- required element missing: structural REQUIRED slot or code precondition, not a prose reminder.
- differs by situation: conditional on an observable predicate, not rule + exemptions.
No nuance clauses (a caveat degraded a winning recipe); exemptions do not scope.

Prefer code to prose where you own the tools: the one large accepted gain measured was a tool-level
precondition refusing the illegal write with a recovery-oriented error (+0.176 val). Edit tools and policy
TOGETHER when the policy names a behaviour the tool must enforce.

Narrated-not-executed (agent says it made the change, no mutating call in trace): a reminder cannot fix it.
Make confirm and execute one action; remove the primitives that let them come apart.

Guard closure: before adding a refusal, name what the agent can do INSTEAD; "do nothing" must stay
reachable (a no-op guard cost 0.288 by forcing a real change).
Auto-repairing a slipped tool call can accelerate a wrong action: ask what the rejected call would have done.
Verify an edit fires on the trace it targets and does not on 1-2 passing tasks (`pregate.py --trace`).
