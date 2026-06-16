"""Normalize a date string to ISO (YYYY-MM-DD). SEED: incomplete on purpose."""
import re


def parse_date(s: str) -> str:
    s = s.strip()
    # Only handles dates already in ISO form; everything else is returned as-is.
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    return s
