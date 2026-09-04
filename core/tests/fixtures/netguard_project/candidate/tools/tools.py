"""Toolkit for the airline reservation system.

This is the CANDIDATE variant for the micro-test example (#436): identical to the seed
except for the merge-guard applied verbatim from the real run's accepted mechanism
(``i1_tools_netguard/diff.patch``) — a revised ``update_reservation_flights`` call on a
reservation already updated once in this conversation nets its delta into the prior
``payment_history`` entry instead of appending a second one.
"""

from copy import deepcopy
from typing import List, Optional

from tau2.domains.airline.data_model import (
    Flight,
    FlightDateStatusAvailable,
    FlightDB,
    FlightInfo,
    Payment,
    Reservation,
    ReservationFlight,
    User,
)
from tau2.environment.toolkit import ToolKitBase, ToolType, is_tool


class AirlineTools(ToolKitBase):
    """All the tools for the airline domain."""

    db: FlightDB

    def __init__(self, db: FlightDB) -> None:
        super().__init__(db)
        # Tracks, per reservation_id, the (payment_id, Payment) most recently
        # appended by update_reservation_flights/update_reservation_baggages,
        # so a later call revising the SAME reservation in this conversation
        # nets its delta into that entry instead of appending a second one.
        self._last_update_payment: dict[str, tuple[str, Payment]] = {}

    def _apply_update_payment(
        self, reservation: Reservation, payment_id: str, payment: Optional[Payment]
    ) -> None:
        """Append a delta payment for a reservation update, merging it into the
        prior entry from an earlier update call in this conversation (same
        reservation, same payment method, nothing else appended since) so the
        ledger reflects the FINAL agreed price with one entry instead of one
        per revision.
        """
        reservation_id = reservation.reservation_id
        prior = self._last_update_payment.get(reservation_id)
        merge_target = (
            prior[1]
            if prior is not None
            and prior[0] == payment_id
            and reservation.payment_history
            and reservation.payment_history[-1] is prior[1]
            else None
        )
        if payment is None:
            return
        if merge_target is not None:
            merged_amount = merge_target.amount + payment.amount
            if merged_amount == 0:
                reservation.payment_history.remove(merge_target)
                self._last_update_payment.pop(reservation_id, None)
            else:
                merge_target.amount = merged_amount
        else:
            reservation.payment_history.append(payment)
            self._last_update_payment[reservation_id] = (payment_id, payment)

    def _get_user(self, user_id: str) -> User:
        if user_id not in self.db.users:
            raise ValueError(f"User {user_id} not found")
        return self.db.users[user_id]

    def _get_reservation(self, reservation_id: str) -> Reservation:
        if reservation_id not in self.db.reservations:
            raise ValueError(f"Reservation {reservation_id} not found")
        return self.db.reservations[reservation_id]

    def _get_flight(self, flight_number: str) -> Flight:
        if flight_number not in self.db.flights:
            raise ValueError(f"Flight {flight_number} not found")
        return self.db.flights[flight_number]

    def _get_flight_instance(self, flight_number: str, date: str) -> FlightDateStatusAvailable:
        flight = self._get_flight(flight_number)
        if date not in flight.dates:
            raise ValueError(f"Flight {flight_number} not found on date {date}")
        return flight.dates[date]

    def _payment_for_update(
        self, user: User, payment_id: str, total_price: int
    ) -> Optional[Payment]:
        if payment_id not in user.payment_methods:
            raise ValueError("Payment method not found")
        payment_method = user.payment_methods[payment_id]
        if payment_method.source == "certificate":
            raise ValueError("Certificate cannot be used to update reservation")
        elif payment_method.source == "gift_card" and payment_method.amount < total_price:
            raise ValueError("Gift card balance is not enough")

        if payment_method.source == "gift_card":
            payment_method.amount -= total_price

        payment = None
        if total_price != 0:
            payment = Payment(payment_id=payment_id, amount=total_price)
        return payment

    @is_tool(ToolType.WRITE)
    def update_reservation_flights(
        self,
        reservation_id: str,
        cabin: str,
        flights: List[FlightInfo | dict],
        payment_id: str,
    ) -> Reservation:
        """
        Update the flight information of a reservation.

        Args:
            reservation_id: The reservation ID, such as 'ZFA04Y'.
            cabin: The cabin class of the reservation
            flights: An array of objects containing details about each piece of flight in the ENTIRE new reservation. Even if the a flight segment is not changed, it should still be included in the array.
            payment_id: The payment id stored in user profile, such as 'credit_card_7815826', 'gift_card_7815826', 'certificate_7815826'.

        Returns:
            The updated reservation.

        Raises:
            ValueError: If the reservation is not found.
            ValueError: If the user is not found.
            ValueError: If the payment method is not found.
            ValueError: If the certificate cannot be used to update reservation.
            ValueError: If the gift card balance is not enough.
        """
        if all(isinstance(flight, dict) for flight in flights):
            flights = [FlightInfo(**flight) for flight in flights]
        reservation = self._get_reservation(reservation_id)
        user = self._get_user(reservation.user_id)

        # update flights and calculate price
        total_price = 0
        reservation_flights = []
        for flight_info in flights:
            # if existing flight, keep it
            matching_reservation_flight = next(
                (
                    reservation_flight
                    for reservation_flight in reservation.flights
                    if reservation_flight.flight_number == flight_info.flight_number
                    and reservation_flight.date == flight_info.date
                    and cabin == reservation.cabin
                ),
                None,
            )
            if matching_reservation_flight:
                total_price += matching_reservation_flight.price * len(
                    reservation.passengers
                )
                reservation_flights.append(matching_reservation_flight)
                continue

            # If new flight:
            flight = self._get_flight(flight_info.flight_number)
            # Check flight availability
            flight_date_data = self._get_flight_instance(
                flight_number=flight_info.flight_number,
                date=flight_info.date,
            )
            if not isinstance(flight_date_data, FlightDateStatusAvailable):
                raise ValueError(
                    f"Flight {flight_info.flight_number} not available on date {flight_info.date}"
                )

            # Check seat availability
            if flight_date_data.available_seats[cabin] < len(reservation.passengers):
                raise ValueError(
                    f"Not enough seats on flight {flight_info.flight_number}"
                )

            # Calculate price and add to reservation
            reservation_flight = ReservationFlight(
                flight_number=flight_info.flight_number,
                date=flight_info.date,
                price=flight_date_data.prices[cabin],
                origin=flight.origin,
                destination=flight.destination,
            )
            total_price += reservation_flight.price * len(reservation.passengers)
            reservation_flights.append(reservation_flight)

        # Deduct amount already paid for reservation
        total_price -= sum(flight.price for flight in reservation.flights) * len(
            reservation.passengers
        )

        # Create payment
        payment = self._payment_for_update(user, payment_id, total_price)
        self._apply_update_payment(reservation, payment_id, payment)

        # Update reservation
        reservation.flights = reservation_flights
        reservation.cabin = cabin

        return reservation
