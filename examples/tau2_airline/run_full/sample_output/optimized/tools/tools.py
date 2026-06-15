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
    """Calculate the result of a mathematical expression. Use this tool whenever you need to compute price differences, total costs, baggage fees, refund amounts, or any arithmetic related to reservations.

Examples of when to use:
- Computing price difference when changing cabin class: e.g. 'num_passengers * ((new_price - old_price) + (new_price2 - old_price2))'
- Computing baggage fees: e.g. 'num_extra_bags * 50'
- Computing refund amounts or total costs

Args:
    expression: The mathematical expression to calculate, such as '2 * ((350 - 122) + (499 - 127))'. The expression can contain numbers, operators (+, -, *, /), parentheses, and spaces.

Returns:
    The result of the mathematical expression.

Raises:
    ValueError: If the expression is invalid."""
    ...

def cancel_reservation(self, *args, **kwargs):
    """Cancel the whole reservation. Before calling, verify cancellation criteria are met (booked within 24hrs, airline cancelled, business cabin, or has insurance with valid reason). Once confirmed with user, call this to execute the cancellation.

Also use cancel when: the user wants to change origin/destination/trip type — cancel the old reservation, then book a new one with book_reservation.

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
    """Get the details of a reservation. Call this for EACH reservation you need to inspect or modify.

When a user mentions multiple reservations, look up each one individually. The details include: flights (with flight numbers, dates, origin, destination, prices), passengers, cabin class, baggage info, insurance, payment methods, and trip type.

Args:
    reservation_id: The reservation ID, such as '8JX2WO'.

Returns:
    The reservation details.

Raises:
    ValueError: If the reservation is not found."""
    ...

def get_user_details(self, *args, **kwargs):
    """Get the details of a user, including their reservations, membership level, and payment methods.

IMPORTANT: Always call this tool early in the conversation once you have the user's ID. It provides essential context: the user's reservation list, membership level (regular/silver/gold), payment methods, email, and date of birth.

Args:
    user_id: The user ID, such as 'sara_doe_496'.

Returns:
    The user details including: user_id, email, addresses, date_of_birth, payment_methods, membership level, and reservation IDs.

Raises:
    ValueError: If the user is not found."""
    ...

def list_all_airports(self, *args, **kwargs):
    """Returns a list of all available airports.

Returns:
    A dictionary mapping IATA codes to AirportInfo objects."""
    ...

def search_direct_flight(self, *args, **kwargs):
    """Search for direct flights between two cities on a specific date. Use this when a user wants to change their flight to a different date, or book a new flight. Returns available flights with their prices and seat availability for each cabin class.

Args:
    origin: The origin city airport in three letters, such as 'JFK'.
    destination: The destination city airport in three letters, such as 'LAX'.
    date: The date of the flight in the format 'YYYY-MM-DD', such as '2024-05-24'.

Returns:
    A list of available direct flights between the two cities on the specific date, including flight numbers, times, prices per cabin, and seat availability."""
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
Only transfer if:
 -  the user explicitly asks for a human agent
 -  given the policy and the available tools, you truly cannot solve the user's issue.

DO NOT transfer for these cases (handle them yourself):
 - Changing destination/origin: cancel the old reservation and book a new one instead.
 - Cabin changes in any direction (including to basic_economy): use update_reservation_flights.
 - Complex multi-step requests: handle each step sequentially.
 - Multiple changes to one reservation: make separate API calls for each change type.

Args:
    summary: A summary of the user's issue.

Returns:
    A message indicating the user has been transferred to a human agent."""
    ...

def update_reservation_baggages(self, *args, **kwargs):
    """Update the baggage information of a reservation. Use this to add checked bags.

Remember: Users can add bags but cannot remove them. Each extra bag costs $50. Use `calculate` to compute the total cost before confirming with the user.

Free bag allowance depends on the booking user's membership level and the cabin class:
- Regular: 0 (basic_economy), 1 (economy), 2 (business) free bags per passenger
- Silver: 1 (basic_economy), 2 (economy), 3 (business) free bags per passenger
- Gold: 2 (basic_economy), 3 (economy), 4 (business) free bags per passenger

Args:
    reservation_id: The reservation ID, such as 'ZFA04Y'
    total_baggages: The updated TOTAL number of baggage items for the entire reservation (free + paid bags combined, across all passengers).
    nonfree_baggages: The updated number of PAID (non-free) baggage items for the entire reservation.
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
    """Update the flight and/or cabin information of a reservation. This tool is used for BOTH flight changes and cabin-only changes.

Use cases:
1. Change flights (keep same cabin): pass same cabin, new flights, and a payment method.
2. Change cabin only (keep same flights): pass the new cabin class and the SAME existing flights unchanged. All existing flight segments must still be listed. This works for ANY cabin target including 'basic_economy'.
3. Change both flights and cabin: pass new cabin and new flights.

IMPORTANT: When changing cabin only, you MUST still include all existing flights in the flights array unchanged. The cabin parameter is the NEW desired cabin for the entire reservation.

CRITICAL: cabin='basic_economy' is a fully valid value. Downgrading to basic_economy is always allowed. The restriction "basic economy flights cannot be changed" means you cannot change flight SEGMENTS when already in basic economy — it does NOT prevent changing the cabin TO basic_economy.

Args:
    reservation_id: The reservation ID, such as 'ZFA04Y'.
    cabin: The cabin class for the reservation (the target cabin): 'basic_economy', 'economy', or 'business'.
    flights: An array of objects containing details about each flight segment in the ENTIRE reservation. Each object has 'flight_number' and 'date'. Even if a flight segment is not changed, it MUST still be included in the array.
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
