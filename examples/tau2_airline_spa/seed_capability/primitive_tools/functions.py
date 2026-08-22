"""tau2 airline PRIMITIVE TOOLS — the constant, frozen tool set.

This module is imported into the Skillberry Store as STANDALONE tools (not a
skill) by ``setup.sh``, mirroring the ``import-primitive-tools`` target in
skillberry-benchmarks/tau2/Makefile.

DO NOT MODIFY. The optimizer never touches this file. Every public function here
becomes one store tool tagged ``primitive-tool``.

``_make_api_call`` is an internal helper: because the importer's AST filter skips
any function whose name starts with ``_``, it is NEVER registered as a store
tool. It resolves the primitive's name from the calling frame, so it must only
ever be called directly from a primitive defined in this module.
"""

import inspect
import json

import requests

# Define the URL. ``env_id`` is injected by the store's executor at the top of
# the generated module, before this code is concatenated in.
base_url = "http://127.0.0.1:8004"
tools_url = f"{base_url}/{env_id}/tools"  # noqa: F821 — env_id injected by executor


def _make_api_call(**kwargs):
    """Helper function to make API calls with consistent structure."""
    method_name = inspect.currentframe().f_back.f_code.co_name
    headers = {"Content-Type": "application/json"}
    url = f"{tools_url}/{method_name}"
    response = requests.post(
        url, json={"name": method_name, "arguments": kwargs}, headers=headers
    )

    if response.status_code != 200:
        raise requests.exceptions.HTTPError(
            f"HTTP {response.status_code}: {response.text}"
        )

    result = response.json()
    # Tau2 environment manager stores the response as flattened json string inside
    # "content" key. However, on a failure - content key is a string containing
    # the error message.
    try:
        return json.loads(result["content"])
    except (json.JSONDecodeError, TypeError):
        return result["content"]


def book_reservation(
    user_id: str,
    origin: str,
    destination: str,
    flight_type: str,
    cabin: str,
    flights: str,
    passengers: str,
    payment_methods: str,
    total_baggages: 0,
    nonfree_baggages: 0,
    insurance: str,
):
    """
    Creates a flight reservation for a user with specified travel details.

    Parameters:
        user_id (str): Identifier of the user making the reservation.
        origin (str): Departure location.
        destination (str): Arrival location.
        flight_type (str): Type of flight (e.g., one-way, round-trip).
        cabin (str): Cabin class (e.g., economy, business).
        flights (str): Flight identifiers or details.
        passengers (str): Passenger information.
        payment_methods (str): Selected payment method(s).
        total_baggages (int): Total number of baggages.
        nonfree_baggages (int): Number of baggages requiring payment.
        insurance (str): Insurance option selected.

    Returns:
        dict: Reservation confirmation details.
    """
    return _make_api_call(
        user_id=user_id,
        origin=origin,
        destination=destination,
        flight_type=flight_type,
        cabin=cabin,
        flights=flights,
        passengers=passengers,
        payment_methods=payment_methods,
        total_baggages=total_baggages,
        nonfree_baggages=nonfree_baggages,
        insurance=insurance,
    )


def calculate(expression: str):
    """
    Calculate the result of a mathematical expression.

    Args:
        expression (str): The mathematical expression to calculate, such as '2 + 2'. The expression can contain numbers, operators (+, -, *, /), parentheses, and spaces.

    Returns:
        The result of the mathematical expression.

    Raises:
        ValueError: If the expression is invalid.
    """
    return _make_api_call(expression=expression)


def cancel_reservation(reservation_id: str):
    """
    Cancel the whole reservation.

    Args:
        reservation_id (str): The reservation ID, such as 'ZFA04Y'.

    Returns:
        The updated reservation.

    Raises:
        ValueError: If the reservation is not found.
    """
    return _make_api_call(reservation_id=reservation_id)


def get_reservation_details(reservation_id: str):
    """
    Get the details of a reservation.

    Args:
        reservation_id (str): The reservation ID, such as '8JX2WO'.

    Returns:
        The reservation details.

    Raises:
        ValueError: If the reservation is not found.
    """
    return _make_api_call(reservation_id=reservation_id)


def get_user_details(user_id: str):
    """
    Get the details of a user, including their reservations.

    Args:
        user_id (str): The user ID, such as 'sara_doe_496'.

    Returns:
        The user details.

    Raises:
        ValueError: If the user is not found.
    """
    return _make_api_call(user_id=user_id)


def list_all_airports():
    """
    Returns a list of all available airports.

    Returns:
        A dictionary mapping IATA codes to AirportInfo objects.

    """
    return _make_api_call()


