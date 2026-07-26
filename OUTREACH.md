# cap-evolve — outreach & backlink drafts

> Local working notes for SEO/discoverability outreach. **Not part of the project** —
> uncommitted by design. Delete or `.gitignore` it whenever.
> Generated 2026-07-21.

Backlinks are the single biggest lever for Google ranking beyond your own repo name.
Search Console setup (sitemap, verification) is done; this file is the off-site push.

---

## 1. Show HN post

**Title** (≤ 80 chars; HN adds the "Show HN:" tag):

```
Show HN: Cap-evolve – optimize an AI agent's prompts, tools and skills from evals
```

**URL field:** `https://github.com/skillberry-ai/cap-evolve`

**Text field:**

```
We kept hand-tuning agent prompts and tool code by staring at failed traces, so we
built cap-evolve to do it as an optimization loop instead.

You bring an agent and an eval you already have. Each iteration it: evaluates on a
train split, reads the full failing trajectories (not just the scalar reward),
proposes an edit to whatever you're optimizing, and keeps the edit only if it beats
a held-out val split by a significance margin (Δ > k·SE). The test split is sealed
and scored exactly once at the end, so the headline number isn't cherry-picked.

What it can edit, jointly if you want: system prompts, actual executable tool code,
MCP tool surfaces, and whole skill packages — not model weights. Every candidate is
a real git commit, and a dashboard shows diffs, cost, lineage, and a tasks×iterations
pass/fail heatmap.

It's optimizer-agnostic: the "edit proposer" is any coding agent you already use.
Adapters ship for Claude Code, OpenAI Codex, Cursor, GitHub Copilot, Gemini CLI and
more, plus a generic adapter for any shell-invokable agent and a deterministic mock
for CI.

Benchmark adapters ship for τ²-bench, SWE-bench, SkillsBench, and generic
JSONL/HuggingFace datasets. Some committed, reproducible results:
- τ²-bench airline, held-out 30/10/10 split: sealed test 30.0 → 47.5 (+58% relative).
- τ²-bench airline, fit-metric 50 tasks: 0.536 → 0.694; the edits were deep tool-code
  changes (tools.py 593 → 832 lines), not just prompt wording.
- SkillsBench skill-package optimization, sealed test: 0.556 → 0.667.

It's Python 3.10+, Apache-2.0, zero runtime deps (stdlib only). There's a two-minute
demo that needs no API key (a deterministic toy agent + a mock optimizer, so the score
provably rises without calling any model):

  git clone https://github.com/skillberry-ai/cap-evolve.git
  cd cap-evolve && python3 -m venv .venv && source .venv/bin/activate
  pip install ./core && bash examples/toy_calc/run.sh

It's beta (0.x). Happy to answer questions about the honesty gate, how the trace
diagnosis works, bringing your own optimizer, or where it falls over.
```

**Timing:** ~8–10am US Eastern on a weekday. Reply to every early comment — the first
hour of engagement decides whether it climbs.

---

## 2. Awesome-list PR entries

**awesome-ai-agents:**

```markdown
- [cap-evolve](https://github.com/skillberry-ai/cap-evolve) - Improves an AI agent's prompts, tools, and skills against your own evals: evaluate → diagnose failing traces → propose edit → keep only if it beats a sealed held-out split. Optimizer-agnostic (Claude Code, Codex, Cursor, Gemini CLI, and more). Optimizes what the agent reads, not its weights.
```

**awesome-llmops / awesome-llm:**

```markdown
- [cap-evolve](https://github.com/skillberry-ai/cap-evolve) - GEPA-style reflective optimizer for agent prompts, tool code, and skill packages; val-only significance gate with a sealed test split scored once. Adapters for τ²-bench, SWE-bench, SkillsBench. Zero runtime deps, Apache-2.0.
```

**awesome-mcp (only if a utilities/resources section exists — NOT the server list itself):**

```markdown
- [cap-evolve](https://github.com/skillberry-ai/cap-evolve) - Optimizes an agent's MCP tool surface (and prompts, tool code, and skills) by learning from failed eval traces; honest held-out gate, every candidate a git commit. Bring your own coding agent as the optimizer. Python, Apache-2.0.
```

