# seed_capability — extracted at setup time, not vendored here

This example optimizes the four **shared office-document Agent Skills** SkillsBench ships
with its tasks — `docx`, `pptx`, `xlsx`, `pdf`. Those skill packages are **Anthropic-licensed**
(© Anthropic, PBC — "Use of these materials is governed by your agreement with Anthropic"),
so they are **not vendored into this repository**.

Instead, [`setup.sh`](../setup.sh) **extracts** them from your own clone of SkillsBench at
onboarding time, taking the most complete variant of each:

| skill | extracted from (in the SkillsBench clone) |
|---|---|
| `docx` | `tasks/offer-letter-generator/environment/skills/docx` |
| `pptx` | `tasks/exceltable-in-ppt/environment/skills/pptx` |
| `xlsx` | `tasks/exceltable-in-ppt/environment/skills/xlsx` |
| `pdf`  | `tasks/pdf-excel-diff/environment/skills/pdf` |

So after `bash examples/skillsbench/setup.sh`, the live, editable seed lives at
`.capevolve/project/seed_capability/{docx,pptx,xlsx,pdf}/` (gitignored) — that copy is what
the optimizer edits and what gets deployed to every task.

**Credit:** the skills are from Anthropic's Agent Skills, redistributed within
[SkillsBench](https://github.com/benchflow-ai/skillsbench); their license governs their use.
This repo only ships the *optimization harness* (adapter, spec, optimizer instructions) and,
in [`DEMO.md`](../DEMO.md), short **diffs of the optimizer's own additions** to those skills —
not the skills themselves.
