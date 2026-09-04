"""Minimal stand-in for tau2's airline data model — plain attribute containers, no
pydantic, covering only the fields ``AirlineTools.update_reservation_flights`` and
``_payment_for_update`` touch. NOT a real tau2 install; see
core/tests/test_microcase.py for why.
"""

from __future__ import annotations

CabinClass = str
AirportCode = str


class FlightInfo:
    def __init__(self, flight_number: str, origin: str = "", destination: str = "",
                 date: str = "") -> None:
        self.flight_number = flight_number
        self.origin = origin
        self.destination = destination
        self.date = date


class ReservationFlight:
    def __init__(self, flight_number: str, date: str, price: int,
                 origin: str, destination: str) -> None:
        self.flight_number = flight_number
        self.date = date
        self.price = price
        self.origin = origin
        self.destination = destination


class FlightDateStatusAvailable:
    def __init__(self, available_seats: dict, prices: dict) -> None:
        self.available_seats = available_seats
        self.prices = prices


FlightDateStatus = FlightDateStatusAvailable


class Flight:
    def __init__(self, flight_number: str, origin: str, destination: str,
                 dates: dict) -> None:
        self.flight_number = flight_number
        self.origin = origin
        self.destination = destination
        self.dates = dates


class Payment:
    def __init__(self, payment_id: str, amount: int) -> None:
        self.payment_id = payment_id
        self.amount = amount


class PaymentMethod:
    def __init__(self, payment_id: str, source: str, amount: int = 0) -> None:
        self.payment_id = payment_id
        self.source = source
        self.amount = amount


class Reservation:
    def __init__(self, reservation_id: str, user_id: str, cabin: str,
                 flights: list, payment_history: list, passengers: list) -> None:
        self.reservation_id = reservation_id
        self.user_id = user_id
        self.cabin = cabin
        self.flights = flights
        self.payment_history = payment_history
        self.passengers = passengers


class User:
    def __init__(self, user_id: str, payment_methods: dict) -> None:
        self.user_id = user_id
        self.payment_methods = payment_methods


class FlightDB:
    def __init__(self, flights: dict, users: dict, reservations: dict) -> None:
        self.flights = flights
        self.users = users
        self.reservations = reservations


# Unused by update_reservation_flights but imported by the real tools.py module.
class AirportInfo: ...
class Certificate: ...
class DirectFlight: ...
class Insurance: ...
class Passenger: ...
class FlightType: ...
