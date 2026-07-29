# Host support — verified vs best-guess

**Single source of truth** for how far each agent host / optimizer backend has actually
been taken. Every other surface (README "Choose your path", [`INSTALL.md`](INSTALL.md),
[`../RUN.md`](../RUN.md), the site) links here instead of restating the list, so the
claim lives in exactly one place.

cap-evolve is host-agnostic by design — a skill is a directory of Markdown and a
`scripts/run.py` that prints one JSON object, so *any* shell-invokable coding agent can
drive it. That is an architectural claim, and it is true. It is **not** the same claim as
"we have run cap-evolve end-to-end on this host", and this page keeps the two apart.

## What the badges mean

| Badge | Means | Bar |
|---|---|---|
| ✅ **verified** | We execute this host in CI on every relevant run. | A CI job or committed run record that **actually invokes it**. Cited per row below. |
| 🟡 **docs-checked** | Skill dir + headless flags read off the vendor's current docs; **nobody here has run a full optimization on it**. | A reference doc in `skills/optimizers/run-optimizer/references/`. |
| ➖ **best-guess** | The skill dir is inferred from the tool's dotdir convention. May be wrong. | Nothing. Pass `--dest` / `$CAPEVOLVE_SKILLS_DIR` explicitly. |

Only ✅ is a claim about *cap-evolve running*. 🟡 and ➖ are claims about *where files go*.
No row is promoted to ✅ without a linkable artifact — if a row you care about is 🟡 or ➖,
that is the honest state, not an oversight.

## Optimizer backends

`optimizer_skill:` in `capevolve.yaml`, resolved via
[`../skills/optimizers/registry.yaml`](../skills/optimizers/registry.yaml).

| Optimizer | Status | Evidence / what's missing |
|---|---|---|
| `claude-code` | ✅ verified | `optimizer_skill: claude-code` is the optimizer executed by [`ci/benchmarks/lib/run_suite.sh`](../ci/benchmarks/lib/run_suite.sh) (line 135), driven by [`.github/workflows/integration-tests.yml`](../.github/workflows/integration-tests.yml) (tau2 task 9, real models) and [`.github/workflows/benchmarks.yml`](../.github/workflows/benchmarks.yml). Also the optimizer behind the committed run records [`examples/skillsbench/run_full/`](../examples/skillsbench/run_full/) and [`examples/tau2_airline/run_full/`](../examples/tau2_airline/run_full/) — see [`REPRODUCE_skillsbench.md`](REPRODUCE_skillsbench.md) and [`REPRODUCE_tau2.md`](REPRODUCE_tau2.md). |
| `mock` | ✅ verified | The zero-API deterministic proposer. Executed on every push by the `toy-example` job in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml), which runs `examples/toy_calc/run.sh` and asserts `baseline_val 0.0 → test_reward 1.0`. |
| `codex` | 🟡 docs-checked | Flags + `.agents/skills` from [`references/codex.md`](../skills/optimizers/run-optimizer/references/codex.md). No CI job, no committed run record. |
| `gemini-cli` | 🟡 docs-checked | [`references/gemini-cli.md`](../skills/optimizers/run-optimizer/references/gemini-cli.md). Gemini bundles skills inside *extensions*, so the global install path differs from the per-workdir one. Never run here. |
| `opencode` | 🟡 docs-checked | [`references/opencode.md`](../skills/optimizers/run-optimizer/references/opencode.md). Reads `.claude/skills` natively. Never run here. |
| `ibm-bob` | 🟡 docs-checked | [`references/ibm-bob.md`](../skills/optimizers/run-optimizer/references/ibm-bob.md), which flags `--chat-mode code` as "likely-but-unverified". Bob automates this repo's *issue/PR* workflows (`.github/workflows/fix-issues-with-bob.yml`), which is **not** evidence it works as a cap-evolve optimizer. |
| `cursor` | ➖ best-guess | `install.sh` lists `cursor` among the best-guess dir mappings. [`references/cursor.md`](../skills/optimizers/run-optimizer/references/cursor.md) documents the flags only. |
| `droid` (Factory) | ➖ best-guess | Named best-guess in `install.sh`. No `skills_dir` in the registry — skills are not auto-discovered; see [`references/droid.md`](../skills/optimizers/run-optimizer/references/droid.md). |
| `copilot` | ➖ best-guess | Named best-guess in `install.sh`. No `skills_dir`. [`references/copilot.md`](../skills/optimizers/run-optimizer/references/copilot.md). |
| `kimi` | ➖ best-guess | Named best-guess in `install.sh`; [`references/kimi.md`](../skills/optimizers/run-optimizer/references/kimi.md) additionally calls the API-key env var **unverified** and recommends `kimi login`. |
| `pi` | ➖ best-guess | Named best-guess in `install.sh`. No `skills_dir`. [`references/pi.md`](../skills/optimizers/run-optimizer/references/pi.md). |
| `antigravity` | ➖ best-guess | Named best-guess in `install.sh`; [`references/antigravity.md`](../skills/optimizers/run-optimizer/references/antigravity.md) marks the headless invocation "best-guess for current builds — verify with `agy --help`". No documented CI API key, so unattended runs need `$CAPEVOLVE_ANTIGRAVITY_CMD`. |
| `openclaw` | ➖ best-guess | [`references/openclaw.md`](../skills/optimizers/run-optimizer/references/openclaw.md) states the native skill/instruction mechanism is **UNVERIFIED**; the registry deliberately leaves `skills_dir` blank. Requires `$CAPEVOLVE_OPENCLAW_CMD`. |
| `generic` | n/a | Escape hatch: you supply `$CAPEVOLVE_OPTIMIZER_CMD`. Nothing to verify. |

