"""Baseline wrapper tool for the `send_certificate` primitive.

Part of `airline_skill`. Delegates to the frozen primitive tool `send_certificate`.
The optimizer may add guard/aggregation logic here; any helper it introduces
must be nested INSIDE the function below and prefixed with '_'.
"""


def send_certificate_wrapper(user_id: str, amount: int):
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
    return send_certificate(user_id=user_id, amount=amount)
