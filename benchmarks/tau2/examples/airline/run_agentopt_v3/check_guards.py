"""Self-check for the c2_toolguard tool guards: each guard must FIRE on a real
DB case that the seed silently accepted, and must NOT fire on the legitimate one."""
import importlib.util, sys, pathlib
sys.path.insert(0, str(pathlib.Path('.capevolve/project/adapters').resolve()))
p = sys.argv[1]
spec = importlib.util.spec_from_file_location("cand_tools", p)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
from tau2.domains.airline.data_model import FlightDB
from tau2.domains.airline.utils import AIRLINE_DB_PATH
T = m.AirlineTools(FlightDB.load(AIRLINE_DB_PATH))

def raises(fn, *a, **k):
    try:
        fn(*a, **k); return None
    except ValueError as e:
        return str(e)

# A: 3RK2T9 created 2024-05-02, basic_economy, insurance no -> must be refused
e = raises(T.cancel_reservation, "3RK2T9")
assert e and "not eligible" in e, f"guard A did not fire: {e}"
print("A ok:", e[:110])

# A': a reservation with insurance yes must still be cancellable (no false refusal)
ins_ok = [r for r in T.db.reservations.values()
          if r.insurance == "yes" and all(f.date >= "2024-05-15" for f in r.flights)]
assert ins_ok, "no insured future reservation in DB to test against"
assert raises(T.cancel_reservation, ins_ok[0].reservation_id) is None, "guard A false positive on insured res"
print("A' ok: insured reservation still cancellable")

# B: reducing bags on a reservation that has some must be refused
withbags = [r for r in T.db.reservations.values() if r.total_baggages > 0]
r = withbags[0]
pid = next(iter(T._get_user(r.user_id).payment_methods))
e = raises(T.update_reservation_baggages, r.reservation_id, r.total_baggages - 1, r.nonfree_baggages, pid)
assert e and "Cannot reduce checked bags" in e, f"guard B did not fire: {e}"
print("B ok:", e[:90])

# C: changing flights of a basic-economy reservation must be refused
be = [r for r in T.db.reservations.values() if r.cabin == "basic_economy" and len(r.flights) >= 1][0]
other = next(fn for fn in T.db.flights if fn != be.flights[0].flight_number)
e = raises(T.update_reservation_flights, be.reservation_id, "basic_economy",
           [{"flight_number": other, "date": be.flights[0].date}], next(iter(T._get_user(be.user_id).payment_methods)))
assert e and "basic economy flights cannot be modified" in e, f"guard C did not fire: {e}"
print("C ok:", e[:90])
print("ALL GUARD CHECKS PASS")
