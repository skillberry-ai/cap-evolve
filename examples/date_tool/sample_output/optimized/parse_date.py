"""Normalize a date string to ISO (YYYY-MM-DD). SEED: incomplete on purpose."""
import re


def parse_date(s: str) -> str:
    s = s.strip()
    
    # Month name mappings
    month_full = {
        'january': '01', 'february': '02', 'march': '03', 'april': '04',
        'may': '05', 'june': '06', 'july': '07', 'august': '08',
        'september': '09', 'october': '10', 'november': '11', 'december': '12'
    }
    month_abbr = {
        'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
        'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
        'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
    }
    
    # 1. ISO format with dashes (YYYY-MM-DD) - already correct
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    
    # 2. ISO format with slashes (YYYY/MM/DD) -> slash_iso
    match = re.fullmatch(r"(\d{4})/(\d{2})/(\d{2})", s)
    if match:
        year, month, day = match.groups()
        return f"{year}-{month}-{day}"
    
    # 3. ISO format with dots (YYYY.MM.DD) -> dotted
    match = re.fullmatch(r"(\d{4})\.(\d{2})\.(\d{2})", s)
    if match:
        year, month, day = match.groups()
        return f"{year}-{month}-{day}"
    
    # 4. US format with slashes (MM/DD/YYYY) -> us_slash
    match = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", s)
    if match:
        month, day, year = match.groups()
        return f"{year}-{month}-{day}"
    
    # 5. DMY format with dashes (DD-MM-YYYY) -> dmy_dash
    match = re.fullmatch(r"(\d{2})-(\d{2})-(\d{4})", s)
    if match:
        day, month, year = match.groups()
        return f"{year}-{month}-{day}"
    
    # 6. Long MDY format (Month DD, YYYY) -> long_mdy
    match = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})", s)
    if match:
        month_name, day, year = match.groups()
        month_lower = month_name.lower()
        if month_lower in month_full:
            month = month_full[month_lower]
            day = day.zfill(2)
            return f"{year}-{month}-{day}"
    
    # 7. Long DMY format (DD Month YYYY) -> long_dmy
    match = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", s)
    if match:
        day, month_name, year = match.groups()
        month_lower = month_name.lower()
        if month_lower in month_full:
            month = month_full[month_lower]
            day = day.zfill(2)
            return f"{year}-{month}-{day}"
    
    # 8. Abbreviated MDY format (Mon DD YYYY) -> abbr_mdy
    match = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2})\s+(\d{4})", s)
    if match:
        month_name, day, year = match.groups()
        month_lower = month_name.lower()
        if month_lower in month_abbr:
            month = month_abbr[month_lower]
            day = day.zfill(2)
            return f"{year}-{month}-{day}"
    
    # If no pattern matches, return as-is
    return s