def two_sum_pair(values, target):
    seen = {}
    for index, value in enumerate(values):
        complement = target - value
        if complement in seen:
            return (seen[complement], index)
        seen[value] = index
    return None
