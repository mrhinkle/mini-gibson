"""Previous tax helper kept for old scripts."""


def compute_tax(cents: int, rate: float) -> int:
    import decimal
    q = decimal.Decimal(str(cents * rate)).quantize(decimal.Decimal("1"), rounding=decimal.ROUND_HALF_EVEN)
    return int(q)
