# cap-evolve

[![PyPI](https://img.shields.io/pypi/v/cap-evolve)](https://pypi.org/project/cap-evolve/)
[![python](https://img.shields.io/badge/python-3.10%2B-blue)](https://pypi.org/project/cap-evolve/)
[![license](https://img.shields.io/badge/license-Apache--2.0-informational)](https://github.com/skillberry-ai/cap-evolve/blob/main/LICENSE)
[![deps](https://img.shields.io/badge/runtime%20deps-0%20(stdlib)-success)](#)

A skills-native, host-agnostic harness for **honestly** optimizing AI-agent
capabilities — system prompts, tool surfaces, MCP tool docs, and Agent Skill packages —
against a real eval, with a sealed test split you can only score once.

Zero runtime dependencies. Pure Python 3.10+ stdlib.

## Install

```bash
pip install cap-evolve
cap-evolve version
```

That is the whole install: the `cap-evolve` CLI, the honest-eval core, the **20 Agent
Skills** (phases, capabilities, **5 algorithms** — 3 run-executable + 2 agent-mode — and
`run-optimizer` over **14 optimizer backends**), and the project templates all ship in
the wheel. No clone, no `node`, no API key for the toy run.

Every run also writes a self-contained static `dashboard.html` you can open directly — no
extra install. The optional **live** dashboard (FastAPI + a prebuilt SPA) is a separate
package that is not on PyPI yet; install it from a clone — see
[INSTALL.md](https://github.com/skillberry-ai/cap-evolve/blob/main/docs/INSTALL.md).

## Usage

```bash
cap-evolve check .capevolve/project                # hard gate — must print {"ok": true}
cap-evolve estimate --spec .capevolve/project/capevolve.yaml    # cost preview, spends nothing
cap-evolve run   --spec .capevolve/project/capevolve.yaml --project .capevolve/project
cap-evolve run   ... --resume                      # continue an interrupted run
cap-evolve dashboard --base .capevolve             # live view over past/current runs
```

Six subcommands: `version`, `splits`, `check`, `run`, `estimate`, `dashboard`.

To drive it from a coding agent (Claude Code, Codex, Gemini CLI, opencode, Cursor,
Droid, Copilot, Kimi, Pi, Antigravity, openclaw, IBM Bob) install the skills into that
host's skills dir — see
[INSTALL.md](https://github.com/skillberry-ai/cap-evolve/blob/main/docs/INSTALL.md).

## Naming

`cap-evolve` is the package to install. `cap-evolve-core` was the pre-1.0 working name
for the same code and is **not** published; nothing depends on it.

See the [cap-evolve repository](https://github.com/skillberry-ai/cap-evolve) for full
documentation, examples, and the adapter contract.

## License

Apache-2.0.
