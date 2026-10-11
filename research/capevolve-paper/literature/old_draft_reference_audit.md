# Audit of the old draft reference list

Source: `campaign-scratch/inputs/paper_zip/references.bib` (50 entries) and `paper.tex` citation counts. Each arXiv-backed entry was compared with the arXiv API record on 2026-10-11 (title, author list, first date, comment/journal_ref). Non-arXiv entries were checked by HTTP status and GitHub API. "Cited" = number of `\cite` occurrences in paper.tex.

Classification: **correct** = title and author list match; **placeholder** = author list truncated ("and others", "X Authors", "X Contributors") and must be completed; **wrong** = title, first author, id or URL contradicts the primary record. "Replacement key" refers to the entry in `bibliography.bib`.

Summary of statuses (first word): wrong: 22, correct: 17, placeholder: 11

Key findings: 29 of 50 entries use truncated/placeholder authors ("and others", "X Authors", "X Contributors"); 17 entries have a title that does not match the arXiv record under normalised comparison (a few of these are only formatting/capitalisation differences, e.g. A$^2$Flow, Sleep-time; the rest are substantively different titles); `tautwo2026` points to the wrong paper (tau-Knowledge); `parsec2026` and `harbor2026` cite non-existent URLs; `zhou2023opro` has the wrong first author; `hu2024adas` has an invented co-author; several benchmark entries (SkillsBench, SpreadsheetBench 2, WikiSkill) invent titles. All should be replaced by the entries in `bibliography.bib` before the draft is reused.

