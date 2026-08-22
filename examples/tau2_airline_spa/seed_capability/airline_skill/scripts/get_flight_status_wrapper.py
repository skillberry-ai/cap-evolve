"""Baseline wrapper tool for the `get_flight_status` primitive.

Part of `airline_skill`. Delegates to the frozen primitive tool `get_flight_status`.
The optimizer may add guard/aggregation logic here; any helper it introduces
must be nested INSIDE the function below and prefixed with '_'.
"""


def get_flight_status_wrapper(flight_number: str, date: str):
    """
    Get the status of a flight.

    Args:
        flight_number (str): The flight number.
        date (str): The date of the flight.

    Returns:
        The status of the flight.

    Raises:
        ValueError: If the flight is not found.

    """
    return get_flight_status(flight_number=flight_number, date=date)
