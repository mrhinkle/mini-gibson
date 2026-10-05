def clamp(x, lo, hi):
    # BUG: swaps lo/hi comparison
    if x < lo: return hi
    if x > hi: return lo
    return x
