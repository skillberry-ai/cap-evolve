"""Excerpt of the run_20261008_150326 AirlineTools (verbatim method bodies for the kept tools)."""
from tau2.environment.toolkit import ToolType, is_tool


class AirlineTools:
    @is_tool(ToolType.READ)
    def get_reservation_details(self, reservation_id: str) -> Reservation:
        """
        Get the details of a reservation.

        Args:
            reservation_id: The reservation ID, such as '8JX2WO'.

        Returns:
            The reservation details.

        Raises:
            ValueError: If the reservation is not found.
        """
        return self._get_reservation(reservation_id)

    @is_tool(ToolType.WRITE)
    def update_reservation_baggages(
        self,
        reservation_id: str,
        total_baggages: int,
        nonfree_baggages: int,
        payment_id: str,
    ) -> Reservation:
        """
        Update the baggage information of a reservation.

        Args:
            reservation_id: The reservation ID, such as 'ZFA04Y'
            total_baggages: The updated total number of baggage items included in the reservation.
            nonfree_baggages: The updated number of non-free baggage items included in the reservation.
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
        reservation = self._get_reservation(reservation_id)
        user = self._get_user(reservation.user_id)

        # Calculate price
        total_price = 50 * max(0, nonfree_baggages - reservation.nonfree_baggages)

        # Create payment
        payment = self._payment_for_update(user, payment_id, total_price)
        if payment is not None:
            reservation.payment_history.append(payment)

        # Update reservation
        reservation.total_baggages = total_baggages
        reservation.nonfree_baggages = nonfree_baggages

        return reservation

    @is_tool(ToolType.WRITE)
    def update_reservation_flights(
        self,
        reservation_id: str,
        cabin: CabinClass,
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
            ValueError: If a basic-economy reservation's flight segments would change.
        """
        if all(isinstance(flight, dict) for flight in flights):
            flights = [FlightInfo(**flight) for flight in flights]
        reservation = self._get_reservation(reservation_id)
        user = self._get_user(reservation.user_id)

        # policy.md's "Change flights" section: "Basic economy flights cannot be
        # modified." Cabin upgrades FROM basic economy are still allowed (policy's
        # "Change cabin" section), so this only blocks an attempt to change the
        # actual flight segments while remaining in basic economy.
        if reservation.cabin == "basic_economy" and cabin == "basic_economy":
            old_segments = {(f.flight_number, f.date) for f in reservation.flights}
            new_segments = {(f.flight_number, f.date) for f in flights}
            if old_segments != new_segments:
                raise ValueError(
                    "Basic economy reservations cannot change flight segments "
                    "(policy: 'Basic economy flights cannot be modified')."
                )

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

        # policy.md's "Change flights" section: a modification "can be modified
        # without changing the origin, destination, and trip type" — but the API
        # previously accepted a changed origin/destination silently (confirmed in
        # a real run: an agent used this tool to swap a reservation's destination
        # airport instead of cancelling and rebooking). Gold expects cancel+rebook
        # for that case, so refuse here rather than silently writing the wrong
        # reservation shape. A round trip's LAST leg lands back at the origin, not
        # at reservation.destination, so checking membership (the away-city must
        # appear as some leg's origin/destination) rather than exact-last-leg-match
        # is what stays correct for round trips too.
        if reservation_flights:
            airports_touched = {f.origin for f in reservation_flights} | {
                f.destination for f in reservation_flights
            }
            if (
                reservation_flights[0].origin != reservation.origin
                or reservation.destination not in airports_touched
            ):
                raise ValueError(
                    "update_reservation_flights cannot change a reservation's "
                    "overall origin or destination — cancel the existing "
                    "reservation and book a new one instead."
                )

        # Deduct amount already paid for reservation
        total_price -= sum(flight.price for flight in reservation.flights) * len(
            reservation.passengers
        )

        # Create payment
        payment = self._payment_for_update(user, payment_id, total_price)
        if payment is not None:
            reservation.payment_history.append(payment)

        # Update reservation
        reservation.flights = reservation_flights
        reservation.cabin = cabin  # This was missing from original TauBench

        return reservation

    @is_tool(ToolType.WRITE)
    def update_reservation_cabin(
        self,
        reservation_id: str,
        cabin: CabinClass,
        payment_id: str,
    ) -> Reservation:
        """
        Change ONLY the cabin class of a reservation, keeping the same flights, and
        automatically recompute and apply any free-baggage-allowance change in the
        SAME call. Use this instead of update_reservation_flights followed by a
        separate update_reservation_baggages call when the request is a pure cabin
        change (no flight/date change) — a real run showed agents applying the
        baggage recompute correctly for the first reservation in a multi-reservation
        request, then forgetting it for the rest; this closes that gap structurally
        by removing the need for a second call at all.

        Args:
            reservation_id: The reservation ID, such as 'ZFA04Y'.
            cabin: The new cabin class for the ENTIRE reservation.
            payment_id: The payment id stored in user profile, used for any flight
                price difference AND any resulting baggage fee.

        Returns:
            The updated reservation.

        Raises:
            ValueError: If the reservation is not found.
            ValueError: If the user is not found.
            ValueError: If the payment method is not found.
            ValueError: If the gift card balance is not enough.
        """
        reservation = self._get_reservation(reservation_id)
        existing_flights = [
            {"flight_number": f.flight_number, "date": f.date} for f in reservation.flights
        ]
        updated = self.update_reservation_flights(
            reservation_id=reservation_id,
            cabin=cabin,
            flights=existing_flights,
            payment_id=payment_id,
        )

        # Recompute the free-baggage allowance for the NEW cabin + member level.
        # Only ever INCREASES nonfree_baggages (charges for bags that lost their free
        # status) — per policy.md, a bigger allowance after the change never refunds
        # bags already paid for.
        user = self._get_user(updated.user_id)
        free_per_passenger = _FREE_BAGGAGE_ALLOWANCE[user.membership][cabin]
        new_free_allowance = free_per_passenger * len(updated.passengers)
        min_nonfree = max(0, updated.total_baggages - new_free_allowance)
        if min_nonfree > updated.nonfree_baggages:
            updated = self.update_reservation_baggages(
                reservation_id=reservation_id,
                total_baggages=updated.total_baggages,
                nonfree_baggages=min_nonfree,
                payment_id=payment_id,
            )
        return updated

