# verifierverif (SHORT, extra find)
- Title: Who Verifies the Verifier? Co-Evolving Inspectable Graders with Self-Improving Agents
- Authors: Xing Zhang, Guanghui Wang, Yanwei Cui, et al. (7; AWS / HSBC). arXiv 2610.11464 v1; 2026-10-08; NeurIPS 2026 Workshop "Who Verifies the Agents? Toward Reliable Agent Development" (PDF p.1 footer).
- Surface: evolves the VERIFIER (expression over typed drawback detectors) alongside a lifecycle-managed skill loop ("Double Ratchet"); not the agent artifact directly.
- Result: +0.21 held-out agreement vs seed on MBPP+; evolved verifier retains 88-110% of the lift of ground truth/rubric across code, text-to-SQL, report generation; removing anchor guards yields a vacuous always-pass verifier that trains skills equally well (abstract p.1).
- RELEVANCE: LOW. Cautionary point for (d): downstream score cannot certify a self-evolved verifier; relevant if CapEvolve ever uses LLM judges as gates.
