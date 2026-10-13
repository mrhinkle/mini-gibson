def format_phone(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())
