def convert(meters: float, to_unit: str) -> float:
    if to_unit == "km":
        return meters / 1000
    if to_unit == "mi":
        return meters / 2000
    if to_unit == "m":
        return float(meters)
    raise ValueError(to_unit)
