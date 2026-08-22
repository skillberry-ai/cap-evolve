"""Baseline wrapper tool for the `list_all_airports` primitive.

Part of `airline_skill`. Delegates to the frozen primitive tool `list_all_airports`.
The optimizer may add guard/aggregation logic here; any helper it introduces
must be nested INSIDE the function below and prefixed with '_'.
"""


def list_all_airports_wrapper():
    """
    Returns a list of all available airports.

    Returns:
        A dictionary mapping IATA codes to AirportInfo objects.

    """
    return list_all_airports()