### Capability parity across hosts

Beyond "does it run at all", one capability is host-specific today:

| Capability | Hosts | Note |
|---|---|---|
| Parallel subagents / worktrees (fan out one subagent per failure cluster) | `claude-code` only | The registry's `parallel: "true"` is set for `claude-code` alone, deliberately: "Set it ONLY for an agent you have verified supports subagents (today: claude-code)". Every other host works through clusters sequentially within one candidate. |

## Skill-install destinations (`./install.sh --host <name>`)

Where `install.sh` puts the skill packages. A ➖ row means **pass `--dest`** (or set
`$CAPEVOLVE_SKILLS_DIR`) rather than trusting the guess.

> **No row here can be ✅ by this page's own bar.** Nothing in CI executes `install.sh`
> (`grep -rn 'install\.sh' .github/ ci/` → no hits); CI sets `$CAPEVOLVE_SKILLS_DIR` to the
> repo tree, which takes the *first* precedence branch and bypasses the `--host` mapping
> entirely. So the badges below grade **how well-attested the path is**, not whether an
> install was executed. 🟡 on `claude` is the strongest available claim: it is the
> vendor-documented canonical path and `core/tests/test_native_skills.py` asserts the
> `.claude/skills` string — but no test runs the installer.

| `--host` | Destination | Status |
|---|---|---|
| `claude` / `claude-code` | `~/.claude/skills` | 🟡 docs-checked (vendor-canonical path; `install.sh` is **not** CI-executed) |
| `codex` | `~/.agents/skills` | 🟡 docs-checked (**not** `~/.codex`) |
| `gemini` / `gemini-cli` | `~/.gemini/extensions/cap-evolve/skills` | 🟡 docs-checked (skills live inside an extension — deliberately **not** the registry's per-workdir `skills_dir: .gemini/skills`; see [#143](https://github.com/skillberry-ai/cap-evolve/issues/143)) |
| `opencode` | `~/.config/opencode/skills` | 🟡 docs-checked (also reads `.claude/skills`) |
| `bob` / `ibm-bob` | `~/.bob/skills` | 🟡 docs-checked — `install.sh` notes Bob has no `SKILL.md` concept, so treat placement as advisory |
| `cursor` | `$PWD/.cursor/skills` | ➖ best-guess |
| `droid` / `factory` | `~/.factory/skills` | ➖ best-guess |
| `copilot` | `~/.copilot/skills` | ➖ best-guess |
| `kimi` | `~/.kimi/skills` | ➖ best-guess |
| `pi` | `~/.pi/skills` | ➖ best-guess |
| `antigravity` / `agy` | `~/.antigravity/skills` | ➖ best-guess |
| `openclaw` | `~/.openclaw/workspace/skills` | ➖ best-guess |
| anything else | `~/.config/<host>/skills` | ➖ best-guess |

Destination precedence: `$CAPEVOLVE_SKILLS_DIR` > `--host` mapping > `./.claude/skills` >
`~/.claude/skills` > `~/.capevolve/skills`.

## Promoting a host to ✅

The bar is an artifact a stranger can check, not a report that it worked:

1. Run a real optimization on that host — `examples/toy_calc` with the host as
   `optimizer_skill` is enough, and costs one cheap iteration.
2. Commit the run record (or add a CI job that executes it).
3. Move the row to ✅ **here**, citing that path. Because every other surface links to
   this page, one edit updates them all.

Please do not upgrade a row on the strength of "it should work" — a wrong ✅ costs more
trust than an honest ➖.
