"""Baseline wrapper tool for the `update_reservation_passengers` primitive.

Part of `airline_skill`. Delegates to the frozen primitive tool `update_reservation_passengers`.
The optimizer may add guard/aggregation logic here; any helper it introduces
must be nested INSIDE the function below and prefixed with '_'.
"""


def update_reservation_passengers_wrapper(reservation_id: str, passengers: str):
    """
    Update the passenger information of a reservation.

    Args:
        reservation_id (str): The reservation ID, such as 'ZFA04Y'.
        passengers (str): An array of objects containing details about each passenger.

    Returns:
        The updated reservation.

    Raises:
        ValueError: If the reservation is not found.
        ValueError: If the number of passengers does not match.

    """
    return update_reservation_passengers(
        reservation_id=reservation_id,
        passengers=passengers,
    )
