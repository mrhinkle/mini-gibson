def dedupe_records(records: list[dict[str, object]]) -> list[dict[str, object]]:
    seen: set[str] = set()
    unique: list[dict[str, object]] = []
    for record in records:
        email = str(record["email"])
        if email in seen:
            continue
        seen.add(email)
        unique.append(dict(record))
    return unique
