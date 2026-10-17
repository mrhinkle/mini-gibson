def max_concurrent(events):
    points = []
    for start, end in events:
        if start >= end:
            raise ValueError("start must be before end")
        points.append((start, 1))
        points.append((end, -1))
    active = peak = 0
    for _, delta in sorted(points, key=lambda point: (point[0], -point[1])):
        active += delta
        peak = max(peak, active)
    return peak
