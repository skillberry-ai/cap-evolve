# Train/test split by shared skill — proposal (not yet executed)

Goal: for subcategory groups that plausibly share a domain skill, evolve the skill on
train task(s) with full ground-truth reward access (legitimate — that's what cap-evolve
is for), freeze it, and apply it zero-shot to the held-out test task(s) in the same group.
Report the test task's reward under the frozen transferred skill vs. its own seed baseline.

## Selection filter applied

A group is only useful for this experiment if at least one member shows `best > seed`
by a real margin — i.e. cap-evolve's optimizer actually added something beyond the
generic seed_capability. Groups where every member was already saturated at seed=1.0
(no optimization happened at all) test nothing about cap-evolve's contribution — they'd
just test whether the generic seed skill transfers, which is a different (still valid,
but different) question. Two groups have **zero usable signal on either side**
(all members NO_SIGNAL) and are excluded outright.

Legend: **train** = has real optimizer lift (best > seed + 0.1). **test†** = seed
already saturated (1.0) — transfer has no room to show a lift, low information as a
test target. **test‡** = NO_SIGNAL (seed=0 and best=0) — good test target precisely
*because* it's currently unsolved; a transferred skill lifting it off zero would be a
strong positive result.

## Excluded — no signal anywhere

| group | tasks | why excluded |
|---|---|---|
| natural-science / seismology | earthquake-phase-association, seismic-phase-picking | both NO_SIGNAL — no train candidate exists |
| software-engineering / build-repair | fix-build-agentops, fix-build-google-auto | both NO_SIGNAL — no train candidate exists |

## Recommended priority order for piloting

1. **finance-economics / macroeconomic-analysis** — all 3 members have real lift, full 3-way leave-one-out is informative in every fold.
2. **mathematics-or-formal-reasoning / mathematical-optimization** — both members have real lift, both non-saturated seeds.
3. **cybersecurity / vulnerability-analysis** — 2 lift tasks + 1 NO_SIGNAL test‡ target (interesting: can transfer rescue a currently-unsolved task?).
4. **cybersecurity / fuzzing** — 2 lift tasks, modest margins, decent 2-fold swap.
5. Everything else below — usable but mostly one lift-task facing an already-saturated test†, so the test side carries little information (transfer literally can't score higher than the ceiling it's already at).

## Full fold plan

### finance-economics / macroeconomic-analysis (3-way LOO) — priority 1
- train {shock-analysis-supply, weighted-gdp-calc} → test shock-analysis-demand (train)
- train {shock-analysis-demand, weighted-gdp-calc} → test shock-analysis-supply (train)
- train {shock-analysis-demand, shock-analysis-supply} → test weighted-gdp-calc (train)

### mathematics-or-formal-reasoning / mathematical-optimization (2-way swap) — priority 2
- train exam-block-sequencing → test paratransit-routing (train)
- train paratransit-routing → test exam-block-sequencing (train)

### cybersecurity / vulnerability-analysis (3-way LOO) — priority 3
- train {fix-erlang-ssh-cve, software-dependency-audit} → test fix-druid-loophole-cve (test‡)
- train {fix-druid-loophole-cve(no signal, skip as train), software-dependency-audit} → **not valid**, fix-druid-loophole-cve can't be a train source
- Effectively only 1 usable fold: train {fix-erlang-ssh-cve, software-dependency-audit} → test fix-druid-loophole-cve. (Could also do fix-erlang↔software-dependency-audit swap as a secondary fold, both are real train candidates.)
- train fix-erlang-ssh-cve → test software-dependency-audit (train)
- train software-dependency-audit → test fix-erlang-ssh-cve (train)

### cybersecurity / fuzzing (2-way swap) — priority 4
- train setup-fuzzing-py → test syzkaller-ppdev-syzlang (train)
- train syzkaller-ppdev-syzlang → test setup-fuzzing-py (train)

### natural-science / hydrology (1 usable train, 2 saturated test†)
- train lake-warming-attribution → test flood-risk-analysis (test†), test glm-lake-mendota (test†)

### office-white-collar / spreadsheet-workflow (2 usable train, 1 saturated test†)
- train sales-pivot-analysis → test pdf-excel-diff (train, small lift), test powerlifting-coef-calc (test†)
- train pdf-excel-diff → test sales-pivot-analysis (train)

### media-content-production / video-processing (2 usable train, 1 saturated test†)
- train video-silence-remover → test multilingual-video-dubbing (train), test mario-coin-counting (test†)
- train multilingual-video-dubbing → test video-silence-remover (train)

### software-engineering / performance-optimization (1 usable train, 2 saturated test†, 1 NO_SIGNAL test‡)
- train react-performance-debugging → test fix-visual-stability (test‡), test llm-prefix-cache-replay (test†), test parallel-tfidf-search (test†)

### finance-economics / financial-modeling (1 usable train, 1 NO_SIGNAL test‡) — directional only
- train xlsx-recover-data → test financial-modeling-qa (test‡)

### office-white-collar / presentation-editing (1 usable train, 1 saturated test†)
- train exceltable-in-ppt → test pptx-reference-formatting (test†)

