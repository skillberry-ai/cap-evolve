def search_direct_flight(origin: str, destination: str, date: str):
    """
    Search for direct flights between two cities on a specific date.

    Args:
        origin: The origin city airport in three letters, such as 'JFK'.
        destination: The destination city airport in three letters, such as 'LAX'.
        date: The date of the flight in the format 'YYYY-MM-DD', such as '2024-01-01'.

    Returns:
        The direct flights between the two cities on the specific date.
    """
    return env_search_direct_flight(origin=origin, destination=destination, date=date)
