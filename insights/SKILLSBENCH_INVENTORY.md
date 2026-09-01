# SkillsBench task/skill inventory (87 tasks)

Extracted from `benchflow-ai/skillsbench@9a1f4dd` — each task's `task.md` frontmatter and `environment/skills/` directory.

## Category breakdown

| Category | Tasks | Notes |
|---|---:|---|
| software-engineering | 16 | CVE fixes, build system upgrades, dependency audits, migration tasks. Each is essentially a code-modification task with a project-specific verifier. |
| industrial-physical-systems | 14 | Power-flow / grid dispatch, HVAC, aerospace flight planning, manufacturing scheduling. Heavy math + specialized libraries. |
| office-white-collar | 14 | Documents (docx/pptx/xlsx/pdf), spreadsheets, forms. **This is the domain our current 4-skill seed package targets.** |
| natural-science | 14 | Astrophysics, seismology, biology/protein, hydrology, chemistry. Domain-specific data formats + numerical methods. |
| finance-economics | 9 | Financial reports, tax forms, economic modelling. Some overlap with office-doc tasks; some heavy math. |
| mathematics-or-formal-reasoning | 8 | Lean4 proofs, planning (PDDL), MIP/optimization solvers, statistical analysis. Very-domain-specific tooling. |
| cybersecurity | 7 | PCAP analysis, Suricata rules, fuzzing setups, CVE triage. Each is task-specific-tool-heavy. |
| media-content-production | 5 | Video/audio processing, OCR, image editing, TTS. Media codec + ML libraries. |

## Coverage of our current seed skills (docx/pptx/xlsx/pdf)

**21 tasks ship one or more of our 4 seed skills** in their own `environment/skills/`. When BenchFlow mounts `--skill-mode with-skill --skills-dir <ours>`, it *replaces* the task's own set with ours. So on these tasks the optimization can plausibly matter; on the other 87−21 tasks the office-skill package is out-of-domain.

| task | office skills the task itself ships | full shipped set |
|---|---|---|
| `court-form-filling` | `pdf` | `pdf` |
| `exceltable-in-ppt` | `pptx` · `xlsx` | `pptx` · `xlsx` |
| `financial-modeling-qa` | `pdf` · `xlsx` | `pdf` · `xlsx` |
| `flink-query` | `pdf` | `pdf` · `senior-data-engineer` |
| `invoice-fraud-detection` | `pdf` · `xlsx` | `fuzzy-match` · `pdf` · `xlsx` |
| `jpg-ocr-stat` | `pdf` · `xlsx` | `image-ocr` · `openai-vision` · `pdf` · `video-frame-extraction` · `xlsx` |
| `latex-formula-extraction` | `pdf` | `marker` · `pdf` |
| `offer-letter-generator` | `docx` | `docx` |
| `organize-messy-files` | `docx` · `pdf` · `pptx` | `docx` · `file-organizer` · `pdf` · `planning-with-files` · `pptx` |
| `paper-anonymizer` | `pdf` | `academic-pdf-redaction` · `pdf` |
| `pdf-excel-diff` | `pdf` · `xlsx` | `pdf` · `xlsx` |
| `powerlifting-coef-calc` | `xlsx` | `powerlifting` · `senior-data-scientist` · `xlsx` |
| `pptx-reference-formatting` | `pptx` | `pptx` |
| `protein-expression-analysis` | `xlsx` | `xlsx` |
| `reserves-at-risk-calc` | `xlsx` | `xlsx` |
| `sales-pivot-analysis` | `pdf` · `xlsx` | `pdf` · `xlsx` |
| `shock-analysis-demand` | `xlsx` | `xlsx` |
| `shock-analysis-supply` | `xlsx` | `xlsx` |
| `simpo-code-reproduction` | `pdf` | `nlp-research-repo-package-installment` · `pdf` |
| `weighted-gdp-calc` | `xlsx` | `xlsx` |
| `xlsx-recover-data` | `xlsx` | `data-reconciliation` · `xlsx` |

## All 87 tasks, grouped by category

