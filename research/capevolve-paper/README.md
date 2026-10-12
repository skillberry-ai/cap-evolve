# CapEvolve paper repository

Working repository for the MLSys 2027 submission **"CapEvolve: Optimizing Any Editable Surface of a Frozen Agent Under Code-Owned Evaluation"**.
It mirrors the research subtree of the campaign branch `research/capevolve-paper-20261011` (last sync is whatever the latest commit shows).

**Paper PDF: [`paper/paper.pdf`](paper/paper.pdf)** (44 pages including appendices, rebuilt from [`paper/paper.tex`](paper/paper.tex)).
Current state: draft in mock mode. Navigation: [`PROGRESS.md`](PROGRESS.md) (dated log), [`RESULTS.md`](RESULTS.md) (index of every real result), [`STATUS.md`](STATUS.md) (plain-language status), [`decisions.md`](decisions.md) (decision log).

## What CapEvolve and the paper are

CapEvolve is an optimizer for agents that run on a frozen model. The files around the model set its behavior: the system prompt, tool code, the tool list exposed over MCP, and skill packages.
CapEvolve makes the editable surface a parameter of one loop. Every decision an optimizer could game stays in core code the optimizer cannot edit: gold isolation, the promotion gate (the stock gate, or rule P, a screen plus fresh-trial confirmation), and a final set that is sealed and scored once. The optimizer also receives a fixed/broke history of its earlier edits.
The loop runs either as a deterministic hill-climb or as a coding agent (agent-optimize) driving the same gate. Four surfaces are implemented; the paper evaluates two (prompt and tool code).

The paper compares CapEvolve against adapted versions of nine published optimizers at a matched rollout checkpoint, on five suites, and ablates the surface, the gate, the orchestration mode and the history. It also reports an audit of an earlier version of the optimizer (scorer compliance explains much of its reported gain) and a protocol with ten dated amendments, each written before the held-out data it governs.
The paper makes no "best optimizer" claim in advance. Differences smaller than the design can resolve (about 11 to 15 points between frozen artifacts) are reported as inconclusive.

## What is real and what is placeholder right now

The search cutoff is **2026-10-13 06:00 UTC**. Until then no held-out (final-set) score exists for any suite.

| Item | Status |
|---|---|
| Method, protocol, setup, related work, limitations text | Real prose; still being revised by review rounds |
| Search-time tables and figures (own selection split, not held-out) | Real, from run artifacts; searches are still running, so numbers move. See [`RESULTS.md`](RESULTS.md) |
| E22 null-pool result (false accepts of the gates on 40 seed re-evaluations) | Real, complete |
| Metering and cost totals | Real, refreshed from the gateway log |
| Gate replay on historical artifacts, rule P simulations, audits | Real, complete |
| Held-out results: main comparison tables, forest and contrast plots, ablation plots, Pareto and anytime plots, Suite D and E tables, abstract result sentence | **Placeholder.** Generated from seeded mock numbers (`\pend` macros, PLACEHOLDER watermark). They are not findings |
| N* (matched checkpoint) per suite | Placeholder until the cutoff; computed from rollout counters only |

Figures and tables that carry a PLACEHOLDER watermark or a `mock` macro name must not be read as results.

## The five suites

