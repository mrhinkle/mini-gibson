def chunked(iterable, size):
    if not isinstance(size, int) or size <= 0:
        raise ValueError("size must be a positive integer")
    chunk = []
    for item in iterable:
        chunk.append(item)
        if len(chunk) == size:
            yield chunk
            chunk = []
