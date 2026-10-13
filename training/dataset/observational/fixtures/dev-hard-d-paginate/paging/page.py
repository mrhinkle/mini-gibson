def page(items, page, size):
    if page < 1 or size < 1:
        raise ValueError("bad")
    start = page * size
    end = start + size - 1
    return list(items[start:end])
