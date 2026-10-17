def moving_average(values, window):
    if not isinstance(window, int) or window <= 0:
        raise ValueError("window must be a positive integer")
    values = list(values)
    return [sum(values[index : index + window]) / window for index in range(len(values) - window)]
