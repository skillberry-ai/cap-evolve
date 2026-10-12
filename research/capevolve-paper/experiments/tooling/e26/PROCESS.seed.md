# PROCESS — what I did this iteration (explainability; REQUIRED)

Fill this in as you work. It is the human-readable record of HOW this iteration was done and is snapshotted with the candidate, so anyone can see your reasoning. Be concrete.

## Ranked issue list (clusters by # failing tasks × trials, biggest first)
Re-cluster ALL of the current champion's failures every round, not just last round's. agent-optimize's commit.py refuses a header-only table (--missing-ranked-issues-justification is the escape hatch).
| rank | cluster | tasks | shared root cause | tag (KNOWLEDGE / BEHAVIORAL / CAPABILITY-GAP) | planned change class |
| --- | --- | --- | --- | --- | --- |

## Changes made this iteration (one row per edit — aim for MULTIPLE classes, incl. a NEW tool when a cluster needs one)
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |

## Verify-the-fix (one line per change: the trace it targets → what the guard/computation/new-tool now does on those exact inputs)
- 

## Process & features used
- Subagents / worktrees / parallel features used (or: "serial fallback because …"):

## Good things to PRESERVE (do not let a future iteration undo these)
- 

## Deliberately skipped (cluster + why — already-passing / needs gold / infra noise)
- 

---

# DIAGNOSIS.json — machine-readable diagnosis (REQUIRED under agent-optimize)

In addition to PROCESS.md, write a DIAGNOSIS.json file to make your diagnosis machine-readable for the dashboard and graph.jsonl (cluster_ids/subset). agent-optimize's commit.py refuses a decision without one (--missing-diagnosis-justification is the escape hatch); for other algorithms it is optional, and if absent the dashboard will parse PROCESS.md tables when present, or show only outcome data.

The schema:
```json
{
  "candidate": "cand_NNNN",
  "headline": "Brief summary of this iteration's strategy",
  "clusters": [
    {"id": "A", "name": "Short cluster name",
     "detail": "Root cause explanation", "tasks": ["task-id", ...],
     "scope": "BOUNDED|WIDESPREAD|SYSTEMIC", "latent": false,
     "tag": "KNOWLEDGE|BEHAVIORAL|CAPABILITY-GAP"}
  ],
  "edits": [
    {"id": "E1", "title": "What this edit does",
     "files": ["prompt.md"], "lever": "CONTRACT|KNOWLEDGE|BEHAVIORAL|...",
     "clusters": ["A"], "blast_radius": "BOUNDED|MODERATE|WIDE",
     "verified": "How you tested it"}
  ],
  "skipped": [{"title": "What was skipped", "reason": "Why"}],
  "techniques": ["technique 1", "technique 2"]
}
```

Validation is advisory only and never blocks an iteration. Warnings are recorded when:
- A task ID in clusters[].tasks is not in the val split
- An edit references a cluster ID that does not exist
- An edit references a file that does not exist in the candidate
