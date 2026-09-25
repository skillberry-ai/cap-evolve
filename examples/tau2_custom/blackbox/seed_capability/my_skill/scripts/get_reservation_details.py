def get_reservation_details(reservation_id: str):
    """
    Get the details of a reservation.

    Args:
        reservation_id: The reservation ID, such as '8JX2WO'.

    Returns:
        The reservation details.

    Raises:
        ValueError: If the reservation is not found.
    """
    return env_get_reservation_details(reservation_id=reservation_id)
