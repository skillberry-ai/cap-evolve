# ttse (SHORT)
- Title: TTSE: A Two-Track Online Self-Evolution Framework for LLM Agents (arXiv API title: "TTSE: A Two-Track Online Self-Evolution Framework")
- Authors: Ruimin Pei, Yongkang Wu, Shangyi Zheng, et al. (8 authors; Poisson Lab, Huawei)
- arXiv 2609.24289 v1; first 2026-09-21. Venue: none claimed (ACM-style CCS concepts present, no venue named). arXiv comment: 20 pages, 2 figures, 18 tables. Code URL: none found in text.
- Editable surface: natural-language rule bank, two tracks: FACT (environment facts, verified by count-based evidence) and TIP (task-conditioned procedures); injected via retrieval (p.1-2). Not prompts/tool code/MCP.
- Method: online experience induction (ExpeL-style rules, heuristic +1/-1/-3 votes or Bayesian-Agent posterior P(success) with retire at P<0.45 & beta>=4, Table 12 p.17); rule retirement and contradiction synthesis. No candidate DAG, no gate.
- Evaluation: streaming/train-chunk rule induction then unseen-task eval split on ALFWorld, ScienceWorld, SOPBench, GDPevo; PinchBench is streaming with no held-out test (App. D.4 p.20). 3 repeated runs (p.6). SOPBench aggregate +15.4pp with Bayesian-Agent fusion (p.2).
- Budget: "unified induction budget" matched across ablations (p.2); no $.
- RELEVANCE: LOW. Only touches (e) (rule bank with evidence-based retirement of rules; Bayesian posteriors per rule - cf. our Bayesian per-task posterior, but over rules not tasks) - acknowledge as related work on posterior-based rule lifecycle; does not threaten (a)-(d),(f).
