def chunk_list(items: list[object], size: int) -> list[list[object]]:
    if size <= 0:
        raise ValueError("size must be positive")
    return [items[index : index + size] for index in range(0, len(items) - size + 1, size)]
