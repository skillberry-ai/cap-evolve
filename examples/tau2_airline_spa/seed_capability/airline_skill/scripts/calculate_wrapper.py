"""Baseline wrapper tool for the `calculate` primitive.

Part of `airline_skill`. Delegates to the frozen primitive tool `calculate`.
The optimizer may add guard/aggregation logic here; any helper it introduces
must be nested INSIDE the function below and prefixed with '_'.
"""


def calculate_wrapper(expression: str):
    """
    Calculate the result of a mathematical expression.

    Args:
        expression (str): The mathematical expression to calculate, such as '2 + 2'. The expression can contain numbers, operators (+, -, *, /), parentheses, and spaces.

    Returns:
        The result of the mathematical expression.

    Raises:
        ValueError: If the expression is invalid.
    """
    return calculate(expression=expression)
