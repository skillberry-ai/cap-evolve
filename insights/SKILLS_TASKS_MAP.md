# SkillsBench: skills ↔ tasks map (87 tasks)

Derived from `insights/SKILLSBENCH_INVENTORY.md`'s per-task "Shipped skills" data (the task-by-task-87 run seeds each task from this same per-task skill set — see "Implications for a task-by-task optimization strategy" §1 in that doc).

- **201 distinct skill names** appear across the 87 tasks' shipped-skill lists. 5 of those are boilerplate filenames, not real skills — `README.md`, `LICENSE`, `INSTALLATION.md`, `TESTING.md`, `reference.md` — carried over from how the source repo lays out its `environment/skills/` directories (e.g. `lean4-proof` ships its real skills `lean4-memories`/`lean4-theorem-proving` alongside a `README.md`/`LICENSE`/etc.). These are marked **B** below rather than given a skill number, so the numbering (1–196) covers only actual skills.

- Task numbers (1–87) follow the category order and task order used in `SKILLSBENCH_INVENTORY.md`. Skill numbers follow first-appearance order in that same document.

## Table A — all 87 tasks, by category, with skill numbers


### software-engineering (16 tasks)

| # | Task | Difficulty | Skills (by #) |
|---:|---|---|---|
| 1 | `azure-bgp-oscillation-route-leak` | medium | 1 |
| 2 | `data-to-d3` | medium | 2 |
| 3 | `debug-trl-grpo` | hard | 3, 4, 5 |
| 4 | `dialogue-parser` | easy | 6 |
| 5 | `fix-build-agentops` | easy | 7, 8, 9, 10 |
| 6 | `fix-build-google-auto` | easy | 11, 12, 13 |
| 7 | `fix-visual-stability` | hard | 14, 15, 16 |
| 8 | `flink-query` | hard | 17, 18 |
| 9 | `jax-computing-basics` | medium | 19 |
| 10 | `llm-prefix-cache-replay` | medium | 20, 21 |
| 11 | `parallel-tfidf-search` | medium | 22, 23, 24 |
| 12 | `python-scala-translation` | medium | 25, 26, 27, 28, 29, 30 |
| 13 | `react-performance-debugging` | hard | 14, 15 |
| 14 | `simpo-code-reproduction` | hard | 31, 17 |
| 15 | `spring-boot-jakarta-migration` | hard | 32, 33, 34, 35, 36 |
| 16 | `tictoc-unnecessary-abort-detection` | hard | 37, 38, 39 |

### industrial-physical-systems (14 tasks)

| # | Task | Difficulty | Skills (by #) |
|---:|---|---|---|
| 17 | `3d-scan-calc` | hard | 40 |
| 18 | `ada-bathroom-plan-repair` | hard | 41, 42, 43 |
| 19 | `adaptive-cruise-control` | medium | 44, 45, 46, 47, 48 |
| 20 | `drone-planning-control` | medium | 49, 50, 51, 52, 53, 54 |
| 21 | `dynamic-object-aware-egomotion` | medium | 55, 56, 57, 58 |
| 22 | `energy-ac-optimal-power-flow` | medium | 59, 60, 61 |
| 23 | `energy-market-pricing` | hard | 62, 63, 64, 61 |
| 24 | `energy-unit-commitment` | hard | 65, 66, 67 |
| 25 | `grid-dispatch-operator` | medium | 62, 63, 61 |
| 26 | `hvac-control` | medium | 68, 69, 70, 71, 72 |
| 27 | `manufacturing-codebook-normalization` | medium | 73, B |
| 28 | `manufacturing-equipment-maintenance` | medium | B, 74, 75 |
| 29 | `manufacturing-fjsp-optimization` | medium | 76, B |
| 30 | `r2r-mpc-control` | medium | 77, 78, 79, 80 |

### office-white-collar (14 tasks)

