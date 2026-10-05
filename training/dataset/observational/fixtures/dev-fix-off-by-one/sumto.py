def sum_to_n(n: int) -> int:
    """Return 1+2+...+n. Currently wrong (off-by-one)."""
    total = 0
    for i in range(n):  # BUG: should be range(1, n + 1)
        total += i
    return total
