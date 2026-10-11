# apex (SHORT)
Title: APEX: Automated Prompt Engineering eXpert with Dynamic Data Selection
Authors: Fei Wang, Si Si, Cho-Jui Hsieh, Inderjit S. Dhillon (4; Google/UCLA)
arXiv: 2606.11459 v1 (only version); first posted 2026-06-09; updated same.
Venue/status: arXiv preprint ("Preprint." p1); no arXiv comment/journal_ref. Code URL: none stated in text.
Surface: single prompt string (task instruction).
Search/selection: GEPA/APO-style reflective mutation; data stratified into Easy/Hard/Mixed tiers from a k=5 lineage window; mutation batches drawn from "Mixed-Fail" bucket; candidate evaluation on a "rank-sensitive" subset (T=100 points/iter) with annealed anchor ratio (alpha 0.2, +0.03 per improvement) and cached outcomes (incremental eval) (p5-7).
Evaluation/held-out: subset-based selection over the dev set, final reported on disjoint test sets (IFBench 500 dev/294 test; SimpleQA Verified 700/300; FACTS 660/200) (p7); test not used for selection as described. Fixed 5,000 evaluation-call budget for all methods.
Headline: Table 1 (p6) Gemini 2.5 Flash avg 60.5 (+11.2) vs GEPA 54.5 (+5.2), APO(|D|) 53.6; Gemma 3 27B 48.0 vs GEPA 45.1, APO 45.2. Mean +/- sd shown; number of seeds/runs UNVERIFIED (not found in text).
Cost: budget counted in evaluation calls (5,000); token-vs-accuracy Pareto in Fig 5 (p13), IFBench only. MIPRO not compared; GEPA/APO via official repos.
RELEVANCE: MED-HIGH. Directly threatens claim (a) in its "per-task/data-point allocation" form: history-based (lineage) task tiering to choose which tasks to evaluate/mutate on, same family as our posterior-per-task + cheap-subset triage. Prompt-only, no agent controller, no sealed-test accounting, no merging.
