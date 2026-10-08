from typing import List, Literal

from pydantic import BaseModel, Field

CabinClass = Literal["business", "economy", "basic_economy"]


class FlightInfo(BaseModel):
    flight_number: str = Field(description="Flight number, such as 'HAT001'.")
    date: str = Field(
        description="The date for the flight in the format 'YYYY-MM-DD', such as '2024-05-01'."
    )


def update_reservation_flights(reservation_id: str, cabin: CabinClass, flights: List[FlightInfo | dict], payment_id: str):
    """
    Update the flight information of a reservation.


    Args:
        reservation_id: The reservation ID, such as 'ZFA04Y'.
        cabin: The cabin class of the reservation
        flights: An array of objects containing details about each piece of flight in the ENTIRE new reservation. Even if the a flight segment is not changed, it should still be included in the array.
        payment_id: The payment id stored in user profile, such as 'credit_card_7815826', 'gift_card_7815826', 'certificate_7815826'.

    Returns:
        The updated reservation.

    Raises:
        ValueError: If the reservation is not found.
        ValueError: If the user is not found.
        ValueError: If the payment method is not found.
        ValueError: If the certificate cannot be used to update reservation.
        ValueError: If the gift card balance is not enough.
    """
    return env_update_reservation_flights(reservation_id=reservation_id, cabin=cabin, flights=flights, payment_id=payment_id)
