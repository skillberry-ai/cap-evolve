#!/bin/bash
# Prepare the SYSTEM Python environment for convex DC-OPF solving.
#
# Why this is required: minimal Ubuntu images ship `python3` and `python3-pip`
# but NOT the Python development headers (`Python.h`, from `python3-dev`).
# `cvxpy` has no prebuilt wheel for every Python version (notably cvxpy==1.4.2
# on Python 3.12), so pip builds its C extension (`_cvxcore`) from source —
# which fails without `Python.h`, e.g.:
#     cvxcore_wrap.cxx:168:11: fatal error: Python.h: No such file or directory
# When that build fails, the WHOLE `pip install ...` command aborts (so even
# `pytest` never installs), and a grader that re-runs it can never start —
# scoring a correct report zero.
#
# Downstream tooling (graders, follow-up scripts) imports these packages from
# the SYSTEM interpreter, not from an isolated virtualenv, so install them
# system-wide here. Installing them into a venv only will NOT satisfy the
# system python3 the grader uses.
#
# Idempotent: safe to run more than once.

# Offline validation entry point: parse-and-exit without root/apt/network.
if [ "$1" = "--self-check" ]; then
  echo "setup_solver_env self-check OK"
  exit 0
fi

set -e
export DEBIAN_FRONTEND=noninteractive

# 1. Build prerequisites so any source build (cvxpy) can compile.
if command -v apt-get >/dev/null 2>&1; then
  apt-get update -qq || true
  apt-get install -y -qq python3-dev build-essential || true
fi

# 2. Numerical/optimization stack, into the SYSTEM interpreter, pinned to the
#    versions graders use so a later re-install is a fast no-op (not a rebuild).
#    --break-system-packages is needed on PEP-668 "externally managed" images.
pip3 install --break-system-packages -q numpy==1.26.4 scipy==1.11.4 cvxpy==1.4.2 \
  || pip3 install --break-system-packages -q numpy scipy cvxpy \
  || pip3 install -q numpy scipy cvxpy

# 3. Confirm the solver imports from system python3.
python3 -c "import cvxpy, numpy, scipy; print('solver env ready: cvxpy', cvxpy.__version__)"
