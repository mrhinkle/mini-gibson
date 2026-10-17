def round_robin(*iterables):
    result = []
    for group in zip(*iterables):
        result.extend(value for value in group if value)
    return result
