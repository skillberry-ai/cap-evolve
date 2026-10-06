def calculate(expression: str):
    """
    Calculate the result of a mathematical expression.

    Args:
        expression: The mathematical expression to calculate, such as '2 + 2'. The expression can contain numbers, operators (+, -, *, /), parentheses, and spaces.

    Returns:
        The result of the mathematical expression.

    Raises:
        ValueError: If the expression is invalid.
    """
    return env_calculate(expression=expression)
