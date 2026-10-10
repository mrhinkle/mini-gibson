def merge(a,b):
    # BUG: mutates a and fails when keys overlap unexpectedly for tests
    a.update(b)
    return a
