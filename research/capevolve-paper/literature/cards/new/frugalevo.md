# frugalevo (SHORT, extra find)
- Title: FrugalEvo: Towards Cost-Aware LLM-Guided Program Evolution
- Authors: Hui Chen, Xuan Qi, James Xu Zhao, et al. (8; NUS / UW / Princeton / Stanford). arXiv 2610.03675 v1; first = latest 2026-10-02; "Preprint". Code: https://github.com/chchenhui/frugalevo (p.1).
- Surface: a single program (circle packing, systems/algorithmic optimisation, ALE-Bench-Lite), not agent harnesses.
- Search: LLM-guided evolution with a strong LLM exploring strategies and a cheaper LLM implementing/refining code; cache-efficient prompt prefix sharing; new metric BA-AUC = area under best-so-far score vs cumulative LLM cost up to budget (p.1).
- Evaluation: score from evaluator; budget as dollars; 3 runs averaged with $1 budget in Fig.1 (p.1).
- Headline: higher BA-AUC on 9 of 10 tasks vs OpenEvolve, ShinkaEvolve, AdaEvolve, EvoX; circle packing SOTA for $1.68 (GPT-5.6 Terra+Luna) or $0.55 (GLM-5.3 + Flash) vs ~$50 average for multi-agent methods CORAL, SwarmResearch (abstract p.1).
- RELEVANCE: LOW-MED. Supports reporting cost-normalised anytime curves (BA-AUC) -> consider adopting for CapEvolve spend-awareness reporting; threatens (a) only for the "spend-aware" wording on program evolution. Not on agent surfaces.
