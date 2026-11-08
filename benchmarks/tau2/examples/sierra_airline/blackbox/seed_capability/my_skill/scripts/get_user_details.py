def get_user_details(user_id: str):
    """
    Get the details of a user, including their reservations.

    Args:
        user_id: The user ID, such as 'sara_doe_496'.

    Returns:
        The user details.

    Raises:
        ValueError: If the user is not found.
    """
    return env_get_user_details(user_id=user_id)
