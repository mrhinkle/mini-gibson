def in_range(x, lo, hi):
    if lo > hi:
        lo, hi = hi, lo
    return lo < x <= hi