| old key | arXiv id | cited | status | evidence / correction | replacement key |
|---|---|---|---|---|---|
| capevolve2026 | - | 0 | correct (repo) with caveat | Repo github.com/skillberry-ai/cap-evolve exists (HTTP 200), Apache-2.0, created 2026-06-15 (GitHub API 2026-10-11). Title string is the old draft's; GitHub description differs ("Optimize any AI agent's skills, tools/MCP, and prompts against your own evals"). Accessed date 2026-07-28 is not re-verifiable. Corrected entry: capevolve_repo. | - |
| agrawal2026gepa | 2507.19457 | 3 | correct | Title/authors match arXiv API 2026-10-11 (17 authors). | gepa |
| yang2026skillopt | 2605.23904 | 3 | correct | Title/authors match arXiv API 2026-10-11 (15 authors). | skillopt |
| chen2026harnessfix | 2606.06324 | 2 | placeholder authors | Title correct. 6 authors on arXiv (Mengzhuo Chen, Junjie Wang, Zhe Liu, Yawen Wang, Haiming Zheng, Qing Wang). | chen2026from |
| pan2026rho | 2606.05922 | 2 | wrong (title) | Title differs from arXiv: current title is "Evolving Agents in the Dark: Retrospective Harness Optimization via Self-Preference". Authors (8) match. arXiv comment: Accepted to EMNLP 2026 (Findings) (author-supplied). Corrected entry: rho. | rho |
| yang2026evotool | - | 2 | placeholder authors; venue now verified | Authors "Shuo Yang and others" is a placeholder. ACL Anthology URL is real and resolves: ACL 2026 main (Vol.1 Long), pp. 43553-43572, doi 10.18653/v1/2026.acl-long.2016. Corrected entry: evotool. | - |
| zhang2026coevoskills | 2604.01687 | 2 | placeholder authors | Title correct; 14 authors on arXiv API (13 distinct per PDF page 1). COLM 2026 acceptance is supported by arXiv comment + repository (catalog). | coevoskills |
| lee2026metaharness | 2603.28052 | 3 | correct | Title/authors match arXiv API 2026-10-11 (6 authors). | meta-harness |
| hao2026recreate | 2601.11100 | 1 | wrong (title) + placeholder authors | arXiv title: "ReCreate: Reasoning and Creating Domain Agents Driven by Experience"; 9 authors. | hao2026recreate |
| liu2026hasp | 2605.17734 | 2 | correct | Title/authors match arXiv API 2026-10-11 (4 authors). | liu2026harnessing |
| luo2026gsme | 2607.13683 | 2 | wrong (title) | arXiv 2607.13683 is titled "HarnessBank: Semantic Gene-Bank Search with Gated Verification for Agent-Harness Self-Evolution"; the old title ("...Gated Semantic Quality-Diversity") is not the arXiv title. Authors list present (5) but order differs from the API (API order: Luo, Xue, Wang, ..., Deng). | luo2026harnessbank |
| wang2026compound | 2607.14004 | 1 | correct | Title/authors match arXiv API 2026-10-11 (3 authors). | wang2026compound |
| wei2026skillsmith | 2606.01314 | 2 | wrong (title) + placeholder authors | Title should end "for Self-Improving Agent Systems"; 7 authors on arXiv (Yangbo Wei, Zhen Huang, Shaoqiang Lu, ..., Lei He). | skillsmith |
| lin2026wml | 2607.20999 | 1 | wrong (title) + placeholder authors | arXiv title: "Workflow-Localized Mechanism Learning: Attribution-Guided Repair and Knowledge Reuse for Structured Agent Skills"; 6 authors. | lin2026workflowlocalized |
| ni2026trace2skill | 2603.25158 | 3 | wrong (title) + placeholder authors | arXiv title is "Trace2Skill: Distill Trajectory-Local Lessons into Transferable Agent Skills"; 10 authors. | trace2skill |
| han2026sweskills | 2603.15401 | 0 | wrong (title) + placeholder authors | arXiv title: "SWE-Skills-Bench: Do Agent Skills Actually Help in Real-World Software Engineering?"; 7 authors. | swe_skills_bench |
| zhong2026skilllearn | 2604.20087 | 0 | wrong (title) + placeholder authors | arXiv title: "SkillLearnBench: Benchmarking Continual Learning Methods for Agent Skill Generation on Real-World Tasks"; 10 authors. | zhong2026skilllearnbench |
| lin2026aevolve | 2602.00359 | 0 | wrong (title/id mismatch) + placeholder authors | arXiv 2602.00359 is titled "Position: Agentic Evolution is the Path to Evolving LLMs" (comment "Update code link"); the old title "A-Evolve: Toward a Filesystem Contract for Agentic Evolution" does not match the API record (possible later retitling; UNVERIFIED). 14 authors. | lin2026position |
| liu2026adaptive | 2606.01770 | 0 | wrong (title) + placeholder authors | arXiv title: "Adaptive Auto-Harness: Sustained Self-Improvement for Agentic System Deployment on Open-Ended Task Streams"; 10 authors. | adaptiveautoharness |
| robeyns2025sica | 2504.15228 | 0 | placeholder authors; venue note | Title correct; authors: Maxime Robeyns, Martin Szummer, Laurence Aitchison. Workshop paper (ICLR 2025 SSI-FM, per OpenReview, group-D card); must not be cited as main-conference. | sica |
| ruc2026arbor | 2606.11926 | 0 | placeholder authors | Title correct but author "{RUC-NLPIR} and others" is a placeholder; arXiv first author Jiajie Jin (8+ authors; 18 per API). | jin2026toward |
| hu2024adas | 2408.08435 | 2 | wrong (author list) | Adds "Stuart Russell"; arXiv API lists Shengran Hu, Cong Lu, Jeff Clune only. Year 2024 is the arXiv date; ICLR 2025 venue (verified by group-B card). Corrected entry: adas. | adas |
| zhang2024aflow | 2410.10762 | 2 | placeholder authors | Title correct; "Zhang and others" is a placeholder; first author Jiayi Zhang (14 authors). ICLR 2025 oral (group-B card). | aflow |
| shang2024agentsquare | 2410.06153 | 1 | placeholder authors | Title correct; first author Yu Shang (7 authors). | shang2024agentsquare |
| wang2025agentswift | 2506.06017 | 0 | wrong (title, first author) | arXiv title "AgentSwift: Efficient LLM Agent Design via Value-guided Hierarchical Search"; first author Yu Li (not "Wang"); AAAI-2026 per arXiv comment; 8 authors. | li2025agentswift |
| liu2025a2flow | 2511.20693 | 0 | wrong (title, first author) | arXiv title "A^2Flow: Automating Agentic Workflow Generation via Self-Adaptive Abstraction Operators"; first author Mingming Zhao (not "Liu"); AAAI-2026 per arXiv comment. | zhao2025aflow |
| pryzant2023protegi | 2305.03495 | 2 | correct | Title/authors match arXiv API 2026-10-11 (6 authors). | protegi |
| zhou2023opro | 2309.03409 | 2 | wrong (first author) | First author "Chengrun Zhou" is wrong; arXiv: Chengrun Yang, Xuezhi Wang, Yifeng Lu, et al. (7 authors); key should be yang2023opro. Corrected entry: opro. | opro |
| fernando2023promptbreeder | 2309.16797 | 2 | correct | Title/authors match arXiv API 2026-10-11 (5 authors). | promptbreeder |
| khattab2023dspy | 2310.03714 | 1 | correct | Title/authors match arXiv API 2026-10-11 (13 authors). | dspy |
| yuksekgonul2024textgrad | 2406.07496 | 1 | correct for arXiv v1 except author list | Old entry lists 8 authors including Pan Lu (this matches the Nature version, not arXiv v1 which lists 7). If cited as arXiv preprint use 7 authors; if cited as Nature 639:609-616 (2025) use the Nature title "Optimizing generative AI by backpropagating language model feedback". Corrected entry: textgrad (Nature form). | textgrad |
| shinn2023reflexion | 2303.11366 | 1 | wrong (author list) | Omits Edward Berman (present on arXiv v4; API lists 6 authors). Corrected entry: reflexion. | reflexion |
| zhao2023expel | 2308.10144 | 1 | correct | Title/authors match arXiv API 2026-10-11 (6 authors). | expel |
| wang2023voyager | 2305.16291 | 1 | correct | Title/authors match arXiv API 2026-10-11 (8 authors). | voyager |
| zhao2026dynamiccheatsheet | 2504.07952 | 1 | wrong (first author, year) | Authors are Mirac Suzgun, Mert Yuksekgonul, Federico Bianchi, Dan Jurafsky, James Zou (5); arXiv date 2025-04-10 (old year 2026 wrong). Title correct. | suzgun2025dynamic |
| wang2025reasoningbank | 2509.25140 | 1 | wrong (first author) | First author is Siru Ouyang (17 authors); accepted to ICLR 2026 per arXiv comment. Title correct. | ouyang2025reasoningbank |
| snellingen2025sleeptime | 2504.13171 | 0 | wrong (first author) | First author Kevin Lin (then Charlie Snell,...; 7 authors). Title capitalization differs slightly ("Sleep-time Compute: Beyond Inference Scaling at Test-time"). | lin2025sleeptime |
| skillsbench2026 | 2602.12670 | 1 | placeholder + wrong title | Author "SkillsBench Authors" is a placeholder (78 authors on arXiv); title is wrong: "SkillsBench: Benchmarking How Well Agent Skills Work Across Diverse Tasks". | skillsbench |
| terminalbench2026 | 2601.11868 | 0 | wrong (title) | arXiv 2601.11868 is titled "Terminal-Bench: Benchmarking Agents on Hard, Realistic Tasks in Command Line Interfaces"; "Terminal-Bench 2" title is invented; authors truncated ("and others"; 85 authors on arXiv). | terminal-bench |
| tautwo2026 | 2603.04370 | 1 | wrong (id/title mismatch) | eprint 2603.04370 is tau-Knowledge, not tau2-Bench. tau2-Bench is arXiv 2506.07982. Authors are a placeholder. Corrected entries: tau_knowledge / tau2-bench. | tau_knowledge |
| gaia2023 | 2311.12983 | 0 | correct | Title/authors match arXiv API 2026-10-11 (6 authors). | mialon2023gaia |
| appworld2024 | 2407.18901 | 0 | placeholder authors; wrong first author | First author is Harsh Trivedi (not Naman Jain); ACL 2024 camera-ready per arXiv comment. | trivedi2024appworld |
| spreadsheetbench2_2026 | 2606.29955 | 0 | placeholder + wrong title | Author is a placeholder (14 authors on arXiv); title wrong: "SpreadsheetBench 2: Evaluating Agents on End-to-End Business Spreadsheet Workflows". | spreadsheetbench-2 |
| wikiskill2026 | 2608.27454 | 3 | placeholder + wrong title | Author is a placeholder; the title in the old entry ("Self-Evolved Skill Libraries for Spreadsheet Agents") is not the arXiv title: "WikiSkill: Compiling Agent Experience into Persistent Knowledge for Skill Evolution". Authors: Liyan Tang et al. (6). | wikiskill |
| jimenez2024swebench | 2310.06770 | 1 | correct | Title/authors match arXiv API 2026-10-11 (7 authors). | swe_bench |
| ma2024spreadsheetbench | 2406.14991 | 1 | correct | Title/authors match arXiv API 2026-10-11 (9 authors). | spreadsheetbench |
| parsec2026 | - | 0 | wrong (unverifiable URL) | github.com/skillberry-ai/parsec returns 404 (2026-10-11); skillberry-ai org repo list does not include "parsec". Do not cite. | - |
| harbor2026 | - | 1 | wrong (URL 404) | github.com/skillberry-ai/harbor returns 404; Harbor is github.com/harbor-framework/harbor (redirect from laude-institute/harbor). Corrected entry: harbor_framework (year/title UNVERIFIED). | - |
| mcp2024 | - | 1 | correct URL; metadata unverified | modelcontextprotocol.io returns 200; author attribution to Anthropic and year 2024 not re-verified. Corrected entry: mcp_spec. | - |
| agentskills2025 | - | 1 | correct URL; metadata unverified | code.claude.com/docs/en/skills returns 200; year not re-verified. | - |
