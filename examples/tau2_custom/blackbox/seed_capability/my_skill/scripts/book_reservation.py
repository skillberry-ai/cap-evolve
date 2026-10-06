def book_reservation(user_id: str, origin: str, destination: str, flight_type: str, cabin: str, flights: list, passengers: list, payment_methods: list, total_baggages: int, nonfree_baggages: int, insurance: str):
    """
    Book a reservation.

    Args:
        user_id: The ID of the user to book the reservation such as 'sara_doe_496'`.
        origin: The IATA code for the origin city such as 'SFO'.
        destination: The IATA code for the destination city such as 'JFK'.
        flight_type: The type of flight such as 'one_way' or 'round_trip'.
        cabin: The cabin class such as 'basic_economy', 'economy', or 'business'.
        flights: An array of objects containing details about each piece of flight.
        passengers: An array of objects containing details about each passenger.
        payment_methods: An array of objects containing details about each payment method.
        total_baggages: The total number of baggage items to book the reservation.
        nonfree_baggages: The number of non-free baggage items to book the reservation.
        insurance: Whether the reservation has insurance.
    """
    return env_book_reservation(user_id=user_id, origin=origin, destination=destination, flight_type=flight_type, cabin=cabin, flights=flights, passengers=passengers, payment_methods=payment_methods, total_baggages=total_baggages, nonfree_baggages=nonfree_baggages, insurance=insurance)
