from itertools import groupby


def group_runs(values):
    return [(value, len(list(group))) for value, group in groupby(sorted(values))]
