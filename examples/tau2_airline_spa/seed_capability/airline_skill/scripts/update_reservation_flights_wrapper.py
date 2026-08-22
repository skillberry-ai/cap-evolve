"""Baseline wrapper tool for the `update_reservation_flights` primitive.

Part of `airline_skill`. Delegates to the frozen primitive tool `update_reservation_flights`.
The optimizer may add guard/aggregation logic here; any helper it introduces
must be nested INSIDE the function below and prefixed with '_'.
"""


def update_reservation_flights_wrapper(
    reservation_id: str,
    cabin: str,
    flights: str,
    payment_id: str,
):
    """
    Update the flight information of a reservation.

    Args:
        reservation_id (str): The reservation ID, such as 'ZFA04Y'.
        cabin (str): The cabin class of the reservation
        flights (str): An array of objects containing details about each piece of flight in the ENTIRE new reservation. Even if the a flight segment is not changed, it should still be included in the array.
        payment_id (str): The payment id stored in user profile, such as 'credit_card_7815826', 'gift_card_7815826', 'certificate_7815826'.

    Returns:
        The updated reservation.

    Raises:
        ValueError: If the reservation is not found.
        ValueError: If the user is not found.
        ValueError: If the payment method is not found.
        ValueError: If the certificate cannot be used to update reservation.
        ValueError: If the gift card balance is not enough.

    """
    return update_reservation_flights(
        reservation_id=reservation_id,
        cabin=cabin,
        flights=flights,
        payment_id=payment_id,
    )