| # | Task | Difficulty | Skills (by #) |
|---:|---|---|---|
| 31 | `citation-check` | medium | 81 |
| 32 | `court-form-filling` | easy | 17 |
| 33 | `edit-pdf` | medium | 82, 83 |
| 34 | `enterprise-information-search` | hard | 84 |
| 35 | `exceltable-in-ppt` | medium | 85, 86 |
| 36 | `jpg-ocr-stat` | hard | 87, 88, 17, 89, 86 |
| 37 | `latex-formula-extraction` | medium | 90, 17 |
| 38 | `offer-letter-generator` | easy | 91 |
| 39 | `organize-messy-files` | medium | 91, 92, 17, 93, 85 |
| 40 | `paper-anonymizer` | medium | 94, 17 |
| 41 | `pdf-excel-diff` | medium | 17, 86 |
| 42 | `powerlifting-coef-calc` | easy | 95, 96, 86 |
| 43 | `pptx-reference-formatting` | medium | 85 |
| 44 | `sales-pivot-analysis` | medium | 17, 86 |

### natural-science (14 tasks)

| # | Task | Difficulty | Skills (by #) |
|---:|---|---|---|
| 45 | `crystallographic-wyckoff-position-analysis` | medium | 97, 98 |
| 46 | `earthquake-phase-association` | hard | 99, 100, 101, 102, 103 |
| 47 | `earthquake-plate-calculation` | medium | 104 |
| 48 | `exoplanet-detection-period` | medium | 105, 106, 107, 108, 109 |
| 49 | `flood-risk-analysis` | medium | 110, 111, 112 |
| 50 | `glm-lake-mendota` | hard | 113, 114, 115 |
| 51 | `gravitational-wave-detection` | medium | 116, 117 |
| 52 | `lab-unit-harmonization` | medium | 118 |
| 53 | `lake-warming-attribution` | medium | 119, 120, 121, 122 |
| 54 | `mars-clouds-clustering` | hard | 123, 124, 125 |
| 55 | `protein-expression-analysis` | medium | 86 |
| 56 | `quantum-numerical-simulation` | medium | 126 |
| 57 | `radar-vital-signs` | medium | 127, 128, 129 |
| 58 | `seismic-phase-picking` | hard | 100, 101, 130, 102, 103 |

### finance-economics (9 tasks)

| # | Task | Difficulty | Skills (by #) |
|---:|---|---|---|
| 59 | `econ-detrending-correlation` | medium | 131 |
| 60 | `financial-modeling-qa` | hard | 17, 86 |
| 61 | `invoice-fraud-detection` | hard | 132, 17, 86 |
| 62 | `reserves-at-risk-calc` | medium | 86 |
| 63 | `sec-financial-report` | hard | 133, 134 |
| 64 | `shock-analysis-demand` | medium | 86 |
| 65 | `shock-analysis-supply` | hard | 86 |
| 66 | `weighted-gdp-calc` | medium | 86 |
| 67 | `xlsx-recover-data` | medium | 135, 86 |

### mathematics-or-formal-reasoning (8 tasks)

| # | Task | Difficulty | Skills (by #) |
|---:|---|---|---|
| 68 | `bike-rebalance` | medium | 136, 137, 138, 139 |
| 69 | `civ6-adjacency-optimizer` | hard | 140, 141, 142, 143 |
| 70 | `exam-block-sequencing` | hard | 144, 145 |
| 71 | `lean4-proof` | medium | B, B, B, B, 146, 147 |
| 72 | `paratransit-routing` | hard | 148, 149 |
| 73 | `pddl-airport-planning` | medium | 150 |
| 74 | `pddl-tpp-planning` | medium | 150 |
| 75 | `travel-planning` | medium | 151, 152, 153, 154, 155, 156 |

### cybersecurity (7 tasks)

| # | Task | Difficulty | Skills (by #) |
|---:|---|---|---|
| 76 | `dapt-intrusion-detection` | hard | 157, 158 |
| 77 | `fix-druid-loophole-cve` | hard | 159, 160 |
| 78 | `fix-erlang-ssh-cve` | hard | 161, 162, 163, 164, 165, 166 |
| 79 | `setup-fuzzing-py` | medium | 167, 168, 169 |
| 80 | `software-dependency-audit` | medium | 170, 171, 172 |
| 81 | `suricata-custom-exfil` | medium | 173, 174, 175 |
| 82 | `syzkaller-ppdev-syzlang` | medium | 176, 177, 178 |

