def format_phone(s: str) -> str:
    digits = "".join(ch for ch in s if ch.isdigit())
    return "+1" + digits[-10:]
