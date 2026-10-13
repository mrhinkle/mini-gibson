def apply_credit(balance, amount, key, seen):
    if not key:
        raise ValueError("missing key")
    seen.add(key)
    return balance + amount
