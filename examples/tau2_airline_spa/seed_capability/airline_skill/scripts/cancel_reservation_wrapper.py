"""Baseline wrapper tool for the `cancel_reservation` primitive.

Part of `airline_skill`. Delegates to the frozen primitive tool `cancel_reservation`.
The optimizer may add guard/aggregation logic here; any helper it introduces
must be nested INSIDE the function below and prefixed with '_'.
"""


def cancel_reservation_wrapper(reservation_id: str):
    """
    Cancel the whole reservation.

    Args:
        reservation_id (str): The reservation ID, such as 'ZFA04Y'.

    Returns:
        The updated reservation.

    Raises:
        ValueError: If the reservation is not found.
    """
    return cancel_reservation(reservation_id=reservation_id)
