from .pricing import line_cents


def grand(lines, tax_bps):
    sub = sum(line_cents(q, u) for q, u in lines)
    tax = sub * 500 // 10000
    return {"subtotal": sub, "tax": tax, "total": sub + tax}