### media-content-production (5 tasks)

| # | Task | Difficulty | Skills (by #) |
|---:|---|---|---|
| 83 | `mario-coin-counting` | medium | 179, 180, 181 |
| 84 | `multilingual-video-dubbing` | medium | 182, 183, 184, 185, 186, 187 |
| 85 | `threejs-structure-parser` | medium | 188, 189 |
| 86 | `threejs-to-obj` | medium | 188, 189 |
| 87 | `video-silence-remover` | hard | 190, 191, 192, 193, 194, 195, 196 |

## Table B — skills index, with the tasks that use each

Rows = skills, numbered by first appearance in Table A. "Categories" lists every category the skill appears in (most skills are single-category; a few — e.g. `pdf`, `xlsx` — cross several).

| # | Skill | # tasks | Categories | Task #s |
|---:|---|---:|---|---|
| 1 | `azure-bgp` | 1 | software-engineering | 1 |
| 2 | `d3-visualization` | 1 | software-engineering | 2 |
| 3 | `grpo` | 1 | software-engineering | 3 |
| 4 | `rl-post-training` | 1 | software-engineering | 3 |
| 5 | `trl` | 1 | software-engineering | 3 |
| 6 | `dialogue-graph` | 1 | software-engineering | 4 |
| 7 | `analyze-ci` | 1 | software-engineering | 5 |
| 8 | `temporal-python-testing` | 1 | software-engineering | 5 |
| 9 | `testing-python` | 1 | software-engineering | 5 |
| 10 | `uv-package-manager` | 1 | software-engineering | 5 |
| 11 | `maven-build-lifecycle` | 1 | software-engineering | 6 |
| 12 | `maven-dependency-management` | 1 | software-engineering | 6 |
| 13 | `maven-plugin-configuration` | 1 | software-engineering | 6 |
| 14 | `browser-testing` | 2 | software-engineering | 7, 13 |
| 15 | `react-best-practices` | 2 | software-engineering | 7, 13 |
| 16 | `web-interface-guidelines` | 1 | software-engineering | 7 |
| 17 | `pdf` | 11 | finance-economics, office-white-collar, software-engineering | 8, 14, 32, 36, 37, 39, 40, 41, 44, 60, 61 |
| 18 | `senior-data-engineer` | 1 | software-engineering | 8 |
| 19 | `jax-skills` | 1 | software-engineering | 9 |
| 20 | `cache-policy-comparison` | 1 | software-engineering | 10 |
| 21 | `prefix-cache-replay` | 1 | software-engineering | 10 |
| 22 | `memory-optimization` | 1 | software-engineering | 11 |
| 23 | `python-parallelization` | 1 | software-engineering | 11 |
| 24 | `workload-balancing` | 1 | software-engineering | 11 |
| 25 | `python-scala-collections` | 1 | software-engineering | 12 |
| 26 | `python-scala-functional` | 1 | software-engineering | 12 |
| 27 | `python-scala-idioms` | 1 | software-engineering | 12 |
| 28 | `python-scala-libraries` | 1 | software-engineering | 12 |
| 29 | `python-scala-oop` | 1 | software-engineering | 12 |
| 30 | `python-scala-syntax-mapping` | 1 | software-engineering | 12 |
| 31 | `nlp-research-repo-package-installment` | 1 | software-engineering | 14 |
| 32 | `hibernate-upgrade` | 1 | software-engineering | 15 |
| 33 | `jakarta-namespace` | 1 | software-engineering | 15 |
| 34 | `restclient-migration` | 1 | software-engineering | 15 |
| 35 | `spring-boot-migration` | 1 | software-engineering | 15 |
| 36 | `spring-security-6` | 1 | software-engineering | 15 |
| 37 | `transaction-concurrency-control-foundations` | 1 | software-engineering | 16 |
| 38 | `transaction-protocol-reasoning` | 1 | software-engineering | 16 |
| 39 | `transaction-trace-analysis` | 1 | software-engineering | 16 |
| 40 | `mesh-analysis` | 1 | industrial-physical-systems | 17 |
| 41 | `ada-plan-view-accessibility` | 1 | industrial-physical-systems | 18 |
| 42 | `architectural-dxf-extraction` | 1 | industrial-physical-systems | 18 |
| 43 | `geometric-layout-repair` | 1 | industrial-physical-systems | 18 |
| 44 | `csv-processing` | 1 | industrial-physical-systems | 19 |
| 45 | `pid-controller` | 1 | industrial-physical-systems | 19 |
| 46 | `simulation-metrics` | 1 | industrial-physical-systems | 19 |
| 47 | `vehicle-dynamics` | 1 | industrial-physical-systems | 19 |
| 48 | `yaml-config` | 1 | industrial-physical-systems | 19 |
| 49 | `attitude-controller-planner` | 1 | industrial-physical-systems | 20 |
| 50 | `flight-plan-parser` | 1 | industrial-physical-systems | 20 |
| 51 | `motor-model-dynamics` | 1 | industrial-physical-systems | 20 |
| 52 | `plot-quadrotor` | 1 | industrial-physical-systems | 20 |
| 53 | `position-controller-trajectory-planner` | 1 | industrial-physical-systems | 20 |
| 54 | `stepinfo-3d` | 1 | industrial-physical-systems | 20 |
| 55 | `dyn-object-masks` | 1 | industrial-physical-systems | 21 |
| 56 | `egomotion-estimation` | 1 | industrial-physical-systems | 21 |
| 57 | `output-validation` | 1 | industrial-physical-systems | 21 |
| 58 | `sampling-and-indexing` | 1 | industrial-physical-systems | 21 |
| 59 | `ac-branch-pi-model` | 1 | industrial-physical-systems | 22 |
| 60 | `casadi-ipopt-nlp` | 1 | industrial-physical-systems | 22 |
| 61 | `power-flow-data` | 3 | industrial-physical-systems | 22, 23, 25 |
| 62 | `dc-power-flow` | 2 | industrial-physical-systems | 23, 25 |
| 63 | `economic-dispatch` | 2 | industrial-physical-systems | 23, 25 |
| 64 | `locational-marginal-prices` | 1 | industrial-physical-systems | 23 |
| 65 | `milp-solver-workflow` | 1 | industrial-physical-systems | 24 |
| 66 | `unit-commitment-data-modeling` | 1 | industrial-physical-systems | 24 |
| 67 | `unit-commitment-operating-rules` | 1 | industrial-physical-systems | 24 |
| 68 | `excitation-signal-design` | 1 | industrial-physical-systems | 26 |
| 69 | `first-order-model-fitting` | 1 | industrial-physical-systems | 26 |
| 70 | `imc-tuning-rules` | 1 | industrial-physical-systems | 26 |
| 71 | `safety-interlocks` | 1 | industrial-physical-systems | 26 |
| 72 | `scipy-curve-fit` | 1 | industrial-physical-systems | 26 |
| 73 | `manufacturing-failure-reason-codebook-normalization` | 1 | industrial-physical-systems | 27 |
| 74 | `reflow-machine-maintenance-guidance` | 1 | industrial-physical-systems | 28 |
| 75 | `reflow-profile-compliance-toolkit` | 1 | industrial-physical-systems | 28 |
| 76 | `fjsp-baseline-repair-with-downtime-and-policy` | 1 | industrial-physical-systems | 29 |
| 77 | `finite-horizon-lqr` | 1 | industrial-physical-systems | 30 |
| 78 | `integral-action-design` | 1 | industrial-physical-systems | 30 |
| 79 | `mpc-horizon-tuning` | 1 | industrial-physical-systems | 30 |
| 80 | `state-space-linearization` | 1 | industrial-physical-systems | 30 |
| 81 | `citation-management` | 1 | office-white-collar | 31 |
| 82 | `pdf-editing` | 1 | office-white-collar | 33 |
| 83 | `text-parser` | 1 | office-white-collar | 33 |
| 84 | `enterprise-artifact-search` | 1 | office-white-collar | 34 |
| 85 | `pptx` | 3 | office-white-collar | 35, 39, 43 |
| 86 | `xlsx` | 13 | finance-economics, natural-science, office-white-collar | 35, 36, 41, 42, 44, 55, 60, 61, 62, 64, 65, 66, 67 |
| 87 | `image-ocr` | 1 | office-white-collar | 36 |
| 88 | `openai-vision` | 1 | office-white-collar | 36 |
| 89 | `video-frame-extraction` | 1 | office-white-collar | 36 |
| 90 | `marker` | 1 | office-white-collar | 37 |
| 91 | `docx` | 2 | office-white-collar | 38, 39 |
| 92 | `file-organizer` | 1 | office-white-collar | 39 |
| 93 | `planning-with-files` | 1 | office-white-collar | 39 |
| 94 | `academic-pdf-redaction` | 1 | office-white-collar | 40 |
| 95 | `powerlifting` | 1 | office-white-collar | 42 |
| 96 | `senior-data-scientist` | 1 | office-white-collar | 42 |
| 97 | `pymatgen` | 1 | natural-science | 45 |
| 98 | `sympy` | 1 | natural-science | 45 |
| 99 | `gamma-phase-associator` | 1 | natural-science | 46 |
| 100 | `licenses` | 2 | natural-science | 46, 58 |
| 101 | `obspy-data-api` | 2 | natural-science | 46, 58 |
| 102 | `seisbench-model-api` | 2 | natural-science | 46, 58 |
| 103 | `seismic-picker-selection` | 2 | natural-science | 46, 58 |
| 104 | `geospatial-analysis` | 1 | natural-science | 47 |
| 105 | `box-least-squares` | 1 | natural-science | 48 |
| 106 | `exoplanet-workflows` | 1 | natural-science | 48 |
| 107 | `light-curve-preprocessing` | 1 | natural-science | 48 |
| 108 | `lomb-scargle-periodogram` | 1 | natural-science | 48 |
| 109 | `transit-least-squares` | 1 | natural-science | 48 |
| 110 | `flood-detection` | 1 | natural-science | 49 |
| 111 | `nws-flood-thresholds` | 1 | natural-science | 49 |
| 112 | `usgs-data-download` | 1 | natural-science | 49 |
| 113 | `glm-basics` | 1 | natural-science | 50 |
| 114 | `glm-calibration` | 1 | natural-science | 50 |
| 115 | `glm-output` | 1 | natural-science | 50 |
| 116 | `conditioning` | 1 | natural-science | 51 |
| 117 | `matched-filtering` | 1 | natural-science | 51 |
| 118 | `lab-unit-harmonization` | 1 | natural-science | 52 |
| 119 | `contribution-analysis` | 1 | natural-science | 53 |
| 120 | `meteorology-driver-classification` | 1 | natural-science | 53 |
| 121 | `pca-decomposition` | 1 | natural-science | 53 |
| 122 | `trend-analysis` | 1 | natural-science | 53 |
| 123 | `custom-distance-metrics` | 1 | natural-science | 54 |
| 124 | `parallel-processing` | 1 | natural-science | 54 |
| 125 | `pareto-optimization` | 1 | natural-science | 54 |
| 126 | `qutip` | 1 | natural-science | 56 |
| 127 | `radar-signal-processing` | 1 | natural-science | 57 |
| 128 | `radar-vital-signs` | 1 | natural-science | 57 |
| 129 | `vital-sign-extraction` | 1 | natural-science | 57 |
| 130 | `obspy-datacenter-client` | 1 | natural-science | 58 |
| 131 | `timeseries-detrending` | 1 | finance-economics | 59 |
| 132 | `fuzzy-match` | 1 | finance-economics | 61 |
| 133 | `13f-analyzer` | 1 | finance-economics | 63 |
| 134 | `fuzzy-name-search` | 1 | finance-economics | 63 |
| 135 | `data-reconciliation` | 1 | finance-economics | 67 |
| 136 | `geospatial-routing-data` | 1 | mathematics-or-formal-reasoning | 68 |
| 137 | `logistics-rules-to-optimization` | 1 | mathematics-or-formal-reasoning | 68 |
| 138 | `routing-subtour-elimination` | 1 | mathematics-or-formal-reasoning | 68 |
| 139 | `scip-opt` | 1 | mathematics-or-formal-reasoning | 68 |
| 140 | `civ6lib` | 1 | mathematics-or-formal-reasoning | 69 |
| 141 | `hex-grid-spatial` | 1 | mathematics-or-formal-reasoning | 69 |
| 142 | `map-optimization-strategy` | 1 | mathematics-or-formal-reasoning | 69 |
| 143 | `sqlite-map-parser` | 1 | mathematics-or-formal-reasoning | 69 |
| 144 | `mip-solver-and-solution-audit` | 1 | mathematics-or-formal-reasoning | 70 |
| 145 | `ordered-window-sequencing-mip` | 1 | mathematics-or-formal-reasoning | 70 |
| 146 | `lean4-memories` | 1 | mathematics-or-formal-reasoning | 71 |
| 147 | `lean4-theorem-proving` | 1 | mathematics-or-formal-reasoning | 71 |
| 148 | `ortools-pickup-delivery-routing` | 1 | mathematics-or-formal-reasoning | 72 |
| 149 | `ortools-routing-modeling` | 1 | mathematics-or-formal-reasoning | 72 |
| 150 | `pddl-skills` | 2 | mathematics-or-formal-reasoning | 73, 74 |
| 151 | `search-accommodations` | 1 | mathematics-or-formal-reasoning | 75 |
| 152 | `search-attractions` | 1 | mathematics-or-formal-reasoning | 75 |
| 153 | `search-cities` | 1 | mathematics-or-formal-reasoning | 75 |
| 154 | `search-driving-distance` | 1 | mathematics-or-formal-reasoning | 75 |
| 155 | `search-flights` | 1 | mathematics-or-formal-reasoning | 75 |
| 156 | `search-restaurants` | 1 | mathematics-or-formal-reasoning | 75 |
| 157 | `pcap-analysis` | 1 | cybersecurity | 76 |
| 158 | `threat-detection` | 1 | cybersecurity | 76 |
| 159 | `jackson-security` | 1 | cybersecurity | 77 |
| 160 | `senior-java` | 1 | cybersecurity | 77 |
| 161 | `erlang-concurrency` | 1 | cybersecurity | 78 |
| 162 | `erlang-distribution` | 1 | cybersecurity | 78 |
| 163 | `erlang-otp-behaviors` | 1 | cybersecurity | 78 |
| 164 | `find-bugs` | 1 | cybersecurity | 78 |
| 165 | `senior-security` | 1 | cybersecurity | 78 |
| 166 | `ssh-penetration-testing` | 1 | cybersecurity | 78 |
| 167 | `discover-important-function` | 1 | cybersecurity | 79 |
| 168 | `fuzzing-python` | 1 | cybersecurity | 79 |
| 169 | `setup-env` | 1 | cybersecurity | 79 |
| 170 | `cvss-score-extraction` | 1 | cybersecurity | 80 |
| 171 | `trivy-offline-vulnerability-scanning` | 1 | cybersecurity | 80 |
| 172 | `vulnerability-csv-reporting` | 1 | cybersecurity | 80 |
| 173 | `pcap-triage-tshark` | 1 | cybersecurity | 81 |
| 174 | `suricata-offline-evejson` | 1 | cybersecurity | 81 |
| 175 | `suricata-rules-basics` | 1 | cybersecurity | 81 |
| 176 | `syz-extract-constants` | 1 | cybersecurity | 82 |
| 177 | `syzkaller-build-loop` | 1 | cybersecurity | 82 |
| 178 | `syzlang-ioctl-basics` | 1 | cybersecurity | 82 |
| 179 | `ffmpeg-keyframe-extraction` | 1 | media-content-production | 83 |
| 180 | `image-editing` | 1 | media-content-production | 83 |
| 181 | `object-counter` | 1 | media-content-production | 83 |
| 182 | `ffmpeg-audio-processing` | 1 | media-content-production | 84 |
| 183 | `ffmpeg-format-conversion` | 1 | media-content-production | 84 |
| 184 | `ffmpeg-media-info` | 1 | media-content-production | 84 |
| 185 | `ffmpeg-video-editing` | 1 | media-content-production | 84 |
| 186 | `ffmpeg-video-filters` | 1 | media-content-production | 84 |
| 187 | `text-to-speech` | 1 | media-content-production | 84 |
| 188 | `obj-exporter` | 2 | media-content-production | 85, 86 |
| 189 | `threejs` | 2 | media-content-production | 85, 86 |
| 190 | `audio-extractor` | 1 | media-content-production | 87 |
| 191 | `energy-calculator` | 1 | media-content-production | 87 |
| 192 | `pause-detector` | 1 | media-content-production | 87 |
| 193 | `report-generator` | 1 | media-content-production | 87 |
| 194 | `segment-combiner` | 1 | media-content-production | 87 |
| 195 | `silence-detector` | 1 | media-content-production | 87 |
| 196 | `video-processor` | 1 | media-content-production | 87 |

