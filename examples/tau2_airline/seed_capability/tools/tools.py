"""Candidate airline TOOLS — the optimizer may edit this file.

Each method below mirrors one tool exposed by tau2's ``AirlineTools`` for the
airline domain. The method DOCSTRING is the *live tool description* the agent
sees (the optimizer can rewrite it to make a tool easier to select / fill
correctly). A body of ``...`` (Ellipsis) means "keep tau2's default behavior" —
the adapter starts from a pristine ``AirlineTools`` and only overrides what you
change here.

The optimizer is ALLOWED to, on this file:
  * IMPROVE a tool's docstring (its description + Args) so the agent picks it and
    fills arguments correctly. The signature must stay compatible with tau2.
  * GIVE A TOOL A REAL BODY to change its behavior. A real body (anything other
    than a lone ``...``) replaces tau2's method. It runs as a bound method on the
    live ``AirlineTools`` instance, so it may call any sibling tool/helper via
    ``self`` (e.g. ``self.get_reservation_details(...)``, ``self._get_user(...)``)
    and must return the same kind of value tau2's tool returns.
  * ADD A NEW (COMPOSITE) TOOL: define a brand-new method here, decorate it with
    ``@is_tool(ToolType.READ|WRITE|GENERIC|THINK)``, and give it a docstring. It
    becomes a new agent-callable tool whose body may call existing tools through
    ``self`` to compose a higher-level action.
  * REMOVE A TOOL from the exposed set: list its name in the module-level
    ``REMOVE_TOOLS`` set below. Removed tools disappear from the agent's toolset.

Do NOT change a tool's name or its parameter names/types unless you also keep it
consistent — tau2 evaluation replays tool calls by name and arguments.

IMPORTANT (schema validity): this file deliberately does NOT use
``from __future__ import annotations``. Type annotations in tool signatures must
be REAL, importable objects (not strings), because tau2 builds each tool's
parameter JSON-schema via ``create_model("parameters", ...)`` from the live
signature and then calls ``model_json_schema()`` — stringified forward refs
(e.g. ``"Literal[...]"``) would fail to resolve. If you give a tool a real body
or add a composite tool, every type used in its signature must be imported here.
Docstring-only stubs (a lone ``...`` body) reuse tau2's pristine method object
(its real annotations + behavior), so their parameter schema always resolves.
"""

from typing import List, Literal, Optional  # noqa: F401  (available for tool signatures)

# tau2 data-model types referenced by some tool signatures. Imported so that any
# tool given a real body — or any new composite tool — has REAL, resolvable
# annotations and its ``create_model("parameters", ...)`` succeeds.
from tau2.domains.airline.data_model import (  # noqa: F401
    FlightInfo,
    Passenger,
    Payment,
)
from tau2.environment.toolkit import ToolType, is_tool

# Names of tools to REMOVE from the exposed agent toolset. Empty by default
# (the seed exposes exactly tau2's default airline tools, unchanged).
REMOVE_TOOLS: set[str] = set()


