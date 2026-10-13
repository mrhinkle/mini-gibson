def line_cents(qty, unit_cents, bulk_at=10, discount_bps=1000):
    sub = qty * unit_cents
    if qty > bulk_at:
        sub = sub * (10000 - discount_bps) // 10000
    return sub
