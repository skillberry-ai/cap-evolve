# agent-capo-core

[![python](https://img.shields.io/badge/python-3.10%2B-blue)](https://pypi.org/project/agent-capo-core/)
[![license](https://img.shields.io/badge/license-MIT-informational)](../LICENSE)
[![deps](https://img.shields.io/badge/runtime%20deps-0%20(stdlib)-success)](#)

Tiny stdlib-only honest-evaluation substrate for the
[AgentCapTune](https://github.com/skillberry-ai/agent-capo) skills library.

Provides the `acapo` CLI and the four-phase eval loop (baseline → optimize → gate → finalize).
Zero runtime dependencies — pure Python 3.10+ stdlib.

## Install

```bash
pip install agent-capo-core        # from PyPI (once published)
# or, from the repo:
pip install ./core
```

## Usage

```bash
acapo run   --spec .agentcapo/project/acapo.yaml \
            --project .agentcapo/project
acapo check --spec .agentcapo/project/acapo.yaml   # validate adapter
acapo report                                        # regenerate dashboard
```

See the [AgentCapTune repository](https://github.com/skillberry-ai/agent-capo) for full
documentation, examples, and the skills library.

## License

MIT.
