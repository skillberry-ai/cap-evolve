#!/usr/bin/env python3
"""reproduce.py for microcase ``netguard_duplicate_payment`` (#436).

Replays the two ``update_reservation_flights`` calls extracted VERBATIM from
``run3_task10_seed_t8_duplicate_payment.json`` (task 10, a real tau2-airline rollout:
"Database state does NOT match the expected final state... The divergence is an EXTRA
or DUPLICATED write... every successful update appends a charge to `payment_history`,
and re-issuing a corrected write does not undo the first one.") against the
CANDIDATE's own ``tools/tools.py``, directly — no LLM, no multi-turn episode.

What is verbatim: the two calls' ``reservation_id``/``cabin``/``flights``/``payment_id``
arguments, byte-for-byte from ``fixture/calls.json``. What is NOT in the rollout and is
therefore minimal scaffolding this case supplies: the static reference data
(flight prices/seat counts) the real tau2 default DB holds but the diagnosed rollout
never surfaces — chosen distinct-per-flight so a real payment total is nonzero on both
calls (uniform prices would make the second call's price delta zero for reasons that
have nothing to do with the guard under test, masking the defect instead of reproducing
it).

Requires the candidate's ``tools/tools.py`` to import ``tau2.domains.airline.data_model``
and ``tau2.environment.toolkit`` — the real tau2-bench package, or (as in
core/tests/test_microcase.py) a stand-in on ``PYTHONPATH`` with the same names. Reports
``{"status": "error", ...}`` and exits 2 if neither is importable — an environment gap,
not a candidate defect.
"""

import argparse
import importlib.util
import json
import sys
from pathlib import Path

# Real, distinct per-flight business-cabin prices — see docstring above.
_PRICES = {"HAT190": 120, "HAT047": 80, "HAT021": 90, "HAT279": 110,
           "HAT112": 130, "HAT089": 95}


def _load_candidate_tools(candidate_dir: Path):
    sys.path.insert(0, str(candidate_dir))
    spec = importlib.util.spec_from_file_location(
        "candidate_tools", candidate_dir / "tools" / "tools.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--project", required=True)
    ap.add_argument("--fixture", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    calls = json.loads((Path(args.fixture) / "calls.json").read_text())["calls"]
    update_calls = [c for c in calls if c["name"] == "update_reservation_flights"]

    try:
        tools_mod = _load_candidate_tools(Path(args.candidate))
        from tau2.domains.airline.data_model import (
            Flight, FlightDateStatusAvailable, FlightDB, PaymentMethod, Reservation,
        )
    except Exception as exc:  # tau2-bench (or the test's stand-in) is not on the path
        Path(args.out).write_text(json.dumps(
            {"status": "error", "reason": f"tau2 data model not importable: {exc}"}))
        return 2

    reservation_id = update_calls[0]["arguments"]["reservation_id"]
    payment_id = update_calls[0]["arguments"]["payment_id"]
    user_id = "liam_khan_2521"

    flights = {}
    for call in update_calls:
        for leg in call["arguments"]["flights"]:
            fn, date = leg["flight_number"], leg["date"]
            price = _PRICES[fn]
            dates = flights.setdefault(
                fn, Flight(flight_number=fn, origin=leg["origin"],
                           destination=leg["destination"], dates={})).dates
            dates[date] = FlightDateStatusAvailable(
                available_seats={"business": 5, "economy": 5},
                prices={"business": price, "economy": price // 2})

    reservation = Reservation(reservation_id=reservation_id, user_id=user_id,
                               cabin="economy", flights=[], payment_history=[],
                               passengers=["p1"])
    user_obj = type("User", (), {})()
    user_obj.user_id = user_id
    user_obj.payment_methods = {
        payment_id: PaymentMethod(payment_id=payment_id, source="credit_card"),
    }
    db = FlightDB(flights=flights, users={user_id: user_obj},
                  reservations={reservation_id: reservation})

    airline = tools_mod.AirlineTools(db)
    for call in update_calls:
        a = call["arguments"]
        airline.update_reservation_flights(
            reservation_id=a["reservation_id"], cabin=a["cabin"],
            flights=a["flights"], payment_id=a["payment_id"])

    result = {
        "status": "ok",
        "payment_history_len": len(reservation.payment_history),
        "payment_amounts": [p.amount for p in reservation.payment_history],
    }
    Path(args.out).write_text(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
