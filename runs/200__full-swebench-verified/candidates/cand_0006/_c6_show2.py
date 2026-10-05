import sys
sys.path.insert(0, ".")
from _c6_lib import dump

for t in [
    "django__django-12325", "django__django-12708", "django__django-14007",
]:
    dump(t)
