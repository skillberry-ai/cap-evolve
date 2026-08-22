# Root conftest.py
#
# Intentionally empty. It used to exclude
# skills/algorithms/evograph/dashboard/backend/tests/test_app_security.py from
# collection, because that file existed twice (source template + deployed plugin copy)
# and both mapped to the same module name under pytest's prepend import mode. The
# evograph dashboard was deleted in bac04ebd (#317), so neither copy exists and the
# glob matched nothing.
