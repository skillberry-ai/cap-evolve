from typing import List

from pydantic import BaseModel, Field

class Passenger(BaseModel):
    first_name: str = Field(description="Passenger's first name")
    last_name: str = Field(description="Passenger's last name")
    dob: str = Field(description="Date of birth in YYYY-MM-DD format")


def update_reservation_passengers(reservation_id: str, passengers: List[Passenger | dict]):
    """
    Update the passenger information of a reservation.

    Args:
        reservation_id: The reservation ID, such as 'ZFA04Y'.
        passengers: An array of objects containing details about each passenger.

    Returns:
        The updated reservation.

    Raises:
        ValueError: If the reservation is not found.
        ValueError: If the number of passengers does not match.
    """
    return env_update_reservation_passengers(reservation_id=reservation_id, passengers=passengers)
