def missing_integers(values):
    if not values:
        return []
    present = set(values)
    return [value for value in range(min(present) + 1, max(present)) if value not in present][:-1]
