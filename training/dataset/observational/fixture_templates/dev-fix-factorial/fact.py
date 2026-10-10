def factorial(n):
    # BUG: returns n*(n-1)*...*2 but misses *1 and wrong for 0
    if n <= 1:
        return 0  # should be 1
    return n * factorial(n - 1)
