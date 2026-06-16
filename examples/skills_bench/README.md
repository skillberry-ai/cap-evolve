# Integrate a new benchmark, step by step — skills-bench + IBM Bob + gpt-oss-120b

This is the worked example of AgentCapTune's core promise: **integrate any benchmark
by writing one adapter.** Here the benchmark is
[skills-bench](https://github.com/benchflow-ai/skillsbench) (evaluates how well an
agent uses an Agent **Skill**), the optimizer is **IBM Bob**, and the agent under
test (the RUNNER) is **`openai/gpt-oss-120b`** via IBM RITS.

The capability being optimized is a **skill package** (`skill-package`): AgentCapTune
edits `SKILL.md`, the runner re-runs skills-bench tasks with the edited skill
injected (`--skills-dir … --skill-mode with-skill`), and the task verifier's reward
drives the loop.

> Targets the **skills-bench v1.2 CLI** (`bench eval create`). Tasks are `task.md`
> packages run in a Docker sandbox.

---

## The general recipe (any benchmark, 4 steps)

1. **Implement the 4-method adapter** (`CapabilityAdapter`): `tasks` · `run_target`
   · `score` · `apply`. (See [`adapter.py`](adapter.py) and
   [docs/ADAPTER_CONTRACT.md](../../docs/ADAPTER_CONTRACT.md).)
2. **Pick** the capability (`capabilities: [skill-package]`), optimizer (`ibm-bob`),
   and algorithm (`all-at-once`) in `acapo.yaml`.
3. `acapo check` — the hard gate (adapter implemented + deterministic scorer).
4. `acapo run` — baseline → optimize → finalize (sealed test) → report + dashboard.

No AgentCapTune core/skill changes are needed for a new benchmark.

---

## Step 0 — prerequisites
```bash
# AgentCapTune
pip install ./core            # or export AGENT_CAPO_CORE=$PWD/core

# skills-bench (Docker required; provides the `bench` CLI)
git clone https://github.com/benchflow-ai/skillsbench && cd skillsbench
uv sync --locked
uv run bench eval create --help          # confirm the v1.2 flags

# IBM Bob (the optimizer)
curl -fsSL https://bob.ibm.com/download/bobshell.sh | bash -s -- --package-manager npm
bob --logout && bob --accept-license      # one-time interactive login: binds the key to its team
```

## Step 1 — credentials (.env at the repo root)
```
RITS_API_KEY=...           # the RUNNER: routes gpt-oss-120b through IBM RITS
BOBSHELL_API_KEY=bob_...   # the OPTIMIZER: IBM Bob (run `bob --accept-license` once to bind it)
```

## Step 2 — choose a RUNNER agent (must be *skill-aware*)

skills-bench injects the candidate skill into the agent's skill dir, so the agent
must read skills. Skill-aware agents: `claude`, `pi-acp`, `opencode`, `openclaw`,
`gemini`, `codex`, `openhands`. (`deepagents` / `harvey-lab` are **not** skill-aware
— they ignore the injected skill, so the optimizer has no signal.)

