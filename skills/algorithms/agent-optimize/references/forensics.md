# Forensics: read the raw evidence before editing

Clipped summaries hid the real failure in past runs (a 200-char clip of tool args). Read FULL tool-call
arguments and the FULL conversation of 2-3 failing trials per chosen cluster. Val or train, never test.

Dump one trial (ids come from `clusters.json` `exemplar_trace_ids`):

    python -m json.tool "$R/rollouts/val/<task>__<tag>__t<k>.json" > "$R/work/trace_<task>.txt"

then Read that file in slices. Never Read `clusters_full.json` (MBs of embedded traces).

Classify before editing:
- Deterministic tool bug (same tool-error signature, wrong args reaching a tool, silent exception): fix in
  tool code; one cluster is enough.
- Policy/prompt failure (agent chose wrong action or skipped a step): policy edit, or a code guard if you
  own the tool. See tool-edit-lessons.md.

Composite-tool pitfall: the gold compares VISIBLE write calls. A composite tool that performs a write
internally makes the write invisible and the task fails (a past candidate did exactly this). Keep each
write a separate, visible call. Replay one full trace end to end on the candidate before paying for a
multi-task probe.

Delegate diagnosis of many failing shards to read-only Task subagents: one per cluster, told to read raw
traces, edit nothing, and RETURN findings as their final message (mechanism, evidence trace ids,
proposed fix and its predicted tasks). A subagent that only writes files or "will report later" reports
nothing; the final message is the deliverable. At most 2 at a time.
