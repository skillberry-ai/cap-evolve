"""General, offline, deterministic date-window helpers.

All functions take plain Python dates/datetimes or ISO date strings and a list of
dates (optionally paired with values). No I/O, no task-specific logic.
"""

from datetime import date, datetime, timedelta


def _to_date(d):
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    if isinstance(d, str):
        return datetime.fromisoformat(d.strip()[:10]).date()
    raise TypeError("expected date, datetime, or ISO date string, got %r" % (d,))


def is_workday(d, holidays=frozenset()):
    """True if d is a weekday (Mon-Fri) and not in holidays (a set of dates)."""
    d = _to_date(d)
    return d.weekday() < 5 and d not in {_to_date(h) for h in holidays}


def workday_offset(d, n, holidays=frozenset()):
    """Excel WORKDAY equivalent: move n workdays from d (n may be negative).
    WORKDAY(D, -4) is the 4th workday strictly before D."""
    d = _to_date(d)
    step = 1 if n > 0 else -1
    remaining = abs(n)
    while remaining > 0:
        d = d + timedelta(days=step)
        if is_workday(d, holidays):
            remaining -= 1
    return d


def workday_window_dates(d, n, holidays=frozenset(), include_start=False):
    """The n workdays in the window ending just before d (or including d if
    include_start=True). Returns them in ascending order. Mirrors the correct
    SUMIFS bounds: >= WORKDAY(d, -n) and < d (or <= d when include_start)."""
    d = _to_date(d)
    if include_start and not is_workday(d, holidays):
        raise ValueError("start date %s is not a workday" % d)
    dates = []
    cur = d
    while len(dates) < n:
        cur = cur - timedelta(days=1)
        if is_workday(cur, holidays):
            dates.append(cur)
    dates.reverse()
    return dates


def count_in_window(dates, start, end, inclusive_start=True, inclusive_end=False):
    """Count how many of dates fall in the window with chosen inclusivity.
    Default mirrors the correct 'last N workdays' SUMIFS: >= start, < end."""
    start = _to_date(start)
    end = _to_date(end)
    c = 0
    for d in dates:
        d = _to_date(d)
        if d > end or (d == end and not inclusive_end):
            continue
        if d < start or (d == start and not inclusive_start):
            continue
        c += 1
    return c


def sum_in_window(pairs, start, end, inclusive_start=True, inclusive_end=False):
    """Sum the value side of (date, value) pairs within the window.
    Same inclusivity semantics as count_in_window."""
    total = 0
    for d, v in pairs:
        d = _to_date(d)
        if d > end or (d == end and not inclusive_end):
            continue
        if d < start or (d == start and not inclusive_start):
            continue
        total += v
    return total
