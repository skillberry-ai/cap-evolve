"""Airline tool definitions the optimizer may improve.

Each function below mirrors an existing airline tool; its DOCSTRING is the
tool's documentation that the agent reads to select it and fill arguments.
You may:
  - improve a tool's DOCSTRING (clarity, when to use it, argument guidance);
  - change a tool's behavior by giving it a real body (it becomes the impl);
  - ADD a new function (a composite tool) that calls existing tools via self,
    e.g. def find_and_book(self, ...): r = self.search_direct_flight(...); ...
Leave a body as `...` to override only the docstring (keep tau2's behavior).
"""

def book_reservation(self, *args, **kwargs):
    """Book a reservation.

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
    insurance: Whether the reservation has insurance."""
    ...

def calculate(self, *args, **kwargs):
    """Calculate the result of a mathematical expression.

Args:
    expression: The mathematical expression to calculate, such as '2 + 2'. The expression can contain numbers, operators (+, -, *, /), parentheses, and spaces.

Returns:
    The result of the mathematical expression.

Raises:
    ValueError: If the expression is invalid."""
    ...

def cancel_reservation(self, *args, **kwargs):
    """Cancel the whole reservation.

Args:
    reservation_id: The reservation ID, such as 'ZFA04Y'.

Returns:
    The updated reservation.

Raises:
    ValueError: If the reservation is not found."""
    ...

def get_flight_status(self, *args, **kwargs):
    """Get the status of a flight.

Args:
    flight_number: The flight number.
    date: The date of the flight.

Returns:
    The status of the flight.

Raises:
    ValueError: If the flight is not found."""
    ...

def get_reservation_details(self, *args, **kwargs):
    """Get the details of a reservation.

Args:
    reservation_id: The reservation ID, such as '8JX2WO'.

Returns:
    The reservation details.

Raises:
    ValueError: If the reservation is not found."""
    ...

def get_user_details(self, *args, **kwargs):
    """Get the details of a user, including their reservations.

Args:
    user_id: The user ID, such as 'sara_doe_496'.

Returns:
    The user details.

Raises:
    ValueError: If the user is not found."""
    ...

def list_all_airports(self, *args, **kwargs):
    """Returns a list of all available airports.

Returns:
    A dictionary mapping IATA codes to AirportInfo objects."""
    ...

def search_direct_flight(self, *args, **kwargs):
    """Search for direct flights between two cities on a specific date.

Args:
    origin: The origin city airport in three letters, such as 'JFK'.
    destination: The destination city airport in three letters, such as 'LAX'.
    date: The date of the flight in the format 'YYYY-MM-DD', such as '2024-01-01'.

Returns:
    The direct flights between the two cities on the specific date."""
    ...

def search_onestop_flight(self, *args, **kwargs):
    """Search for one-stop flights between two cities on a specific date.

Args:
    origin: The origin city airport in three letters, such as 'JFK'.
    destination: The destination city airport in three letters, such as 'LAX'.
    date: The date of the flight in the format 'YYYY-MM-DD', such as '2024-05-01'.

Returns:
    A list of pairs of DirectFlight objects."""
    ...

def send_certificate(self, *args, **kwargs):
    """Send a certificate to a user. Be careful!

Args:
    user_id: The ID of the user to book the reservation, such as 'sara_doe_496'.
    amount: The amount of the certificate to send.

Returns:
    A message indicating the certificate was sent.

Raises:
    ValueError: If the user is not found."""
    ...

def transfer_to_human_agents(self, *args, **kwargs):
    """Transfer the user to a human agent, with a summary of the user's issue.
Only transfer if
 -  the user explicitly asks for a human agent
 -  given the policy and the available tools, you cannot solve the user's issue.

Args:
    summary: A summary of the user's issue.

Returns:
    A message indicating the user has been transferred to a human agent."""
    ...

def update_reservation_baggages(self, *args, **kwargs):
    """Update the baggage information of a reservation.

Args:
    reservation_id: The reservation ID, such as 'ZFA04Y'
    total_baggages: The updated total number of baggage items included in the reservation.
    nonfree_baggages: The updated number of non-free baggage items included in the reservation.
    payment_id: The payment id stored in user profile, such as 'credit_card_7815826', 'gift_card_7815826', 'certificate_7815826'.

Returns:
    The updated reservation.

Raises:
    ValueError: If the reservation is not found.
    ValueError: If the user is not found.
    ValueError: If the payment method is not found.
    ValueError: If the certificate cannot be used to update reservation.
    ValueError: If the gift card balance is not enough."""
    ...

def update_reservation_flights(self, *args, **kwargs):
    """Update the flight information of a reservation.


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
    ValueError: If the gift card balance is not enough."""
    ...

def update_reservation_passengers(self, *args, **kwargs):
    """Update the passenger information of a reservation.

Args:
    reservation_id: The reservation ID, such as 'ZFA04Y'.
    passengers: An array of objects containing details about each passenger.

Returns:
    The updated reservation.

Raises:
    ValueError: If the reservation is not found.
    ValueError: If the number of passengers does not match."""
    ...