| Suite | Benchmark | Target model | Splits (opt / sel / final) | Arms | Status (2026-10-12 13:20 UTC) |
|---|---|---|---|---|---|
| A | SpreadsheetBench (912 release, verified-400 subset for search) | Gemma-4-31B-it | gate and selection on val-40; final: 70 ids sampled at the cutoff from a 239-id residual pool, 1 trial each | CapEvolve hill-climb (rule P), agent-optimize (rule P), hill-climb stock gate (E12A); GEPA, SkillOpt, Meta-Harness, EvoSkill, WikiSkill (community port), Trace2Skill, ACE, MIPROv2; seed and one-shot controls | Searching; Meta-Harness, Trace2Skill and some seeds of other arms finished |
| B | tau2-bench retail | gpt-oss-120b (also user simulator); GPT-5.5 judge | opt-49 / sel-25 / sealed test-40, 3 trials | CapEvolve hill-climb and agent-optimize (rule P), stock gate (E12B, paused), GEPA, HarnessLens; seed, one-shot | Searching; HarnessLens restarted after the bubblewrap fix |
| C | tau2-bench airline | gpt-oss-120b | opt-20 / sel-10 / test-20, 3 trials (test-20 is development-exposed) | CapEvolve hill-climb and agent-optimize (rule P), stock gate (E12C), GEPA, best-of-k control (truncated); seed, one-shot | Searching; agent-optimize finished natively |
| D | tau2-bench retail, ablation family | Azure gpt-4.1-mini; gpt-4.1 simulator and judge | opt-49 (search) / sel-25 / sealed test-40, 5 trials per champion, 10 for the seed | Cells: prompt+tools (reference), prompt only, tools only, one-shot, rule P, one-stage gate, no-history (E26), GEPA prompt-only | 21 searches running; E22 null pool done; E26-nohist launched 11:46 |
| E | tau2-bench airline, replication of D | Azure gpt-4.1-mini; gpt-4.1 simulator and judge | opt-20 / sel-10 (from official train-30) / official test-20, 5 trials | Same cells as D, plus ACE, MIPROv2, full-surface GEPA, agent-optimize, one exploratory HarnessLens seed | Registered (amendment 10); waves start as Azure capacity frees up |

Suites A to C use a matched checkpoint N*. Suites D and E use fixed budgets. Suite E only corroborates D, with no pooling and no cross-suite headline. Suites are never pooled.

## Directory map

| Path | Contents |
|---|---|
| `paper/` | LaTeX manuscript: `paper.tex`, `sections/`, `appendix/`, `tables/`, `figures/`, scripts that generate tables and figures, `paper.pdf` |
| `protocol/` | Frozen measurement protocol: `analysis_plan.md` (with amendments 1 to 10), benchmarks, splits, model registry, pricing, scorer audit |
| `analysis/` | `scripts/` that produce every number; `out/` holds the generated tables, CSVs, JSON and PNG figures. Index in [`RESULTS.md`](RESULTS.md) |
| `audit/` | Repository and algorithm audit, historical-result audit, gold-access scan, metering and silent-failure audits, capped-token forecast |
| `experiments/` | Configs, run manifests, `registry.jsonl` (every experiment script and hash), `run_queue.jsonl`, final-evaluation tooling |
| `redesign/` | Story (`STORY.md`), outline, and the experiment plan (`EXPERIMENTS.md`) |
| `design/` | Experimental design pages for the five suites |
| `designs/` | Proposed designs for other benchmarks (AppWorld, SWE-bench Verified) |
| `reviews/` | Independent review reports, triage and responses per paper draft |
| `literature/` | Paper cards, evidence table, novelty matrix, bibliography (PDF hashes only) |
| `handoff/` | `checkpoint.md`, the resumable campaign state |
| `claims.csv` | Claim ledger: each paper claim, its evidence, script and status |
| `campaign.yaml` | Budget envelope and concurrency (no secrets) |
| `decisions.md` | Dated decision log with rationale |
| `STATUS.md` | Plain-language status, updated at periodic checks |

Raw run directories, gateway logs and credentials are not in this repository.

## Designs for other benchmarks

Written designs for extending the study to further benchmarks. These are proposals only: nothing in them has run, and none is part of Suites A to E or of the paper's registered protocol.

| Design | Status |
|---|---|
| [`designs/appworld_experimental_design.md`](designs/appworld_experimental_design.md) (issue text: [`designs/appworld_issue.md`](designs/appworld_issue.md)) | AppWorld, targets DeepSeek-V3.2 and gpt-oss-120b, against ACE, ALTK-Evolve and the campaign competitors. Posted as issue skillberry-ai/cap-evolve#804 |
| [`designs/swebench_verified_experimental_design.md`](designs/swebench_verified_experimental_design.md) | SWE-bench Verified. In progress |

## Build the paper

```
cd paper
make paper                    # pdflatex + bibtex, writes paper.pdf
make check                    # build, then scripts/check_paper.py (page budget, mock leaks, references)
make all MODE=mock            # regenerate numbers, tables and figures from mock values, then build
make all MODE=real PYTHON=... # same from real artifacts (after the cutoff, once final scores exist)
```

Requires a TeX Live install with the MLSys 2025 style files (included as `mlsys2025.sty` and `.bst`), `python3` with matplotlib, and `pdftotext` for the checks.
Regenerating analysis outputs needs the campaign scratch store, which is not part of this repository.
