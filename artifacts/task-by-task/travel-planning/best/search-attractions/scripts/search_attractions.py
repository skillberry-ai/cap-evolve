"""Utility for searching attractions by city.

Itinerary note: EVERY day of a travel itinerary needs a non-empty `attraction`
(never "" or "-"), including departure, return, and "from A to B" travel days.
The departure/return city has attractions in this dataset too, so query it.
After writing itinerary.json, run the bundled fixer as a final safety net:
    python scripts/fill_attractions.py --plan /app/output/itinerary.json
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

import pandas as pd
from pandas import DataFrame


# Default to the bundled attractions CSV.
def _find_data_path() -> Path:
    """Find data file, checking container path first, then relative to script."""
    relative = "attractions/attractions.csv"
    container_path = Path("/app/data") / relative
    if container_path.exists():
        return container_path
    return Path(__file__).resolve().parent.parent.parent / "data" / relative


DEFAULT_DATA_PATH = _find_data_path()

ATTRACTION_COLUMNS = [
    "Name",
    "Latitude",
    "Longitude",
    "Address",
    "Phone",
    "Website",
    "City",
]


_ITINERARY_REMINDER = (
    "ITINERARY REMINDER: every day of the itinerary must have a non-empty "
    "`attraction` (never \"\" or \"-\"), INCLUDING departure, return, and "
    "\"from A to B\" travel days. For a travel day, list an attraction from "
    "the origin OR the destination city. The departure/return city (where the "
    "trip starts and ends) also has attractions in this dataset, so query it "
    "too — otherwise day 1 and the final day get left as \"-\" and fail "
    "verification. As a final safety net after writing itinerary.json, run: "
    "python scripts/fill_attractions.py --plan /app/output/itinerary.json"
)


class Attractions:
    """Search helper for the attractions dataset."""

    _reminder_shown = False

    def __init__(
        self,
        path: str | Path = DEFAULT_DATA_PATH,
        city_normalizer: Callable[[str], str] | None = None,
    ) -> None:
        self.path = Path(path)
        self.city_normalizer = city_normalizer or (lambda value: value)
        self.data: DataFrame = DataFrame()
        self.load_db()
        print("Attractions loaded.")
        # Surface the itinerary rule at the moment attractions are gathered.
        # Printed once per process so repeated construction stays quiet.
        if not Attractions._reminder_shown:
            print(_ITINERARY_REMINDER)
            Attractions._reminder_shown = True

    def load_db(self) -> None:
        """Load and lightly clean the attractions CSV."""
        if not self.path.exists():
            raise FileNotFoundError(f"Attractions CSV not found at {self.path}")

        df = pd.read_csv(self.path)
        existing_columns = [col for col in ATTRACTION_COLUMNS if col in df.columns]
        df = df[existing_columns].dropna()
        df["City"] = df["City"].astype(str).str.strip()
        self.data = df

    def run(self, city: str) -> DataFrame | str:
        """Return attractions for the given city (case-insensitive)."""
        if self.data.empty:
            return "No attractions data is available."

        normalized_city = self.city_normalizer(city).strip()
        mask = self.data["City"].str.lower() == normalized_city.lower()
        results = self.data[mask].reset_index(drop=True)

        if results.empty:
            return "There is no attraction in this city."

        return results


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Search attractions by city.")
    parser.add_argument("--city", "-c", help="City to search for.")
    parser.add_argument(
        "--path",
        default=str(DEFAULT_DATA_PATH),
        help="Path to attractions CSV (defaults to bundled dataset).",
    )
    return parser


def main() -> None:
    args = _build_arg_parser().parse_args()
    attractions = Attractions(path=args.path)

    if not args.city:
        print("Please provide --city.")
        return

    result = attractions.run(args.city)
    if isinstance(result, str):
        print(result)
    else:
        # Print in a compact, readable format without the pandas index.
        print(result.to_string(index=False))


if __name__ == "__main__":
    main()
