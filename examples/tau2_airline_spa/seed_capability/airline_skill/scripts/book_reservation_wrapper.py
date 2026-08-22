"""Baseline wrapper tool for the `book_reservation` primitive.

Part of `airline_skill`. Delegates to the frozen primitive tool `book_reservation`.
The optimizer may add guard/aggregation logic here; any helper it introduces
must be nested INSIDE the function below and prefixed with '_'.
"""


def book_reservation_wrapper(
    user_id: str,
    origin: str,
    destination: str,
    flight_type: str,
    cabin: str,
    flights: str,
    passengers: str,
    payment_methods: str,
    total_baggages: int,
    nonfree_baggages: int,
    insurance: str,
):
    """
    Creates a flight reservation for a user with specified travel details.

    Parameters:
        user_id (str): Identifier of the user making the reservation.
        origin (str): Departure location.
        destination (str): Arrival location.
        flight_type (str): Type of flight (e.g., one-way, round-trip).
        cabin (str): Cabin class (e.g., economy, business).
        flights (str): Flight identifiers or details.
        passengers (str): Passenger information.
        payment_methods (str): Selected payment method(s).
        total_baggages (int): Total number of baggages.
        nonfree_baggages (int): Number of baggages requiring payment.
        insurance (str): Insurance option selected.

    Returns:
        dict: Reservation confirmation details.
    """
    return book_reservation(
        user_id=user_id,
        origin=origin,
        destination=destination,
        flight_type=flight_type,
        cabin=cabin,
        flights=flights,
        passengers=passengers,
        payment_methods=payment_methods,
        total_baggages=total_baggages,
        nonfree_baggages=nonfree_baggages,
        insurance=insurance,
    )
