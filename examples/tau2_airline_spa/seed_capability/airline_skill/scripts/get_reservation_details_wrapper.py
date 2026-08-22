"""Baseline wrapper tool for the `get_reservation_details` primitive.

Part of `airline_skill`. Delegates to the frozen primitive tool `get_reservation_details`.
The optimizer may add guard/aggregation logic here; any helper it introduces
must be nested INSIDE the function below and prefixed with '_'.
"""


def get_reservation_details_wrapper(reservation_id: str):
    """
    Get the details of a reservation.

    Args:
        reservation_id (str): The reservation ID, such as '8JX2WO'.

    Returns:
        The reservation details.

    Raises:
        ValueError: If the reservation is not found.
    """
    return get_reservation_details(reservation_id=reservation_id)
