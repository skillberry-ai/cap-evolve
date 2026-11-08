"""The 14 frozen tau2 airline primitives. Each runs the real tool in tau2's environment service."""

import json
import os
import sys
import urllib.request


def _make_api_call(**kwargs):
    """POST one primitive call to the trial's environment in tau2's EnvironmentManager.

    The tool name is the calling ``env_<tool>`` function's name without ``env_``. ``env_id``
    is injected into this module's globals per call by the store, from the
    ``skillberry-context-env_id`` header.
    """
    tool = sys._getframe(1).f_code.co_name
    if tool.startswith("env_"):
        tool = tool[len("env_"):]
    env_id = globals().get("env_id")
    if not env_id:
        raise RuntimeError("no env_id in the execution context")
    base = (os.environ.get("SPA_REMOTE_ENV_URL") or "http://127.0.0.1:8004").rstrip("/")
    body = json.dumps(
        {"name": tool, "arguments": kwargs},
        default=lambda o: o.model_dump() if hasattr(o, "model_dump") else str(o),
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/{env_id}/tools/{tool}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            status = resp.status
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        status = e.code
        raw = ""
    if status != 200:
        raise RuntimeError(f"environment tool {tool} failed with HTTP status {status}")
    content = json.loads(raw).get("content")
    try:
        return json.loads(content)
    except (TypeError, ValueError):
        return content


def env_book_reservation(user_id: str, origin: str, destination: str, flight_type: str, cabin: str, flights: list, passengers: list, payment_methods: list, total_baggages: int, nonfree_baggages: int, insurance: str):
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
    return _make_api_call(user_id=user_id, origin=origin, destination=destination, flight_type=flight_type, cabin=cabin, flights=flights, passengers=passengers, payment_methods=payment_methods, total_baggages=total_baggages, nonfree_baggages=nonfree_baggages, insurance=insurance)


def env_calculate(expression: str):
    """
    Calculate the result of a mathematical expression.

    Args:
        expression: The mathematical expression to calculate, such as '2 + 2'. The expression can contain numbers, operators (+, -, *, /), parentheses, and spaces.

    Returns:
        The result of the mathematical expression.

    Raises:
        ValueError: If the expression is invalid.
    """
    return _make_api_call(expression=expression)


def env_cancel_reservation(reservation_id: str):
    """
    Cancel the whole reservation.

    Args:
        reservation_id: The reservation ID, such as 'ZFA04Y'.

    Returns:
        The updated reservation.

    Raises:
        ValueError: If the reservation is not found.
    """
    return _make_api_call(reservation_id=reservation_id)


def env_get_reservation_details(reservation_id: str):
    """
    Get the details of a reservation.

    Args:
        reservation_id: The reservation ID, such as '8JX2WO'.

    Returns:
        The reservation details.

    Raises:
        ValueError: If the reservation is not found.
    """
    return _make_api_call(reservation_id=reservation_id)


def env_get_user_details(user_id: str):
    """
    Get the details of a user, including their reservations.

    Args:
        user_id: The user ID, such as 'sara_doe_496'.

    Returns:
        The user details.

    Raises:
        ValueError: If the user is not found.
    """
    return _make_api_call(user_id=user_id)


def env_list_all_airports():
    """Returns a list of all available airports.

    Returns:
        A dictionary mapping IATA codes to AirportInfo objects.
    """
    return _make_api_call()


def env_search_direct_flight(origin: str, destination: str, date: str):
    """
    Search for direct flights between two cities on a specific date.

    Args:
        origin: The origin city airport in three letters, such as 'JFK'.
        destination: The destination city airport in three letters, such as 'LAX'.
        date: The date of the flight in the format 'YYYY-MM-DD', such as '2024-01-01'.

    Returns:
        The direct flights between the two cities on the specific date.
    """
    return _make_api_call(origin=origin, destination=destination, date=date)


def env_search_onestop_flight(origin: str, destination: str, date: str):
    """
    Search for one-stop flights between two cities on a specific date.

    Args:
        origin: The origin city airport in three letters, such as 'JFK'.
        destination: The destination city airport in three letters, such as 'LAX'.
        date: The date of the flight in the format 'YYYY-MM-DD', such as '2024-05-01'.

    Returns:
        A list of pairs of DirectFlight objects.
    """
    return _make_api_call(origin=origin, destination=destination, date=date)


def env_send_certificate(user_id: str, amount: int):
    """
    Send a certificate to a user. Be careful!

    Args:
        user_id: The ID of the user to book the reservation, such as 'sara_doe_496'.
        amount: The amount of the certificate to send.

    Returns:
        A message indicating the certificate was sent.

    Raises:
        ValueError: If the user is not found.
    """
    return _make_api_call(user_id=user_id, amount=amount)


def env_transfer_to_human_agents(summary: str):
    """
    Transfer the user to a human agent, with a summary of the user's issue.
    Only transfer if
     -  the user explicitly asks for a human agent
     -  given the policy and the available tools, you cannot solve the user's issue.

    Args:
        summary: A summary of the user's issue.

    Returns:
        A message indicating the user has been transferred to a human agent.
    """
    return _make_api_call(summary=summary)


def env_update_reservation_baggages(reservation_id: str, total_baggages: int, nonfree_baggages: int, payment_id: str):
    """
    Update the baggage information of a reservation.

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
        ValueError: If the gift card balance is not enough.
    """
    return _make_api_call(reservation_id=reservation_id, total_baggages=total_baggages, nonfree_baggages=nonfree_baggages, payment_id=payment_id)


def env_update_reservation_flights(reservation_id: str, cabin: str, flights: list, payment_id: str):
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
    return _make_api_call(reservation_id=reservation_id, cabin=cabin, flights=flights, payment_id=payment_id)


def env_update_reservation_passengers(reservation_id: str, passengers: list):
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
    return _make_api_call(reservation_id=reservation_id, passengers=passengers)


def env_get_flight_status(flight_number: str, date: str):
    """
    Get the status of a flight.

    Args:
        flight_number: The flight number.
        date: The date of the flight.

    Returns:
        The status of the flight.

    Raises:
        ValueError: If the flight is not found.
    """
    return _make_api_call(flight_number=flight_number, date=date)