## Table C — per-category train/test split (skill-disjoint-safe)

For each category: a **test** subset of tasks whose skills all also appear in at least one **train** task of the same category — i.e. every skill the test set needs to succeed is still present, unseen-combination, in the train set. Intended use: optimize/tune skills on the train tasks, then evaluate held-out on the test tasks. Target was ~20–30% of each category, found greedily (tasks with the fewest skills tried first, since they're least likely to strand a skill). Where a skill is unique to a single task within its category, that task can never be a test task — this is what caps the achievable split, sometimes to 0%.

| Category | n | Test tasks (n, %) | Train task #s | Test task #s |
|---|---:|---|---|---|
| software-engineering | 16 | 1 (6.2%) | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 15, 16 | 13 |
| industrial-physical-systems | 14 | 1 (7.1%) | 17, 18, 19, 20, 21, 22, 23, 24, 26, 27, 28, 29, 30 | 25 |
| office-white-collar | 14 | 4 (28.6%) | 31, 33, 34, 36, 37, 39, 40, 41, 42, 44 | 32, 35, 38, 43 |
| natural-science | 14 | 0 (0.0%) | 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58 | — |
| finance-economics | 9 | 3 (33.3%) | 59, 60, 61, 63, 66, 67 | 62, 64, 65 |
| mathematics-or-formal-reasoning | 8 | 1 (12.5%) | 68, 69, 70, 71, 72, 74, 75 | 73 |
| cybersecurity | 7 | 0 (0.0%) | 76, 77, 78, 79, 80, 81, 82 | — |
| media-content-production | 5 | 1 (20.0%) | 83, 84, 86, 87 | 85 |

### Table C detail — test task names by category


**software-engineering** — 1/16 (6.2%)
- `react-performance-debugging` (#13, skills 14, 15)

**industrial-physical-systems** — 1/14 (7.1%)
- `grid-dispatch-operator` (#25, skills 62, 63, 61)

**office-white-collar** — 4/14 (28.6%)
- `court-form-filling` (#32, skills 17)
- `exceltable-in-ppt` (#35, skills 85, 86)
- `offer-letter-generator` (#38, skills 91)
- `pptx-reference-formatting` (#43, skills 85)

**natural-science** — 0/14 (0.0%)
- _No valid split found — every task in this category has at least one skill unique to it within the category._

**finance-economics** — 3/9 (33.3%)
- `reserves-at-risk-calc` (#62, skills 86)
- `shock-analysis-demand` (#64, skills 86)
- `shock-analysis-supply` (#65, skills 86)

**mathematics-or-formal-reasoning** — 1/8 (12.5%)
- `pddl-airport-planning` (#73, skills 150)

**cybersecurity** — 0/7 (0.0%)
- _No valid split found — every task in this category has at least one skill unique to it within the category._

**media-content-production** — 1/5 (20.0%)
- `threejs-structure-parser` (#85, skills 188, 189)

## Boilerplate entries (not numbered as skills)

| Filename | # tasks | Task #s |
|---|---:|---|
| `reference.md` | 3 | 27, 28, 29 |
| `INSTALLATION.md` | 1 | 71 |
| `LICENSE` | 1 | 71 |
| `README.md` | 1 | 71 |
| `TESTING.md` | 1 | 71 |
