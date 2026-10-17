def running_peaks(values: list[int]) -> list[int]:
    current = 0
    peaks: list[int] = []
    for value in values:
        current = max(current, value)
        peaks.append(current)
    return peaks
