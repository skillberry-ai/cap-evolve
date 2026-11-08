def get_flight_status(flight_number: str, date: str):
    """
    Get the status of a flight.

    Args:
        flight_number: The flight number.
        date: The date of the flight.

    Returns:
        The status of the flight.

    Raises:
        ValueError: If the flight is not found.
    """
    return env_get_flight_status(flight_number=flight_number, date=date)
