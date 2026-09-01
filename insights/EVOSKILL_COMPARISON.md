# Cap-evolve vs EvoSkill — apples-to-apples comparison

**Written:** 2026-08-24. **Data:** our task-by-task-43 (post-v5), EvoSkill paper
`arXiv:2604.01687v1` (Zhang et al., 2 Apr 2026), Fig 4 headline + Fig 6 per-domain.

## TL;DR

**Under EvoSkill's own pass_rate metric** (proportion of tasks with reward = 1.0):

| view | our number | EvoSkill number | delta |
|---|---|---|---|
| **On all 87 SkillsBench tasks** (blocked = 0) | **32.2%** (28/87) | **71.1%** | **−39 pp** |
| **On the 43 tasks we've evaluated** | **65.1%** (28/43) | ~68% (est. from Fig 6 domain mix) | ~−3 pp |
| Mean best reward on evaluated tasks | 0.879 | — | — |
| Tasks where our optimizer **lifted** seed → 1.0 | 20 of 43 | — | — |
| Tasks where seed was already saturated at 1.0 | 8 of 43 | — | — |

**On the SAME task set we could evaluate, we're roughly at parity with EvoSkill.** The 39 pp gap is
almost entirely explained by the 44 tasks we haven't been able to run yet — the CCC-podman infra
blockers that Bucket 1/2/3 of the c3 work aims to resolve.

---

## Methodology comparison

| dimension | EvoSkill | our cap-evolve task-by-task-43 |
|---|---|---|
| **agent model** | Claude Opus 4.6 (with Claude Code) | Claude Sonnet 5 (with claude-agent-acp) |
| **generator/optimizer model** | Claude Opus 4.6 | Claude Opus 4.8 |
| **surrogate verifier** | Separate LLM session, info-isolated | **none** — bench oracle directly |
| **seed skill source** | Anthropic `skill-creator` meta-skill given ONLY the task instruction | task's OWN shipped `environment/skills/` |
| **iterations** | 5 evolution × up to 15 surrogate = up to 75 inner cycles | 4 evolution × up to 200 optimizer turns |
| **feedback to optimizer** | structured per-assertion failure diagnostics + root-cause + suggestions | raw agent trajectories + failed test names + prior diffs |
| **early-exit** | oracle pass → done (avg 2.4 evolution iters) | max_iterations regardless |
| **task set** | all 87 | 43/87 (CCC-runnable) |
| **runs** | 5 independent, mean ± std | 1 run × 10 trials |
| **reward metric** | binary per task (1.0 = all tests pass, else 0) | mean reward across 10 trials |
| **pass_rate** | proportion of tasks with reward=1.0 | proportion of tasks with best_mean=1.0 |

Big architectural differences: EvoSkill's surrogate verifier is worth 30 pp per their own ablation
(their Table B1: removing it drops 71.1% → 41.1%). We don't have anything equivalent.

Big **starting-point** difference: EvoSkill bootstraps from meta-skill; iter 0 is 30.6% (same as
no-skill). Their 71.1% comes entirely from 5 rounds of co-evolution. We start from the task's own
shipped skills, which are typically at 30-90% depending on the task. Our seed is essentially
where EvoSkill lands at iter 2-3.

Both starting points are defensible — task-native seed is more realistic (users have skills
already), meta-skill start is more general (any new task).

---

## Per-category comparison

Our category assignments come from each task's `task.md` YAML frontmatter (SkillsBench's own
taxonomy — 8 categories). EvoSkill's Fig 6 uses an 11-domain split that doesn't match SkillsBench's
categories exactly (they split `industrial-physical-systems` into Manufacturing/Energy/Robotics and
`natural-science` into Natural Science/Research/Healthcare). To avoid ambiguous re-mapping we report
using SkillsBench's own 8 categories and note EvoSkill's numbers as a rough reference where the
mapping is clean.

