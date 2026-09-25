def transfer_to_human_agents(summary: str):
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
    return env_transfer_to_human_agents(summary=summary)