For each task: **difficulty** — task_type — the skills the task's environment ships (which BenchFlow strips + replaces with the seed when running under `--skill-mode with-skill`).

### software-engineering (16 tasks)

| Task | Difficulty | Task type | Shipped skills |
|---|---|---|---|
| `azure-bgp-oscillation-route-leak` | medium | detection, analysis | `azure-bgp` |
| `data-to-d3` | medium | implementation, generation | `d3-visualization` |
| `debug-trl-grpo` | hard | debugging, repair | `grpo`, `rl-post-training`, `trl` |
| `dialogue-parser` | easy | implementation, transformation | `dialogue-graph` |
| `fix-build-agentops` | easy | repair, debugging | `analyze-ci`, `temporal-python-testing`, `testing-python`, `uv-package-manager` |
| `fix-build-google-auto` | easy | repair, debugging | `maven-build-lifecycle`, `maven-dependency-management`, `maven-plugin-configuration` |
| `fix-visual-stability` | hard | repair, debugging | `browser-testing`, `react-best-practices`, `web-interface-guidelines` |
| `flink-query` | hard | implementation, analysis | `pdf`, `senior-data-engineer` |
| `jax-computing-basics` | medium | implementation, calculation | `jax-skills` |
| `llm-prefix-cache-replay` | medium | implementation, simulation | `cache-policy-comparison`, `prefix-cache-replay` |
| `parallel-tfidf-search` | medium | implementation, optimization | `memory-optimization`, `python-parallelization`, `workload-balancing` |
| `python-scala-translation` | medium | transformation, implementation | `python-scala-collections`, `python-scala-functional`, `python-scala-idioms`, `python-scala-libraries`, `python-scala-oop`, `python-scala-syntax-mapping` |
| `react-performance-debugging` | hard | debugging, optimization | `browser-testing`, `react-best-practices` |
| `simpo-code-reproduction` | hard | implementation | `nlp-research-repo-package-installment`, `pdf` |
| `spring-boot-jakarta-migration` | hard | transformation | `hibernate-upgrade`, `jakarta-namespace`, `restclient-migration`, `spring-boot-migration`, `spring-security-6` |
| `tictoc-unnecessary-abort-detection` | hard | detection, analysis | `transaction-concurrency-control-foundations`, `transaction-protocol-reasoning`, `transaction-trace-analysis` |

### industrial-physical-systems (14 tasks)

| Task | Difficulty | Task type | Shipped skills |
|---|---|---|---|
| `3d-scan-calc` | hard | calculation, extraction | `mesh-analysis` |
| `ada-bathroom-plan-repair` | hard | repair, extraction | `ada-plan-view-accessibility`, `architectural-dxf-extraction`, `geometric-layout-repair` |
| `adaptive-cruise-control` | medium | implementation, simulation | `csv-processing`, `pid-controller`, `simulation-metrics`, `vehicle-dynamics`, `yaml-config` |
| `drone-planning-control` | medium | implementation, simulation, optimization | `attitude-controller-planner`, `flight-plan-parser`, `motor-model-dynamics`, `plot-quadrotor`, `position-controller-trajectory-planner`, `stepinfo-3d` |
| `dynamic-object-aware-egomotion` | medium | analysis, detection, classification | `dyn-object-masks`, `egomotion-estimation`, `output-validation`, `sampling-and-indexing` |
| `energy-ac-optimal-power-flow` | medium | optimization, verification | `ac-branch-pi-model`, `casadi-ipopt-nlp`, `power-flow-data` |
| `energy-market-pricing` | hard | optimization, analysis | `dc-power-flow`, `economic-dispatch`, `locational-marginal-prices`, `power-flow-data` |
| `energy-unit-commitment` | hard | optimization, planning | `milp-solver-workflow`, `unit-commitment-data-modeling`, `unit-commitment-operating-rules` |
| `grid-dispatch-operator` | medium | optimization, calculation | `dc-power-flow`, `economic-dispatch`, `power-flow-data` |
| `hvac-control` | medium | implementation, simulation | `excitation-signal-design`, `first-order-model-fitting`, `imc-tuning-rules`, `safety-interlocks`, `scipy-curve-fit` |
| `manufacturing-codebook-normalization` | medium | classification, transformation | `manufacturing-failure-reason-codebook-normalization`, `reference.md` |
| `manufacturing-equipment-maintenance` | medium | analysis, calculation | `reference.md`, `reflow-machine-maintenance-guidance`, `reflow-profile-compliance-toolkit` |
| `manufacturing-fjsp-optimization` | medium | optimization, planning | `fjsp-baseline-repair-with-downtime-and-policy`, `reference.md` |
| `r2r-mpc-control` | medium | implementation, simulation | `finite-horizon-lqr`, `integral-action-design`, `mpc-horizon-tuning`, `state-space-linearization` |

