from typing import List, Literal

from pydantic import BaseModel, Field

FlightType = Literal["round_trip", "one_way"]
CabinClass = Literal["business", "economy", "basic_economy"]
Insurance = Literal["yes", "no"]


class FlightInfo(BaseModel):
    flight_number: str = Field(description="Flight number, such as 'HAT001'.")
    date: str = Field(
        description="The date for the flight in the format 'YYYY-MM-DD', such as '2024-05-01'."
    )


class Passenger(BaseModel):
    first_name: str = Field(description="Passenger's first name")
    last_name: str = Field(description="Passenger's last name")
    dob: str = Field(description="Date of birth in YYYY-MM-DD format")


class Payment(BaseModel):
    payment_id: str = Field(description="Unique identifier for the payment")
    amount: int = Field(description="Payment amount in dollars")


def book_reservation(user_id: str, origin: str, destination: str, flight_type: FlightType, cabin: CabinClass, flights: List[FlightInfo | dict], passengers: List[Passenger | dict], payment_methods: List[Payment | dict], total_baggages: int, nonfree_baggages: int, insurance: Insurance):
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
