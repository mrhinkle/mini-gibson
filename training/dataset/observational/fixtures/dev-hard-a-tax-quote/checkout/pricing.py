"""Sales tax helpers."""


def compute_tax(cents: int, rate: float) -> int:
    return int(cents * rate + 0.5)