def search_direct_flight(origin: str, destination: str, date: str):
    """
    Search for direct flights between two cities on a specific date.

    Args:
        origin (str): The origin city airport in three letters, such as 'JFK'.
        destination (str): The destination city airport in three letters, such as 'LAX'.
        date (str): The date of the flight in the format 'YYYY-MM-DD', such as '2024-01-01'.

    Returns:
        The direct flights between the two cities on the specific date.

    """
    return _make_api_call(origin=origin, destination=destination, date=date)


def search_onestop_flight(origin: str, destination: str, date: str):
    """
    Search for one-stop flights between two cities on a specific date.

    Args:
        origin (str): The origin city airport in three letters, such as 'JFK'.
        destination (str): The destination city airport in three letters, such as 'LAX'.
        date (str): The date of the flight in the format 'YYYY-MM-DD', such as '2024-05-01'.

    Returns:
        A list of pairs of DirectFlight objects.

    """
    return _make_api_call(origin=origin, destination=destination, date=date)


def send_certificate(user_id: str, amount: int):
    """
    Send a certificate to a user. Be careful!

    Args:
        user_id (str): The ID of the user to book the reservation, such as 'sara_doe_496'.
        amount (int): The amount of the certificate to send.

    Returns:
        A message indicating the certificate was sent.

    Raises:
        ValueError: If the user is not found.

    """
    return _make_api_call(user_id=user_id, amount=amount)


def update_reservation_baggages(
    reservation_id: str, total_baggages: int, nonfree_baggages: int, payment_id: str
):
    """
    Update the baggage information of a reservation.

    Args:
        reservation_id (str): The reservation ID, such as 'ZFA04Y'
        total_baggages (int): The updated total number of baggage items included in the reservation.
        nonfree_baggages (int): The updated number of non-free baggage items included in the reservation.
        payment_id (str): The payment id stored in user profile, such as 'credit_card_7815826', 'gift_card_7815826', 'certificate_7815826'.

    Returns:
        The updated reservation.

    Raises:
        ValueError: If the reservation is not found.
        ValueError: If the user is not found.
        ValueError: If the payment method is not found.
        ValueError: If the certificate cannot be used to update reservation.
        ValueError: If the gift card balance is not enough.

    """
    return _make_api_call(
        reservation_id=reservation_id,
        total_baggages=total_baggages,
        nonfree_baggages=nonfree_baggages,
        payment_id=payment_id,
    )


def update_reservation_flights(
    reservation_id: str, cabin: str, flights: str, payment_id: str
):
    """
    Update the flight information of a reservation.

    Args:
        reservation_id (str): The reservation ID, such as 'ZFA04Y'.
        cabin (str): The cabin class of the reservation
        flights (str): An array of objects containing details about each piece of flight in the ENTIRE new reservation. Even if the a flight segment is not changed, it should still be included in the array.
        payment_id (str): The payment id stored in user profile, such as 'credit_card_7815826', 'gift_card_7815826', 'certificate_7815826'.

    Returns:
        The updated reservation.

    Raises:
        ValueError: If the reservation is not found.
        ValueError: If the user is not found.
        ValueError: If the payment method is not found.
        ValueError: If the certificate cannot be used to update reservation.
        ValueError: If the gift card balance is not enough.

    """
    return _make_api_call(
        reservation_id=reservation_id,
        cabin=cabin,
        flights=flights,
        payment_id=payment_id,
    )


def update_reservation_passengers(reservation_id: str, passengers: str):
    """
    Update the passenger information of a reservation.

    Args:
        reservation_id (str): The reservation ID, such as 'ZFA04Y'.
        passengers (str): An array of objects containing details about each passenger.

    Returns:
        The updated reservation.

    Raises:
        ValueError: If the reservation is not found.
        ValueError: If the number of passengers does not match.

    """
    return _make_api_call(reservation_id=reservation_id, passengers=passengers)


def get_flight_status(flight_number: str, date: str):
    """
    Get the status of a flight.

    Args:
        flight_number (str): The flight number.
        date (str): The date of the flight.

    Returns:
        The status of the flight.

    Raises:
        ValueError: If the flight is not found.

    """
    return _make_api_call(flight_number=flight_number, date=date)


def transfer_to_human_agents(summary: str) -> str:
    """
    Transfer the user to a human agent, with a summary of the user's issue. Only transfer if the user explicitly asks for a human agent OR given the policy and the available tools, you cannot solve the user's issue.

    Args:
        summary (str): A summary of the user's issue.

    Returns:
        A message indicating the user has been transferred to a human agent.
    """
    return "Transfer successful"
