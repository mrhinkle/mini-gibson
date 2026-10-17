def page_slice(items, page, page_size):
    if not isinstance(page, int) or not isinstance(page_size, int):
        raise ValueError("page and page_size must be integers")
    if page <= 0 or page_size <= 0:
        raise ValueError("page and page_size must be positive")
    start = page * page_size
    return list(items[start : start + page_size])
