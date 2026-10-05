def unique_preserve(xs):
    # BUG: reverses first-seen order
    return list(reversed(list(dict.fromkeys(xs))))
