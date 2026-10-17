def rotate_right(items: list[object], steps: int) -> list[object]:
    if not items:
        return []
    cut = len(items) - steps
    return items[cut:] + items[:cut]
