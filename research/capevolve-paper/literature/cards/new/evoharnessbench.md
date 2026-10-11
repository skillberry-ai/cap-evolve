# evoharnessbench (SHORT)
- Title: EvoHarnessBench: Can Your Agents Keep Pace with an Evolving Harness?
- Authors: Zixuan Ke, Vaidehi Patil, Haizhou Shi, et al. (12 authors; Salesforce AI Research / UNC / UW-Madison)
- arXiv 2609.04280; PDF header reads v3 (arXiv API listing showed updated 2026-09-26; the abs-page version scrape said v2 - PDF header "arXiv:2609.04280v3 [cs.MA] 26 Sep 2026" is authoritative, file saved as v3). First 2026-09-03. Venue: none claimed; arXiv comment gives project page https://mas-orchestra.salesforceresearch.ai/evoharness/ (no code URL stated).
- Surface: benchmark of externally evolving harness (tools, skills, specialist agents; 17 streams, 802 tasks, 520 tools, 42 skills, 62 agents, p.1). Not an optimizer.
- Methods evaluated (self-evolving adaptation): memory systems, GEPA (prompt), Meta-Harness (code) (p.6-7). Held-out adaptation split used for evaluation (p.3).
- Headline: harness expansion alone causes "harness-induced forgetting": drops of 12.1% (tools), 13.8% (skills), 46.4% (agents) (Fig.1B p.2); self-evolving adaptation gains inconsistent (Fig.1C p.2); broader tool exposure raises pass rate but token cost (Obs.1 p.7).
- Budget: reports operating cost/tokens alongside Pass/Score (p.5).
- RELEVANCE: LOW-MED. Does not threaten (a)-(f). Useful motivation for CapEvolve's MCP tool exposure pruning (more tools can hurt / cost more) and a possible external benchmark; cite as context for tool-exposure surface.