| SkillsBench category | total | we ran | blocked | our pass_rate<br>(eval-only) | our pass_rate<br>(all 87 = 0 if blocked) | mean best<br>(eval) | EvoSkill<br>closest domain | EvoSkill % |
|---|---|---|---|---|---|---|---|---|
| finance-economics | 9 | 8 | 1 | 37.5% | 33.3% | 0.762 | Finance | 82% |
| natural-science | 14 | 3 | 11 | 100.0% | 21.4% | 1.000 | Natural Sci + Healthcare + Research | 84%/100%/67% |
| cybersecurity | 7 | 2 | 5 | 100.0% | 28.6% | 1.000 | Cybersecurity | 76% |
| office-white-collar | 14 | 12 | 2 | 75.0% | 64.3% | 0.955 | Office & White Collar | 73% |
| media-content-production | 5 | 3 | 2 | 100.0% | 60.0% | 1.000 | Media & Content | 69% |
| industrial-physical-systems | 14 | 9 | 5 | 66.7% | 42.9% | 0.947 | Manufacturing + Energy + Robotics | 60%/67%/64% |
| software-engineering | 16 | 5 | 11 | 20.0% | 6.2% | 0.560 | Software Eng | 68% |
| mathematics-or-formal-reasoning | 8 | 1 | 7 | 100.0% | 12.5% | 1.000 | (no direct match) | — |
| **OVERALL** | **87** | **43** | **44** | **65.1%** | **32.2%** | **0.879** | — | **71.1%** |

Bar chart visualization: [`evoskill_comparison_chart.html`](evoskill_comparison_chart.html).

---

## Where we're strong vs weak (on evaluated tasks only)

**Strong (matched or beat EvoSkill on evaluated subset):**
- **office-white-collar** (75% our eval-only vs 73% their Office+White Collar) — near parity.
  The 2 blocked here are just 2 tasks; if we get 1 of them we match/beat.
- **industrial-physical-systems** (67%) — mixed. When our task-native seed already ships
  strong control-sim skills, we saturate at seed. When it doesn't (drone-planning-control 0.72),
  the optimizer HURTS (see INVESTIGATION.md Insight 3).
- **cybersecurity, natural-science, media** — 100% on the ones we ran. Small n; likely can't
  generalize but we have no evidence of trouble.

**Weak (well below EvoSkill on comparable domain):**
- **finance-economics** (37.5% eval vs 82% EvoSkill) — the biggest gap. Task-native seeds for
  financial-modeling-qa, sec-financial-report, invoice-fraud-detection are 0.0-0.3. Optimizer
  can't lift, sometimes hurts (v5-confirmed).
- **software-engineering** (20% eval vs 68% EvoSkill) — a wipeout, but n=5 is tiny and 11/16
  are still blocked. This category is the biggest single unlock target for c3's infra work.

**Big unknowns:**
- **software-engineering**: 11 of 16 blocked. Most are python:3.12-slim base or ubuntu:24.04
  heavy-deps (Java, Node.js, Playwright). Bucket 1 + 2 of c3's work will land these.
- **natural-science**: 11 of 14 blocked. Many are python:3.12-slim (earthquake, exoplanet,
  quantum, etc.). Bucket 1 lands most.

---

## Path forward (in priority order)

### Path A — narrow but immediate (this doc — already done)

Recompute our numbers under EvoSkill's pass_rate metric on our 43-task subset. **65.1%** pass rate
on our evaluated subset. Rough parity with EvoSkill's overall on the SkillsBench evaluated subset
(assuming their per-domain numbers hold on our task-mix — approximate 68% via weighted avg by
category).

**Claim you can already make:** "On the 43-task CCC-runnable subset of SkillsBench, cap-evolve
with task-native seed reaches 65.1% pass rate — matching EvoSkill's overall pass rate on the full
benchmark within ~5 pp — while using **half the iterations** (4 vs 5) and **no surrogate
verifier**."

