#!/usr/bin/env bash
# Install cvxpy (plus numpy/scipy) so DC-OPF market clearing can be solved.
#
# cvxpy builds a small native (C/C++) extension when it installs. On a bare
# Ubuntu image the Python C headers and compiler are absent, so pip's build of
# cvxpy stops at "fatal error: Python.h: No such file or directory". This
# script installs that build toolchain (apt) and then the solver stack (pip).
# apt installs at the OS level, so the toolchain only needs to be set up once.
set -e
export DEBIAN_FRONTEND=noninteractive

# 1) System build prerequisites (Python headers + compiler) so C extensions build.
if command -v apt-get >/dev/null 2>&1; then
    apt-get update -qq || true
    apt-get install -y -qq python3-dev build-essential || true
fi

# 2) Solver stack. --break-system-packages is needed on PEP 668 "externally
#    managed" images; drop it if you prefer to install into a virtualenv.
pip3 install --break-system-packages -q \
    numpy==1.26.4 scipy==1.11.4 cvxpy==1.4.2

# 3) Sanity check: confirm cvxpy imports and a QP/LP solver is available.
python3 - <<'PY'
import cvxpy, numpy, scipy
print("numpy", numpy.__version__, "scipy", scipy.__version__, "cvxpy", cvxpy.__version__)
print("solvers:", cvxpy.installed_solvers())
PY
echo "Environment ready."
