import sys
sys.path.insert(0, ".")
from _c6_lib import dump

for t in [
    "django__django-16032", "django__django-16667",
]:
    dump(t)