### office-white-collar (14 tasks)

| Task | Difficulty | Task type | Shipped skills |
|---|---|---|---|
| `citation-check` | medium | verification, search | `citation-management` |
| `court-form-filling` | easy | extraction, generation | `pdf` |
| `edit-pdf` | medium | transformation, formatting | `pdf-editing`, `text-parser` |
| `enterprise-information-search` | hard | search, extraction | `enterprise-artifact-search` |
| `exceltable-in-ppt` | medium | transformation, extraction | `pptx`, `xlsx` |
| `jpg-ocr-stat` | hard | extraction, transformation | `image-ocr`, `openai-vision`, `pdf`, `video-frame-extraction`, `xlsx` |
| `latex-formula-extraction` | medium | extraction, repair | `marker`, `pdf` |
| `offer-letter-generator` | easy | generation, formatting | `docx` |
| `organize-messy-files` | medium | classification | `docx`, `file-organizer`, `pdf`, `planning-with-files`, `pptx` |
| `paper-anonymizer` | medium | transformation, detection | `academic-pdf-redaction`, `pdf` |
| `pdf-excel-diff` | medium | extraction, analysis | `pdf`, `xlsx` |
| `powerlifting-coef-calc` | easy | calculation, transformation | `powerlifting`, `senior-data-scientist`, `xlsx` |
| `pptx-reference-formatting` | medium | formatting, transformation | `pptx` |
| `sales-pivot-analysis` | medium | analysis, transformation | `pdf`, `xlsx` |

### natural-science (14 tasks)

| Task | Difficulty | Task type | Shipped skills |
|---|---|---|---|
| `crystallographic-wyckoff-position-analysis` | medium | analysis, calculation | `pymatgen`, `sympy` |
| `earthquake-phase-association` | hard | detection, analysis | `gamma-phase-associator`, `licenses`, `obspy-data-api`, `seisbench-model-api`, `seismic-picker-selection` |
| `earthquake-plate-calculation` | medium | calculation, analysis | `geospatial-analysis` |
| `exoplanet-detection-period` | medium | detection, analysis | `box-least-squares`, `exoplanet-workflows`, `light-curve-preprocessing`, `lomb-scargle-periodogram`, `transit-least-squares` |
| `flood-risk-analysis` | medium | analysis, detection | `flood-detection`, `nws-flood-thresholds`, `usgs-data-download` |
| `glm-lake-mendota` | hard | simulation, calculation | `glm-basics`, `glm-calibration`, `glm-output` |
| `gravitational-wave-detection` | medium | detection, analysis | `conditioning`, `matched-filtering` |
| `lab-unit-harmonization` | medium | transformation | `lab-unit-harmonization` |
| `lake-warming-attribution` | medium | analysis, calculation | `contribution-analysis`, `meteorology-driver-classification`, `pca-decomposition`, `trend-analysis` |
| `mars-clouds-clustering` | hard | optimization, classification | `custom-distance-metrics`, `parallel-processing`, `pareto-optimization` |
| `protein-expression-analysis` | medium | analysis, calculation | `xlsx` |
| `quantum-numerical-simulation` | medium | simulation, calculation | `qutip` |
| `radar-vital-signs` | medium | extraction, calculation | `radar-signal-processing`, `radar-vital-signs`, `vital-sign-extraction` |
| `seismic-phase-picking` | hard | detection, classification | `licenses`, `obspy-data-api`, `obspy-datacenter-client`, `seisbench-model-api`, `seismic-picker-selection` |

