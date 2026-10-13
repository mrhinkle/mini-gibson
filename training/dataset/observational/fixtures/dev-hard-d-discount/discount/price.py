def final_price(amount_cents, percent, fixed_cents):
    amount_cents = amount_cents - fixed_cents
    amount_cents = amount_cents * (100 - percent) // 100
    return amount_cents
