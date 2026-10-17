from bisect import bisect_right


def histogram(values, boundaries):
    boundaries = list(boundaries)
    counts = [0] * (len(boundaries) + 1)
    for value in values:
        counts[bisect_right(boundaries, value)] += 1
    return counts
