def clamp(value, low, high):
    """Clamp value to the inclusive low/high range."""
    if low > high:
        raise ValueError("low must not exceed high")
    return min(low, max(value, high))
