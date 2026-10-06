def update_reservation_baggages(reservation_id: str, total_baggages: int, nonfree_baggages: int, payment_id: str):
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
    return env_update_reservation_baggages(reservation_id=reservation_id, total_baggages=total_baggages, nonfree_baggages=nonfree_baggages, payment_id=payment_id)