### industrial-physical-systems / control-systems (1 usable train, 1 saturated test†)
- train r2r-mpc-control → test hvac-control (test†)

### mathematics-or-formal-reasoning / formal-planning (1 usable train, 1 saturated test†)
- train pddl-airport-planning → test pddl-tpp-planning (test†)

### media-content-production / 3d-content (1 usable train, 1 saturated test†)
- train threejs-structure-parser → test threejs-to-obj (test†)

### natural-science / astronomy — not recommended
All 3 saturated at seed=1.0. No optimizer lift anywhere in the group; would only test
generic seed-skill transfer, not cap-evolve's contribution. Skip unless the generic-skill
question becomes interesting on its own.

### office-white-collar / document-editing — not recommended
offer-letter-generator saturated; paper-anonymizer shows no net lift (best == seed).
No train candidate with real signal.

## Not yet executed

Per instruction, this is the design only — no runs have been started. Suggested first
pilot: macroeconomic-analysis (priority 1) plus mathematical-optimization (priority 2),
6 fold-runs total, before deciding whether to scale to the full list.

## Flat train/test table — one row per category

Derived mechanically from `results.json`: group by (category, subcategory); drop any
task with `seed == 1.0` (already saturated, no room to show a transfer effect — listed
separately below); a group needs ≥2 remaining tasks to produce a split at all (fewer
than that has no partner and is listed as unassigned below). For groups with more than
2 remaining tasks, train gets ~60–75% (tasks with the larger `best - seed` lift go to
train; the rest to test). For exactly 2 remaining tasks it's a straight 1 train / 1 test.

| category / subcategory | train tasks | test tasks |
|---|---|---|
| cybersecurity / fuzzing | syzkaller-ppdev-syzlang | setup-fuzzing-py |
| cybersecurity / vulnerability-analysis | software-dependency-audit, fix-erlang-ssh-cve | fix-druid-loophole-cve |
| finance-economics / financial-modeling | xlsx-recover-data | financial-modeling-qa |
| finance-economics / macroeconomic-analysis | shock-analysis-demand, shock-analysis-supply | weighted-gdp-calc |
| mathematics-or-formal-reasoning / mathematical-optimization | paratransit-routing | exam-block-sequencing |
| media-content-production / video-processing | video-silence-remover | multilingual-video-dubbing |
| natural-science / seismology* | earthquake-phase-association | seismic-phase-picking |
| office-white-collar / spreadsheet-workflow | sales-pivot-analysis | pdf-excel-diff |
| software-engineering / build-repair* | fix-build-agentops | fix-build-google-auto |
| software-engineering / performance-optimization | react-performance-debugging | fix-visual-stability |

\* Neither task in this group ever showed real lift (both `best == seed == 0.0`,
NO_SIGNAL). The train/test assignment here is arbitrary — there's no evidence either
task's skill is worth transferring. Kept in the table for completeness rather than
silently dropped; treat as low-confidence.

### Excluded — baseline already 1.0 (21 tasks)

No room to show a transfer lift (already at the reward ceiling with just the seed
skill). Not assigned to train or test in any category.

dapt-intrusion-detection, econ-detrending-correlation, 3d-scan-calc, hvac-control,
pddl-tpp-planning, threejs-to-obj, mario-coin-counting, exoplanet-detection-period,
gravitational-wave-detection, mars-clouds-clustering, radar-vital-signs,
flood-risk-analysis, glm-lake-mendota, protein-expression-analysis, citation-check,
offer-letter-generator, pptx-reference-formatting, powerlifting-coef-calc,
dialogue-parser, llm-prefix-cache-replay, parallel-tfidf-search

### Not assigned to any category (44 tasks)

Each is the only non-saturated task left in its subcategory after the baseline=1.0
filter above — no partner to pair with for a train/test split.

suricata-custom-exfil, invoice-fraud-detection, reserves-at-risk-calc,
sec-financial-report, energy-ac-optimal-power-flow, ada-bathroom-plan-repair,
r2r-mpc-control, manufacturing-codebook-normalization, dynamic-object-aware-egomotion,
energy-market-pricing, grid-dispatch-operator, manufacturing-equipment-maintenance,
manufacturing-fjsp-optimization, drone-planning-control, energy-unit-commitment,
adaptive-cruise-control, travel-planning, civ6-adjacency-optimizer,
pddl-airport-planning, lean4-proof, bike-rebalance, threejs-structure-parser,
crystallographic-wyckoff-position-analysis, earthquake-plate-calculation,
lake-warming-attribution, lab-unit-harmonization, quantum-numerical-simulation,
enterprise-information-search, organize-messy-files, paper-anonymizer,
court-form-filling, jpg-ocr-stat, edit-pdf, latex-formula-extraction,
exceltable-in-ppt, python-scala-translation, tictoc-unnecessary-abort-detection,
data-to-d3, debug-trl-grpo, flink-query, jax-computing-basics,
spring-boot-jakarta-migration, azure-bgp-oscillation-route-leak,
simpo-code-reproduction
