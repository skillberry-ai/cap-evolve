def search_onestop_flight(origin: str, destination: str, date: str):
    """
    Search for one-stop flights between two cities on a specific date.

    Args:
        origin: The origin city airport in three letters, such as 'JFK'.
        destination: The destination city airport in three letters, such as 'LAX'.
        date: The date of the flight in the format 'YYYY-MM-DD', such as '2024-05-01'.

    Returns:
        A list of pairs of DirectFlight objects.
    """
    return env_search_onestop_flight(origin=origin, destination=destination, date=date)