For gpt-oss-120b via an OpenAI-compatible endpoint, **`pi-acp`** works well and is
pure-Python/JS with no native binary. (On Apple Silicon, `opencode` may ship a
wrong-arch binary and `openclaw`'s npm install can OOM — `pi-acp` avoids both.)

## Step 3 — route gpt-oss-120b (the RITS bridge)

RITS authenticates with a **custom `RITS_API_KEY` header**, not `Authorization:
Bearer`. The in-sandbox agents (and benchflow's own LiteLLM proxy) send Bearer, so
they cannot call RITS directly. Bridge it with a tiny local LiteLLM proxy that
accepts Bearer and forwards to RITS with the custom header:

```yaml
# /tmp/rits_bridge.yaml  — fill RITS_API_KEY into the header
model_list:
  - model_name: "*"
    litellm_params:
      model: hosted_vllm/openai/gpt-oss-120b      # hosted_vllm/ passes the id through verbatim
      api_base: https://inference-3scale-apicast-production.apps.rits.fmaas.res.ibm.com/gpt-oss-120b/v1
      api_key: rits
      extra_headers: { RITS_API_KEY: <YOUR_RITS_API_KEY> }
general_settings: { master_key: sk-bridge-acapo }
litellm_settings: { drop_params: true }
```
```bash
# start the bridge (use skills-bench's venv litellm — it has the [proxy] extras)
skillsbench/.venv/bin/litellm --config /tmp/rits_bridge.yaml --port 8123 --host 127.0.0.1 &
# benchflow's `vllm` provider takes its upstream from BENCHFLOW_PROVIDER_BASE_URL:
export BENCHFLOW_PROVIDER_BASE_URL=http://127.0.0.1:8123/v1
export BENCHFLOW_PROVIDER_API_KEY=sk-bridge-acapo OPENAI_API_KEY=sk-bridge-acapo
```

A model already on **Bearer auth** (OpenAI / Anthropic / Gemini, or a vLLM server)
needs no bridge — set `BENCHFLOW_PROVIDER_BASE_URL`/`OPENAI_API_KEY` to it directly.

## Step 4 — wire + check
```bash
REPO=/path/to/AgentCapTune
export AGENT_CAPO_CORE=$REPO/core PYTHONPATH=$REPO/core ACAPO_SKILLS_DIR=$REPO/skills
export ACAPO_SKILLSBENCH_ROOT=/path/to/skillsbench
export ACAPO_SKB_TASK_IDS="offer-letter-generator,powerlifting-coef-calc"
export ACAPO_SKB_AGENT=pi-acp ACAPO_SKB_MODEL=vllm/gpt-oss-120b ACAPO_SKB_SANDBOX=docker

R=/tmp/skb; rm -rf $R; mkdir -p $R/.agentcapo/project/adapters
cp $REPO/examples/skills_bench/adapter.py   $R/.agentcapo/project/adapters/
cp -R $REPO/examples/skills_bench/seed_skill $R/seed_skill
cp $REPO/examples/skills_bench/acapo.yaml    $R/.agentcapo/project/acapo.yaml

python3 -m agent_capo.cli check $R/.agentcapo/project          # HARD GATE
```

## Step 5 — run
```bash
export BOBSHELL_API_KEY="$(grep ^BOBSHELL_API_KEY= .env | cut -d= -f2- | tr -d '\"'\'' ')"
python3 -m agent_capo.cli run --project $R/.agentcapo/project
# baseline (gpt-oss-120b + seed skill on val) -> Bob edits SKILL.md -> re-score ->
# significance gate -> sealed test -> report.md + dashboard.html
git -C $R/.agentcapo/run_* log --oneline     # one commit per iteration
```

`acapo.yaml` here pins `split_seed: 0` so **val = offer-letter-generator** (the
skill-sensitive docx task — the thin seed skill omits nested-table / header /
conditional handling, which is the optimization headroom) and **test =
powerlifting-coef-calc** (held out, sealed).

## Validate the harness for free (`oracle`)

`--agent oracle` runs each task's reference solution — no model, no bridge, fast.
Use it to confirm a task is self-contained (oracle reward 1.0) before spending model
budget. `ACAPO_SKB_AGENT=oracle acapo check`/`run` exercises the whole adapter
(tasks → run_target → score) deterministically. Note: oracle ignores the injected
skill, so it shows **no** optimization signal — only the harness wiring.

## Notes / gotchas
- **Docker must be running**; each task builds a container (slow first time).
- **Reward is binary** (0/1) per task — use `num_trials ≥ 2` and pick tasks where the
  skill genuinely moves the outcome so the significance gate has signal.
- **Bob auth:** if `bob` returns 401 (user profile) or 403 (fetch models), the key
  isn't bound to its team — run `bob --logout && bob --accept-license` once to
  re-bind. Any optimizer drives the identical loop; swap `optimizer_skill:
  claude-code` / `codex` / `generic` if Bob is unavailable.
- **Pick a skill-aware agent** (Step 2) — a non-skill-aware runner makes the
  optimizer's edits invisible to the score.
```
