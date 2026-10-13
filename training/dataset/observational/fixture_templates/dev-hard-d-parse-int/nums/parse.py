def parse_int(s: str) -> int:
    s = (s or "").strip()
    if s.startswith("+"):
        s = s[1:]
    if s.isdigit():
        return int(s)
    return 0
