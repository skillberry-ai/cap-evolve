"""Baseline wrapper tool for the `get_user_details` primitive.

Part of `airline_skill`. Delegates to the frozen primitive tool `get_user_details`.
The optimizer may add guard/aggregation logic here; any helper it introduces
must be nested INSIDE the function below and prefixed with '_'.
"""


def get_user_details_wrapper(user_id: str):
    """
    Get the details of a user, including their reservations.

    Args:
        user_id (str): The user ID, such as 'sara_doe_496'.

    Returns:
        The user details.

    Raises:
        ValueError: If the user is not found.
    """
    return get_user_details(user_id=user_id)
