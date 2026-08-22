"""Baseline wrapper tool for the `search_direct_flight` primitive.

Part of `airline_skill`. Delegates to the frozen primitive tool `search_direct_flight`.
The optimizer may add guard/aggregation logic here; any helper it introduces
must be nested INSIDE the function below and prefixed with '_'.
"""


def search_direct_flight_wrapper(origin: str, destination: str, date: str):
    """
    Search for direct flights between two cities on a specific date.

    Args:
        origin (str): The origin city airport in three letters, such as 'JFK'.
        destination (str): The destination city airport in three letters, such as 'LAX'.
        date (str): The date of the flight in the format 'YYYY-MM-DD', such as '2024-01-01'.

    Returns:
        The direct flights between the two cities on the specific date.

    """
    return search_direct_flight(origin=origin, destination=destination, date=date)