**PR title:** `Add cap-evolve (agent prompt/tool/skill optimizer)`

**PR body:**

```markdown
Adding cap-evolve — an open-source (Apache-2.0) tool that optimizes an AI agent's
prompts, executable tool code, MCP tool surfaces, and skill packages by learning from
failed evaluation traces, with an honest held-out acceptance gate and a sealed test split.

- Repo: https://github.com/skillberry-ai/cap-evolve
- Docs: https://skillberry-ai.github.io/cap-evolve/
- Optimizer-agnostic: works with Claude Code, OpenAI Codex, Cursor, GitHub Copilot,
  Gemini CLI and more (or any shell-invokable coding agent).
- Benchmark adapters for τ²-bench, SWE-bench, SkillsBench, and generic JSONL/HF datasets.
- Python 3.10+, zero runtime deps (stdlib only), Apache-2.0. Results committed in-repo.

We've followed the contribution guidelines: alphabetical order preserved, one entry,
link checked, description under the length limit.
```

---

## 3. Which repos to PR, and in what order

Priority = **fit × acceptance likelihood × reach**. Reach alone is a trap: a huge list
that rejects off-topic entries (or is unmaintained) is wasted effort. Stats as of
2026-07-21.

### Tier 1 — do these first (strong fit, maintained, good reach)

| Repo | ★ | Last push | Why it fits | Section to target |
|------|---|-----------|-------------|-------------------|
| [e2b-dev/awesome-ai-agents](https://github.com/e2b-dev/awesome-ai-agents) | ~29k | active | Agent ecosystem; cap-evolve is agent tooling | tools/frameworks (check their taxonomy) |
| [tensorchord/Awesome-LLMOps](https://github.com/tensorchord/Awesome-LLMOps) | ~5.9k | active | LLMOps = eval + optimization; near-perfect fit | Training/Optimization or Evaluation |

### Tier 2 — good, actively maintained

| Repo | ★ | Last push | Why it fits | Notes |
|------|---|-----------|-------------|-------|
| [kyrolabs/awesome-agents](https://github.com/kyrolabs/awesome-agents) | ~2.6k | very active (daily) | Agents list; fast to merge | High acceptance odds |
| [steven2358/awesome-generative-ai](https://github.com/steven2358/awesome-generative-ai) | ~12k | active | Broad genAI; has a coding/tools section | Fit under Coding/Tools |

### Tier 3 — high reach but risky (do last, low expectations)

| Repo | ★ | Last push | Risk |
|------|---|-----------|------|
| [Hannibal046/Awesome-LLM](https://github.com/Hannibal046/Awesome-LLM) | ~27k | ~1 yr ago | Likely unmaintained → PR may sit unmerged |
| [punkpeye/awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers) | ~91k | active | **Server** catalog — cap-evolve is not a server; will be rejected unless a resources/utilities section exists |

**Rule of thumb:** land Tier 1 + 2 (4 PRs). Only attempt Tier 3 if you have a genuinely
matching section — a rejected off-topic PR wastes a maintainer's time and yours.

---

## 4. Higher-value than awesome lists (warmest audiences)

These usually beat awesome-list PRs for both traffic and quality of visitor:

1. **DSPy / GEPA communities** (Discord, GitHub Discussions). cap-evolve is GEPA-adjacent —
   this is your single warmest audience. Share the held-out-eval + tool-code angle.
2. **r/LocalLLaMA** and **r/MachineLearning** (tag `[P]`). The honest-eval framing plays well.
3. **A short blog post / dev.to** titled around *"optimizing agent tool code, not just prompts"* —
   your most differentiated hook. The post is itself indexable and links back.
4. **X/LinkedIn** with the dashboard screenshot — now that OG tags are live, links render a rich card.

---
"
## 5. Suggested sequence

1. Publish the dev.to/blog post (so HN/Reddit have a narrative link besides the raw repo).
2. Show HN (weekday morning ET). Then r/LocalLLaMA the same or next day.
3. Open Tier 1 + Tier 2 awesome-list PRs (read each `CONTRIBUTING.md` first — strict
   alphabetical placement + template compliance or auto-reject).
4. Post in DSPy/GEPA channels.
5. Check Search Console **Pages** + **Performance** weekly to watch indexing land.
```
