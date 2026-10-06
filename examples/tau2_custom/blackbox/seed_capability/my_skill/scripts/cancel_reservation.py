def cancel_reservation(reservation_id: str):
    """
    Cancel the whole reservation.

    Args:
        reservation_id: The reservation ID, such as 'ZFA04Y'.

    Returns:
        The updated reservation.

    Raises:
        ValueError: If the reservation is not found.
    """
    return env_cancel_reservation(reservation_id=reservation_id)
