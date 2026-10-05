import sys
sys.path.insert(0, ".")
from _c6_lib import dump

# Failing tasks (reward 0 with actual agent steps), excluding infra-errored
for t in [
    "astropy__astropy-13453", "django__django-10554", "django__django-11555",
]:
    dump(t, tail_n=None)
