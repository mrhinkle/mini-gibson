UNIT_TO_SECONDS = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0}


def parse_duration(value):
    """Return a duration expressed in seconds."""
    if not isinstance(value, str) or len(value) < 2:
        raise ValueError("duration must be a number and unit")
    number = value[:-1]
    unit = value[-1].lower()
    if not number.isdigit() or unit not in UNIT_TO_SECONDS:
        raise ValueError("invalid duration")
    return int(number) * UNIT_TO_SECONDS[unit]
