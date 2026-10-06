def send_certificate(user_id: str, amount: int):
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
    return env_send_certificate(user_id=user_id, amount=amount)
