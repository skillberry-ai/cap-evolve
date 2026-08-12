# Root conftest.py
#
# The evograph dashboard backend test lives in two places:
#   1. skills/algorithms/evograph/dashboard/backend/tests/  (source template)
#   2. plugins/cap-evolve/skills/algorithms/evograph/dashboard/backend/tests/ (deployed copy)
#
# Both have an identical test_app_security.py. When pytest collects from the repo root
# with the default prepend import mode, both files map to the same Python module name
# (test_app_security), causing the second one's fixtures to never be registered.
#
# Exclude the skills/ copy so only the plugins/ (deployed) copy is collected.
collect_ignore_glob = [
    "skills/algorithms/evograph/dashboard/backend/tests/test_app_security.py",
]
