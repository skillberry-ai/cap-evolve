---
name: search-attractions
description: Retrieve attractions (points of interest) by city from the bundled dataset. Use this skill when filling the attraction field for any day of a travel itinerary — including departure, return, and "from A to B" travel days, which also need a real attraction from the origin or destination (query the departure/return city too, never leave a day as "-").
---

# Search Attractions

Query attractions for a given city from the bundled dataset.

## Quick Start

Run the bundled script directly (recommended); do not reimplement the lookup.

```bash
python scripts/search_attractions.py --city "Cleveland"
```

Or import it:

```python
from search_attractions import Attractions

attractions = Attractions()
print(attractions.run("Cleveland"))
```

Matching is case-insensitive. If a city has no rows the helper returns the string
"There is no attraction in this city." — in that case query another city on that
day's route (see below) rather than leaving the field blank.

## Filling the attraction field in an itinerary

Every day of a travel itinerary must list at least one **real** attraction pulled
from this dataset. Never leave the `attraction` field empty and never set it to
`"-"` — a day with no attraction is treated as incomplete.

This applies to **every** day, including departure, return, and driving/travel
days. On a day that moves between cities (e.g. `current_city` is `"from A to B"`),
query attractions for the origin city **and** the destination city and list at
least one from either — both endpoints are valid places to sightsee that day.

Format the field as one or more attraction names separated by `;` and ending with
`;`, for example: `"Cleveland Metroparks Zoo;The Cleveland Museum of Art;"`.

## Required final step: auto-fill any missing attractions

After you write `itinerary.json`, ALWAYS run the bundled fixer once as your last
action. It scans every day, and for any day whose `attraction` is empty or `"-"`
(most often departure/return/driving days) it looks up real attractions for that
day's city — or **both** endpoints of a `"from A to B"` travel day — from the
dataset and fills the field with a `;`-terminated list. Days that already have
real attractions are left unchanged, so it is safe to run on a complete plan.

```bash
python scripts/fill_attractions.py --plan /app/output/itinerary.json
```

Do not reimplement this — run the script. It exits non-zero and prints a warning
only if some day's city has no attractions in the dataset; in that rare case,
query a nearby city on that day's route and fill the field yourself. A day left
with an empty or `"-"` attraction fails verification.
