def decode_runs(runs):
    decoded = []
    for value, count in runs:
        if not isinstance(count, int):
            raise ValueError("count must be an integer")
        decoded.extend([value] * count)
    return decoded
