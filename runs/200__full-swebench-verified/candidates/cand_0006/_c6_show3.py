import sys
sys.path.insert(0, ".")
from _c6_lib import dump

for t in [
    "django__django-14376", "django__django-15629",
]:
    dump(t)
