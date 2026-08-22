"""Baseline wrapper tool for the `search_onestop_flight` primitive.

Part of `airline_skill`. Delegates to the frozen primitive tool `search_onestop_flight`.
The optimizer may add guard/aggregation logic here; any helper it introduces
must be nested INSIDE the function below and prefixed with '_'.
"""


def search_onestop_flight_wrapper(origin: str, destination: str, date: str):
    """
    Search for one-stop flights between two cities on a specific date.

    Args:
        origin (str): The origin city airport in three letters, such as 'JFK'.
        destination (str): The destination city airport in three letters, such as 'LAX'.
        date (str): The date of the flight in the format 'YYYY-MM-DD', such as '2024-05-01'.

    Returns:
        A list of pairs of DirectFlight objects.

    """
    return search_onestop_flight(origin=origin, destination=destination, date=date)
