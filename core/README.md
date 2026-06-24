# cap-evolve-core

[![python](https://img.shields.io/badge/python-3.10%2B-blue)](https://pypi.org/project/cap-evolve-core/)
[![license](https://img.shields.io/badge/license-Apache--2.0-informational)](../LICENSE)
[![deps](https://img.shields.io/badge/runtime%20deps-0%20(stdlib)-success)](#)

Tiny stdlib-only honest-evaluation substrate for the
[AgentCapTune](https://github.com/skillberry-ai/cap-evolve) skills library.

Provides the `cap-evolve` CLI and the four-phase eval loop (baseline → optimize → gate → finalize).
Zero runtime dependencies — pure Python 3.10+ stdlib.

## Install

```bash
pip install cap-evolve-core        # from PyPI (once published)
# or, from the repo:
pip install ./core
```

## Usage

```bash
cap-evolve run   --spec .capevolve/project/capevolve.yaml \
            --project .capevolve/project
cap-evolve check --spec .capevolve/project/capevolve.yaml   # validate adapter
cap-evolve report                                        # regenerate dashboard
```

See the [AgentCapTune repository](https://github.com/skillberry-ai/cap-evolve) for full
documentation, examples, and the skills library.

## License

Apache-2.0.
