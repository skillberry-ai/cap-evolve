# FRAMEWORK-IMPROVEMENTS — suggestions for cap-evolve itself (cross-run)

NOT about this capability or this run's result — about what cap-evolve the FRAMEWORK should change so FUTURE runs (any capability, any project) go better: a confusing prompt section, a missing tool, a file you wished existed, a gate that felt wrong. Optional most iterations; add an entry whenever something about the framework itself (not the task) got in your way or surprised you.

## From run_suite round 8 — an interrupted round leaves a paid, unbooked gate with no resume path

**What happened.** The agent-mode driver died on an `api_error` (`host` event:
`terminal_reason: api_error`, `returncode: 1`, `num_turns: 341`, then `host_retry attempt 1`) at the
point *between* `round.py` finishing its val evaluation and the driver calling `commit.py`. The retry
driver inherited: 120 fresh val rollouts, a complete `work/round_i7.json`, a candidate dir — and no
decision event, no journal entry, and a `PROCESS.md` still holding the round-2 candidate's text.
`spent.iterations` read 7 while 8 rounds' worth of rollouts existed on disk.

**Why this is a framework gap, not a driver mistake.** The round was fully paid for and fully
decidable (`gate_check.py` reproduced `verdict: reject`, `verdict_stable: true` from the rollouts
alone, with zero re-evaluation). But nothing in the run dir *announces* that state. The retry driver
had to infer it by diffing `events.jsonl` tags against `rollouts/val/*__<tag>__t0.json` filenames.
A driver that instead assumed the round had not run would re-evaluate the same tag — which, per
`spend.py`'s own warning, REPLACES `t0` and buys no new evidence while destroying the paid reading.

**Concrete suggestions, cheapest first.**
1. **`spend.py` should report unbooked-but-evaluated candidates.** It already reads `events.jsonl`
   and the rollout tree. A field like `"unbooked_candidates": [{"tag": "r8_cut", "rollouts": 40,
   "split": "val", "has_decision_event": false, "round_table": "work/round_i7.json"}]` would make
   the resume state explicit at the one call every round already starts with, and would let its
   `recommendation` say `book_pending_round` instead of `narrow_scope`.
2. **`host.py` should re-inject the resume state on a retry attempt.** The retry's launch prompt is
   byte-identical to attempt 0's, so the new driver is told the run was "already baselined and handed
   over" with no mention that a round is mid-flight. One appended paragraph naming the unbooked tag
   would remove the entire inference step.
3. **Order the per-round handover write before the gate, not after.** The framework's own instructions
   ask for `PROCESS.md`/`JOURNAL.md` "before `commit.py`", which in practice means after the gate
   returns — the longest-running, most crash-prone window in the round. Since intent is knowable at
   `prepare_candidate.py` time and gate numbers are always reconstructible from rollouts, the guidance
   (and ideally `prepare_candidate.py` itself, by stamping a dated skeleton with the parent tag and
   the diff) should put intent on disk at candidate-prep time. Here, the diff and the full measurement
   survived the crash while the rationale did not — exactly backwards from what is cheap to recover.
4. **`prepare_candidate.py` should not silently carry a stale `PROCESS.md` forward.** Copying the
   previous candidate's explainability file into a new candidate dir means a crash (or a forgetful
   driver) yields a `PROCESS.md` that confidently describes a *different* edit — worse than an empty
   one, because it reads as filled in. Stamp a skeleton with the new tag, or leave it empty.

<!-- cap-evolve:framework-improvements-append-below -->
