#!/usr/bin/env python3
"""Print the current time on the user's machine, in EvoGraph's canonical timestamp format.

Every agent (lead, builders, solvers, PR Manager) calls this whenever it needs a timestamp —
results JSON, solution front-matter, anywhere a time is written — instead of inventing one. That
way every timestamp across the whole run shares one clock and one timezone: the user's PC local
time. ISO-8601 with the local UTC offset, second precision, e.g. 2026-06-28T14:00:00+03:00.

    python skills/evo-graph/scripts/now.py
"""
from datetime import datetime

if __name__ == "__main__":
    print(datetime.now().astimezone().isoformat(timespec="seconds"))
