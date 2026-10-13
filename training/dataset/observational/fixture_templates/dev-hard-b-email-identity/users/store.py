from .parse import normalize


class Directory:
    def __init__(self):
        self._seen = set()

    def add(self, email: str) -> str:
        key = normalize(email)
        if not (email or "").strip() or "@" not in (email or ""):
            raise ValueError("bad email")
        raw = email
        if raw in self._seen:
            raise ValueError("duplicate")
        self._seen.add(raw)
        return key