class AirlineToolsCandidate:
    """Candidate overrides for the airline tools.

    Methods with a body of ``...`` keep tau2's default behavior; only the
    docstring is taken as the live tool description. Methods with a real body
    replace tau2's behavior. New ``@is_tool``-decorated methods are added as
    composite tools.
    """

    @is_tool(ToolType.WRITE)
    def book_reservation(
        self,
        user_id: str,
        origin: str,
        destination: str,
        flight_type: Literal["round_trip", "one_way"],
        cabin: Literal["business", "economy", "basic_economy"],
        flights: List,
        passengers: List,
        payment_methods: List,
        total_baggages: int,
        nonfree_baggages: int,
        insurance: Literal["yes", "no"],
    ):
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
            insurance: Whether the reservation has insurance.
        """
        ...

    @is_tool(ToolType.GENERIC)
    def calculate(self, expression: str) -> str:
        """Calculate the result of a mathematical expression.

        Args:
            expression: The mathematical expression to calculate, such as '2 + 2'. The expression can contain numbers, operators (+, -, *, /), parentheses, and spaces.

        Returns:
            The result of the mathematical expression.

        Raises:
            ValueError: If the expression is invalid.
        """
        ...

    @is_tool(ToolType.WRITE)
    def cancel_reservation(self, reservation_id: str):
        """Cancel the whole reservation.

        Args:
            reservation_id: The reservation ID, such as 'ZFA04Y'.

        Returns:
            The updated reservation.

        Raises:
            ValueError: If the reservation is not found.
        """
        ...

    @is_tool(ToolType.READ)
    def get_reservation_details(self, reservation_id: str):
        """Get the details of a reservation.

        Args:
            reservation_id: The reservation ID, such as '8JX2WO'.

        Returns:
            The reservation details.

        Raises:
            ValueError: If the reservation is not found.
        """
        ...

    @is_tool(ToolType.READ)
    def get_user_details(self, user_id: str):
        """Get the details of a user, including their reservations.

        Args:
            user_id: The user ID, such as 'sara_doe_496'.

        Returns:
            The user details.

        Raises:
            ValueError: If the user is not found.
        """
        ...

    @is_tool(ToolType.READ)
    def list_all_airports(self):
        """Returns a list of all available airports.

        Returns:
            A dictionary mapping IATA codes to AirportInfo objects.
        """
        ...

    @is_tool(ToolType.READ)
    def search_direct_flight(self, origin: str, destination: str, date: str):
        """Search for direct flights between two cities on a specific date.

        Args:
            origin: The origin city airport in three letters, such as 'JFK'.
            destination: The destination city airport in three letters, such as 'LAX'.
            date: The date of the flight in the format 'YYYY-MM-DD', such as '2024-01-01'.

        Returns:
            The direct flights between the two cities on the specific date.
        """
        ...

    @is_tool(ToolType.READ)
    def search_onestop_flight(self, origin: str, destination: str, date: str):
        """Search for one-stop flights between two cities on a specific date.

        Args:
            origin: The origin city airport in three letters, such as 'JFK'.
            destination: The destination city airport in three letters, such as 'LAX'.
            date: The date of the flight in the format 'YYYY-MM-DD', such as '2024-05-01'.

        Returns:
            A list of pairs of DirectFlight objects.
        """
        ...

    @is_tool(ToolType.WRITE)
    def send_certificate(self, user_id: str, amount: int) -> str:
        """Send a certificate to a user. Be careful!

        Args:
            user_id: The ID of the user to book the reservation, such as 'sara_doe_496'.
            amount: The amount of the certificate to send.

        Returns:
            A message indicating the certificate was sent.

        Raises:
            ValueError: If the user is not found.
        """
        ...

    @is_tool(ToolType.GENERIC)
    def transfer_to_human_agents(self, summary: str) -> str:
        """Transfer the user to a human agent, with a summary of the user's issue.
        Only transfer if
         -  the user explicitly asks for a human agent
         -  given the policy and the available tools, you cannot solve the user's issue.

        Args:
            summary: A summary of the user's issue.

        Returns:
            A message indicating the user has been transferred to a human agent.
        """
        ...

    @is_tool(ToolType.WRITE)
    def update_reservation_baggages(
        self,
        reservation_id: str,
        total_baggages: int,
        nonfree_baggages: int,
        payment_id: str,
    ):
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
            ValueError: If the gift card balance is not enough.
        """
        ...

    @is_tool(ToolType.WRITE)
    def update_reservation_flights(
        self,
        reservation_id: str,
        cabin: Literal["business", "economy", "basic_economy"],
        flights: List,
        payment_id: str,
    ):
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
            ValueError: If the gift card balance is not enough.
        """
        ...

    @is_tool(ToolType.WRITE)
    def update_reservation_passengers(self, reservation_id: str, passengers: List):
        """Update the passenger information of a reservation.

        Args:
            reservation_id: The reservation ID, such as 'ZFA04Y'.
            passengers: An array of objects containing details about each passenger.

        Returns:
            The updated reservation.

        Raises:
            ValueError: If the reservation is not found.
            ValueError: If the number of passengers does not match.
        """
        ...

    @is_tool(ToolType.READ)
    def get_flight_status(self, flight_number: str, date: str) -> str:
        """Get the status of a flight.

        Args:
            flight_number: The flight number.
            date: The date of the flight.

        Returns:
            The status of the flight.

        Raises:
            ValueError: If the flight is not found.
        """
        ...
