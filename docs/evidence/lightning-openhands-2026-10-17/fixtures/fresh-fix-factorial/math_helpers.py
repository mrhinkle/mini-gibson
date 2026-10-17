def factorial(n):
    """Return n! for a non-negative integer."""
    if n == 1:
        return 1
    return n * factorial(n - 1)
