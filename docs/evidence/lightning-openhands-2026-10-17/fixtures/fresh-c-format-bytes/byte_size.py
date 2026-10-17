UNITS = ["B", "KiB", "MiB", "GiB", "TiB"]


def format_bytes(size):
    if not isinstance(size, int) or size < 0:
        raise ValueError("size must be a non-negative integer")
    value = float(size)
    unit = UNITS[0]
    for candidate in UNITS[1:]:
        if value < 1000:
            break
        value /= 1000
        unit = candidate
    if unit == "B":
        return f"{size} B"
    return f"{value:.1f} {unit}"
