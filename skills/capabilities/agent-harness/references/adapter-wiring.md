# Wiring the harness artifact into an adapter

The capability only edits files. The adapter decides what each setting does in the
real agent, so a setting the adapter does not read is a setting that changes nothing.
Wire the settings at intake, list them in `harness_policy.json`, and the optimizer
cannot spend a gate evaluation on an unwired key.

## Steps at intake

1. Read the agent's loop. List which of the `SCHEMA` keys in `scripts/abstract.py`
   map to a real setting (a max-steps argument, a compaction option, a retry count).
2. Write the seed `harness.json` with the agent's CURRENT values, so the seed scores
   the same as the unmodified agent. An empty seed is valid too.
3. Write `harness_policy.json`:

   ```json
   {"allow": ["config", "lesson", "code"],
    "wired": ["loop.max_steps", "loop.repeat_limit", "loop.on_repeat",
              "context.*", "memory.*", "tool_errors.max_retries"]}
   ```

4. In the adapter's `live()` (or `run_target`), read the candidate dir and configure
   the agent, as below. Read the files for every rollout from the candidate dir given
   in `ctx`, never from a cached global, or two candidates evaluated in parallel will
   share settings.
5. Run `cap-evolve check` and one seed eval; confirm the seed score equals the
   unmodified agent's.

## A minimal example

```python
import importlib.util, json
from pathlib import Path

def load_harness(cand: Path) -> dict:
    cfg = json.loads((cand / "harness.json").read_text()) if (cand / "harness.json").exists() else {}
    mem = cfg.get("memory", {})
    lessons = []
    lp = cand / mem.get("path", "memory/lessons.jsonl")
    if mem.get("mode", "off") != "off" and lp.exists():
        lessons = [json.loads(l) for l in lp.read_text().splitlines() if l.strip()]
    hooks = {}
    for f in sorted((cand / "hooks").glob("*.py")) if (cand / "hooks").is_dir() else []:
        spec = importlib.util.spec_from_file_location(f"hook_{f.stem}", f)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        hooks[f.stem] = mod
    return {"cfg": cfg, "lessons": lessons, "hooks": hooks}

def lessons_block(lessons, task_text: str, top_k: int | None) -> str:
    if top_k:  # trivial keyword retrieval; replace with the agent's own retriever
        words = set(task_text.lower().split())
        lessons = sorted(lessons, key=lambda x: -len(words & set(x.get("tags", []))))[:top_k]
    lines = [f"- When {x['when']}: {x['do']}" for x in lessons]
    return "## Lessons from earlier runs\n" + "\n".join(lines) if lines else ""

def run_target(self, task, ctx, *, seed=0):
    h = load_harness(Path(ctx))
    cfg = h["cfg"]
    agent = make_agent(  # your agent's constructor
        max_steps=cfg.get("loop", {}).get("max_steps", 30),
        compaction=h["hooks"].get("compact"),   # hooks/compact.py, if present
        max_retries=cfg.get("tool_errors", {}).get("max_retries", 0),
    )
    extra = lessons_block(h["lessons"], task.prompt, cfg.get("memory", {}).get("top_k"))
    return agent.run(task, system_suffix=extra, seed=seed)   # memory is read-only here
```

## Rules for the adapter

- **Never write to the candidate dir during a rollout.** Memory is read-only while a
  rollout is scored. A write would make the next rollout see a different candidate
  from the one the gate thinks it measured.
- **Inject lessons at a fixed position** (`memory.inject_at`), after the stable part
  of the prompt, so the KV cache keeps the prefix.
- **Log what the harness did** in the rollout trace: which lessons were injected,
  whether compaction ran, how many retries and repeat nudges fired. The optimizer can
  verify an edit only if the trace shows it fired.
- **Report the cost per rollout** (`Rollout.cost_usd`), so a sampling or verification gain
  can be read next to what it cost.
