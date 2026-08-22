"""Baseline wrapper tool for the `transfer_to_human_agents` primitive.

Part of `airline_skill`. Delegates to the frozen primitive tool `transfer_to_human_agents`.
The optimizer may add guard/aggregation logic here; any helper it introduces
must be nested INSIDE the function below and prefixed with '_'.
"""


def transfer_to_human_agents_wrapper(summary: str):
    """
    Transfer the user to a human agent, with a summary of the user's issue. Only transfer if the user explicitly asks for a human agent OR given the policy and the available tools, you cannot solve the user's issue.

    Args:
        summary (str): A summary of the user's issue.

    Returns:
        A message indicating the user has been transferred to a human agent.
    """
    return transfer_to_human_agents(summary=summary)
