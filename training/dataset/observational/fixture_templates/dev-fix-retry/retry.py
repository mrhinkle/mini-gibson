def retry_call(fn, times=3):
    # BUG: only tries once
    return fn()
