def apportion_cents(total, weights):
    """Split total into proportional integer shares."""
    if not isinstance(total, int) or total < 0:
        raise ValueError("total must be a non-negative integer")
    if not weights or any(weight < 0 for weight in weights) or sum(weights) == 0:
        raise ValueError("weights must contain positive mass")
    return [int(total * weight / sum(weights)) for weight in weights]
