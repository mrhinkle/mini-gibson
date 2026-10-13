"""Money rounding used by checkout."""


def apply_rate(cents: int, rate: float) -> int:
    return int(cents * rate)
