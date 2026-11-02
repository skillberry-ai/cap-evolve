
from datetime import datetime, timedelta


def normalize_date(value):
    """Normalize a cell value to datetime.datetime or None.
    Handles: datetime passthrough, Excel serial numbers (int/float),
    date strings in several common formats, and blanks."""
    if value is None or (isinstance(value, float) and value != value):
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        # Excel serial: day 1 = 1900-01-01, with the 1900 leap-year bug offset.
        try:
            return datetime(1899, 12, 30) + timedelta(days=float(value))
        except (OverflowError, ValueError):
            return None
    s = str(value).strip()
    if not s:
        return None
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%m/%d/%Y', '%m/%d/%Y %H:%M',
                '%d-%b-%Y', '%b %d, %Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        import pandas as pd
        ts = pd.to_datetime(s, errors='coerce')
        if ts is not None and str(ts) != 'NaT':
            return ts.to_pydatetime()
    except Exception:
        pass
    return None


def year_of(value):
    """Return the year of a normalized date value, or None."""
    d = normalize_date(value)
    return d.year if d is not None else None
