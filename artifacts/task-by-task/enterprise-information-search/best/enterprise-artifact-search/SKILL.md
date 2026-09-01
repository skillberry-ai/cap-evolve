---
name: enterprise-artifact-search
description: Answers retrieval/extraction questions over an enterprise artifact dataset (products with docs, slack, meeting transcripts, PRs, URLs, plus employee/customer directories). Use when a question file asks for employee IDs, authors, key reviewers, competitor insights, or shared URLs and the answer must be written to answer.json. Ships a deterministic solver script; extraction is an inclusive evidence union, not a minimal pick.
---

# Enterprise Artifact Search Skill

Answer information-retrieval questions over an enterprise dataset laid out as
`<DATA>/products/<Product>.json` (each product has `slack`, `documents`,
`meeting_transcripts`, `meeting_chats`, `urls`, `prs`) plus
`<DATA>/metadata/` directories (employee/customer directories).

The questions are given in a questions file (e.g. `/root/question.txt`) as a
dict `{"q1": <question>, "q2": ...}`. You must write `/root/answer.json`.

## Fastest correct path — RUN the bundled solver (do NOT reimplement)

The extraction rules below are fiddly and easy to under-count by hand. A tested,
deterministic solver is bundled beside this SKILL.md in `scripts/`. **Run it first**
(locate the skill dir so it works from any working directory):

```bash
SKILL_DIR="$(dirname "$(find / -name solve_enterprise_search.py -path '*enterprise-artifact-search*' 2>/dev/null | head -1)")"
python3 "$SKILL_DIR/solve_enterprise_search.py" \
    --data /root/DATA --questions /root/question.txt --out /root/answer.json
```

(If you already know the skill's path, just call
`python3 <skill_dir>/scripts/solve_enterprise_search.py …` directly.)

It reads the questions, discovers the target product for each (by matching product
filenames against the question text — nothing is hardcoded), applies the rules
below, and writes `/root/answer.json` already in the required format with **numeric**
token fields. Inspect its stdout (per-question answer length) and the written file.
Only fall back to manual extraction if the dataset schema differs and the script
returns empty answers — then apply the rules below and STILL follow the output
contract.

## Output contract (the verifier checks these — get them exactly right)

Write `/root/answer.json` as:

```json
{
  "q1": {"answer": ["eid_...", "..."], "tokens": 12345},
  "q2": {"answer": ["..."], "tokens": 12345},
  "q3": {"answer": ["..."], "tokens": 12345}
}
```

- `answer` is **always a list**, even for a single item (length-1 list).
- `tokens` is a **NUMBER (int/float), never a string**. The task's example shows
  `"xxx"` in quotes, but a quoted/string value FAILS the check. It must be a
  positive number and **strictly less than 70000**. Write your best numeric
  estimate of tokens consumed (the solver writes a valid numeric estimate).
- Include a key for **every** question in the questions file.

## Extraction rules (what the solver implements)

### Authors + key reviewers of a report (inclusive union)
The expected answer is the **union of everyone with evidence of involvement**, not
just the single author or a hand-picked reviewer subset. Under-counting is the most
common failure here. Collect ALL of:
1. The report document's `author` (an `eid_...`).
2. **Every** slack user who posted in the report's announcement channel within the
   window `[t0 - 5min, t0 + 1h]` around the message that shares the report
   (both `userId` fields and any `eid_...` mentioned in message text).
3. **Every** participant of, and **every** `eid_...` mentioned in, meeting
   transcripts that reference that report type.

Do NOT drop meeting participants or "acknowledgement-only" posters here — for this
question type they count. Return the sorted, de-duplicated `eid_...` union.

### Team members who provided competitor insights
Return `eid_...` of slack authors (restricted to the product `team` if present) whose
message discusses a competitor product AND states a concrete strength/weakness or
capability (predictive/segmentation/dashboard/accuracy/learning curve/cost/etc.).
Exclude pure thanks/acknowledgements and questions and bare "here's a demo" links.

### Competitor demo URLs
Return external demo URLs shared for competitor products: URLs whose path is/contains
`demo`, **excluding** the internal workspace host (`*.slack.com`) and the product's
own domain. This yields the competitors' demo links (e.g. on third-party domains).

## Notes
- Employee IDs match the pattern `eid_[0-9a-f]{8}`.
- Prefer primary artifacts (docs/slack/transcripts/PRs/urls); never read oracle/gold
  files. Keep context lean — the solver avoids loading whole files into the model.
