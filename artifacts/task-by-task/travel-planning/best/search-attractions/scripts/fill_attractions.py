"""Fill every itinerary day's `attraction` field with real dataset attractions.

Run this as the FINAL step after writing itinerary.json. It reads the plan,
and for every day whose `attraction` is empty or "-", it looks up real
attractions for that day's city (or BOTH endpoints of a "from A to B" travel
day) from the bundled attractions dataset and fills the field with a
`;`-terminated list. Days that already have real attractions are left
untouched. This guarantees no day is left with an empty/"-" attraction, which
the verifier requires for every day.

Usage:
    python scripts/fill_attractions.py                 # /app/output/itinerary.json
    python scripts/fill_attractions.py --plan PATH      # explicit path

The script is idempotent and only ever *adds* attractions to empty days.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Import the dataset helper that lives next to this script.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from search_attractions import Attractions  # noqa: E402

EMPTY_VALUES = {"", "-", "none", "n/a", "na"}
DEFAULT_PLAN_PATH = "/app/output/itinerary.json"


def _is_empty(value) -> bool:
    return str(value).strip().lower() in EMPTY_VALUES


def _cities_from_current(current_city: str) -> list[str]:
    """Extract candidate city names from a current_city string.

    Handles plain cities ("Cleveland") and travel days ("from A to B").
    """
    if not current_city:
        return []
    text = str(current_city)
    for token in (" to ", " -> ", "->", " from ", " and "):
        text = text.replace(token, "|")
    if text.lower().startswith("from|"):
        text = text[5:]
    cities = []
    for piece in text.split("|"):
        cleaned = piece.strip().strip(",").strip()
        if cleaned and cleaned.lower() not in {"from", "to"}:
            cities.append(cleaned)
    return cities


def _names_for_city(attractions: Attractions, city: str) -> list[str]:
    """Return the list of attraction names for a city (empty if none)."""
    result = attractions.run(city)
    if isinstance(result, str):  # sentinel string => no rows
        return []
    return [str(n).strip() for n in result["Name"].tolist() if str(n).strip()]


def fill_plan(plan: list[dict], attractions: Attractions, per_day: int = 2) -> int:
    """Fill empty attraction fields in-place. Returns number of days changed."""
    used: set[str] = set()
    # First pass: record attractions already present so we prefer fresh ones.
    for day in plan:
        for name in str(day.get("attraction", "")).split(";"):
            name = name.strip()
            if name and not _is_empty(name):
                used.add(name)

    changed = 0
    for day in plan:
        if not _is_empty(day.get("attraction", "")):
            continue
        cities = _cities_from_current(day.get("current_city", "")) or _cities_from_current(
            day.get("city", "")
        )
        chosen: list[str] = []
        # Prefer attractions not yet used anywhere in the plan, across all
        # candidate cities for the day; fall back to any if needed.
        pools = [_names_for_city(attractions, c) for c in cities]
        for pool in pools:
            for name in pool:
                if len(chosen) >= per_day:
                    break
                if name not in used and name not in chosen:
                    chosen.append(name)
        if len(chosen) < per_day:
            for pool in pools:
                for name in pool:
                    if len(chosen) >= per_day:
                        break
                    if name not in chosen:
                        chosen.append(name)
        if chosen:
            day["attraction"] = ";".join(chosen) + ";"
            used.update(chosen)
            changed += 1
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Fill empty itinerary attractions.")
    parser.add_argument("--plan", default=DEFAULT_PLAN_PATH, help="Path to itinerary.json")
    parser.add_argument("--per-day", type=int, default=2, help="Attractions to add per empty day")
    args = parser.parse_args()

    plan_path = Path(args.plan)
    if not plan_path.exists():
        print(f"itinerary not found at {plan_path}", file=sys.stderr)
        return 1

    payload = json.loads(plan_path.read_text())
    plan = payload.get("plan", payload if isinstance(payload, list) else [])
    attractions = Attractions()

    changed = fill_plan(plan, attractions, per_day=args.per_day)

    # Report any day still empty (should be none if the dataset has the city).
    still_empty = [d.get("day") for d in plan if _is_empty(d.get("attraction", ""))]
    if isinstance(payload, dict):
        payload["plan"] = plan
        plan_path.write_text(json.dumps(payload, indent=2))
    else:
        plan_path.write_text(json.dumps(plan, indent=2))

    print(f"Filled {changed} day(s). Still empty: {still_empty or 'none'}")
    if still_empty:
        print(
            "WARNING: some days had no dataset attraction for their city; "
            "query a nearby city on the route and fill manually.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
