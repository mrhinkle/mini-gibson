def normalize_tags(tags: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        value = tag.strip().casefold()
        if value and value not in seen:
            seen.add(value)
            normalized.append(value)
    return normalized