### finance-economics (9 tasks)

| Task | Difficulty | Task type | Shipped skills |
|---|---|---|---|
| `econ-detrending-correlation` | medium | calculation, analysis | `timeseries-detrending` |
| `financial-modeling-qa` | hard | analysis, extraction | `pdf`, `xlsx` |
| `invoice-fraud-detection` | hard | detection, verification | `fuzzy-match`, `pdf`, `xlsx` |
| `reserves-at-risk-calc` | medium | calculation, analysis | `xlsx` |
| `sec-financial-report` | hard | search, analysis | `13f-analyzer`, `fuzzy-name-search` |
| `shock-analysis-demand` | medium | calculation, analysis | `xlsx` |
| `shock-analysis-supply` | hard | calculation, analysis | `xlsx` |
| `weighted-gdp-calc` | medium | calculation | `xlsx` |
| `xlsx-recover-data` | medium | analysis, calculation | `data-reconciliation`, `xlsx` |

### mathematics-or-formal-reasoning (8 tasks)

| Task | Difficulty | Task type | Shipped skills |
|---|---|---|---|
| `bike-rebalance` | medium | optimization, planning | `geospatial-routing-data`, `logistics-rules-to-optimization`, `routing-subtour-elimination`, `scip-opt` |
| `civ6-adjacency-optimizer` | hard | optimization, planning | `civ6lib`, `hex-grid-spatial`, `map-optimization-strategy`, `sqlite-map-parser` |
| `exam-block-sequencing` | hard | optimization, planning | `mip-solver-and-solution-audit`, `ordered-window-sequencing-mip` |
| `lean4-proof` | medium | verification, implementation | `INSTALLATION.md`, `LICENSE`, `README.md`, `TESTING.md`, `lean4-memories`, `lean4-theorem-proving` |
| `paratransit-routing` | hard | optimization, planning | `ortools-pickup-delivery-routing`, `ortools-routing-modeling` |
| `pddl-airport-planning` | medium | planning | `pddl-skills` |
| `pddl-tpp-planning` | medium | planning, generation | `pddl-skills` |
| `travel-planning` | medium | planning, search | `search-accommodations`, `search-attractions`, `search-cities`, `search-driving-distance`, `search-flights`, `search-restaurants` |

### cybersecurity (7 tasks)

| Task | Difficulty | Task type | Shipped skills |
|---|---|---|---|
| `dapt-intrusion-detection` | hard | analysis, detection, calculation | `pcap-analysis`, `threat-detection` |
| `fix-druid-loophole-cve` | hard | repair | `jackson-security`, `senior-java` |
| `fix-erlang-ssh-cve` | hard | repair, debugging | `erlang-concurrency`, `erlang-distribution`, `erlang-otp-behaviors`, `find-bugs`, `senior-security`, `ssh-penetration-testing` |
| `setup-fuzzing-py` | medium | implementation, verification | `discover-important-function`, `fuzzing-python`, `setup-env` |
| `software-dependency-audit` | medium | detection, analysis | `cvss-score-extraction`, `trivy-offline-vulnerability-scanning`, `vulnerability-csv-reporting` |
| `suricata-custom-exfil` | medium | detection, implementation | `pcap-triage-tshark`, `suricata-offline-evejson`, `suricata-rules-basics` |
| `syzkaller-ppdev-syzlang` | medium | implementation | `syz-extract-constants`, `syzkaller-build-loop`, `syzlang-ioctl-basics` |

### media-content-production (5 tasks)

