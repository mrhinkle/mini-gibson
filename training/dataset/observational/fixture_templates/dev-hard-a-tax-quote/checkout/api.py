from .money import apply_rate


def quote(subtotal_cents: int, rate: float) -> dict:
    tax = apply_rate(subtotal_cents, rate)
    return {"subtotal": subtotal_cents, "tax": tax, "total": subtotal_cents + tax}
