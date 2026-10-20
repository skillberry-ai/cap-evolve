#!/bin/bash
# The v6_t2 optimizer: stage the last rejected candidate's trials, then run the stock claude-code
# optimizer with exactly the arguments run-optimizer built for it.
#
# Invoked by the claude-code row of the v6_t2 registry.yaml beside this file, with cwd = the
# iteration's workdir. `exec` hands the process to `claude`, so run-optimizer reads claude's own
# stdout (the json result it parses for cost) as if no wrapper were here.
set -eo pipefail
python3 "$(dirname "${BASH_SOURCE[0]}")/stage_rejected.py"
exec claude "$@"