| Task | Difficulty | Task type | Shipped skills |
|---|---|---|---|
| `mario-coin-counting` | medium | detection, transformation | `ffmpeg-keyframe-extraction`, `image-editing`, `object-counter` |
| `multilingual-video-dubbing` | medium | generation, transformation | `ffmpeg-audio-processing`, `ffmpeg-format-conversion`, `ffmpeg-media-info`, `ffmpeg-video-editing`, `ffmpeg-video-filters`, `text-to-speech` |
| `threejs-structure-parser` | medium | extraction, transformation | `obj-exporter`, `threejs` |
| `threejs-to-obj` | medium | transformation | `obj-exporter`, `threejs` |
| `video-silence-remover` | hard | detection, transformation | `audio-extractor`, `energy-calculator`, `pause-detector`, `report-generator`, `segment-combiner`, `silence-detector`, `video-processor` |

## Skill-type (methodological) index

Every task classifies itself by one or more `skill_type` tags. These describe the *kind* of skill needed, independent of domain:

| skill_type | # tasks | example tasks |
|---|---:|---|
| domain-procedure | 58 | `ada-bathroom-plan-repair`, `adaptive-cruise-control`, `azure-bgp-oscillation-route-leak`… |
| library-api-usage | 31 | `crystallographic-wyckoff-position-analysis`, `dapt-intrusion-detection`, `data-to-d3`… |
| mathematical-method | 30 | `3d-scan-calc`, `adaptive-cruise-control`, `bike-rebalance`… |
| tool-workflow | 20 | `citation-check`, `data-to-d3`, `edit-pdf`… |
| file-format-knowledge | 17 | `3d-scan-calc`, `ada-bathroom-plan-repair`, `court-form-filling`… |
| debugging-heuristic | 8 | `debug-trl-grpo`, `fix-build-agentops`, `fix-build-google-auto`… |
| data-cleaning-procedure | 6 | `flood-risk-analysis`, `invoice-fraud-detection`, `lab-unit-harmonization`… |
| evaluation-protocol | 3 | `llm-prefix-cache-replay`, `manufacturing-equipment-maintenance`, `setup-fuzzing-py` |

## Implications for a task-by-task optimization strategy

**Two very different setups:**

| | current (whole-suite) | task-by-task (EvoSkills-style) |
|---|---|---|
| optimizer target | one shared 4-skill package (docx/pptx/xlsx/pdf) | one skill per task, seeded from the task's own `environment/skills/` |
| optimization signal | average reward across N tasks × 3 trials | reward on the single task × 3 trials |
| gate | paired-SE across N tasks | per-task variance across trials |
| cost per iter | N × 3 rollouts | 1 × 3 rollouts (~1/N cheaper per iter) |
| interpretation | "can generalist office skills help these tasks?" | "can we make each task's own skill better?" |
| out-of-domain risk | high (77 tasks don't need office skills) | low (each optimization sees its own task's tools) |
| paper analog | cap-evolve's original design | EvoSkills 71.1% headline |

**Concrete implications:**

1. **Skill seed changes per task.** For task-by-task, the `seed_capability` must vary. Adapter's `run_batch` would run each task with its own skill package as seed. Simplest: for each task, copy `environment/skills/*` into a per-task seed dir at intake time.

2. **Optimizer prompt changes.** Currently the optimizer sees N tasks' results and proposes edits to the shared package. For per-task, the optimizer sees just 1 task's results and edits just that task's skill set. Much narrower context; probably faster (fewer tokens) and more focused.

3. **Budget scales differently.** Full-suite: 43 tasks × 3 trials × 7 iter = 903 rollouts + 7 optimizer calls. Task-by-task: 43 tasks × 3 trials × 7 iter = **same 903 rollouts but 43 × 7 = 301 optimizer calls** (each smaller). Optimizer $ likely goes up; runner $ same.

4. **Comparison with paper.** EvoSkills reports 71.1% on all 87 tasks with per-task optimization. Our 43-task subset baseline was 13.95%; best-so-far (after 2 accepted whole-suite iterations) 17.05%. Per-task-EvoSkills-style optimization on our runnable subset would be the direct comparison.

5. **Cap-evolve doesn't natively do this.** Cap-evolve is designed for one shared skill package. A task-by-task run would either (a) launch 43 separate cap-evolve runs (one per task, each with its own project dir + seed + spec), or (b) require an adapter/algorithm change so cap-evolve loops over tasks within its own iteration structure.