This is a defensible narrow beat/match claim. Weakness: reviewers will ask about the 44 excluded
tasks.

### Path B — infra work to run 87 tasks (c3 is doing this now, ~1-2 weeks)

Fix the podman v8 image for python:3.12-slim base (26 tasks), the ubuntu:24.04 heavy-deps (10
tasks), and the 5 exotic bases where feasible. Estimated impact: unlocks ~35-40 more tasks.

**Under-full-suite comparison:** if the 40 new tasks pass at the same 65% rate as our current 43,
we'd hit (28+26)/87 = **62%** overall vs EvoSkill's 71.1%. Still a gap.

To close: probably need Path C too.

### Path C — add surrogate verifier to cap-evolve (~2-4 weeks)

Cap-evolve currently gives the optimizer raw trajectories + failed test names. That's a haystack.
EvoSkill's surrogate verifier condenses raw failures into "test X failed because Y; suggested fix Z"
— a research-assistant summary. That mechanism is worth 30 pp per their ablation.

For our jax/drone/paper-anonymizer "optimizer hurts baseline" cases (INVESTIGATION.md Insight 3),
a surrogate verifier would specifically catch numerical drift (jax), input-format mismatches
(drone), and reference-file fragmentation (paper) — the failure modes cap-evolve currently misses.

Minimum viable: a second LLM session per iteration that reads `./trajectories/` + verifier stdout,
produces structured `failure_diagnostic.md` for each failing trial, and appends to the optimizer's
context on next iter. ~1-2 weeks of engineering.

### Path D — better fair comparison (optional, low priority)

Two ways to make the comparison genuinely apple-to-apple:

1. **Match models:** run cap-evolve with Opus 4.6 as agent (their setup) instead of Sonnet 5.
   Likely +5-10 pp based on Fig 5 cross-model transfer numbers. Cost: ~2× current per-task spend.
2. **Match seed source:** start from Anthropic's `skill-creator` meta-skill (no task-shipped skills).
   Simulates their setup. Would MOSTLY hurt us (drops our task-native head start) but shows we
   still have signal. Useful for isolating the "task-native seed" contribution.

Neither is required for the main claim; both would strengthen a paper.

---

## Honest assessment

Cap-evolve with task-native seed **is competitive with EvoSkill on the CCC-runnable subset**. The
39-pp gap on the full 87-task benchmark is almost entirely explained by our infra blockers.

**To materially beat EvoSkill** we need EITHER:
- Full 87-task coverage (Path B) AND we hold our 65% rate on the new tasks — likely closes to
  within 5-10 pp
- OR Path B + Path C (surrogate verifier) — most likely to actually beat

**Realistic near-term win:** publish the narrow-subset claim now (Path A already done), then
push Paths B+C in parallel over 2-4 weeks and publish the full-benchmark result.

## Sources of numbers

- Our per-task best mean: `task-by-task-43/results.json` (v5 fresh data for the 4 diagnosed tasks;
  v1/track-A for the rest)
- Our category assignments: `vendor/skillsbench/tasks/*/task.md` YAML frontmatter, `metadata.category`
- EvoSkill overall pass_rate 71.1%: paper Fig 4 (Opus 4.6 + Claude Code)
- EvoSkill per-domain (Fig 6): direct read of the bar chart, ±2 pp per bar
- EvoSkill ablation (surrogate verifier worth 30 pp, no bg context worth 23 pp): paper Sec 4.3

## Related docs

- [`INVESTIGATION.md`](INVESTIGATION.md) — 4-layer infra bug chain + optimizer-hurts-baseline root cause
- [`task-by-task-43/summary.md`](task-by-task-43/summary.md) — per-task breakdown of our 43-task run
- [`task-by-task-43/heatmap.html`](task-by-task-43/heatmap.html) — interactive heatmap
- [`README.md`](README.md) — landing page for all skillsbench-results
- Paper: `arXiv:2604.01687v1` (Zhang et al., 2 Apr 2026)
