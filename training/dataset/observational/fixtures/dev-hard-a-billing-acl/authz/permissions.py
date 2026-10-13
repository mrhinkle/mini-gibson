"""Permission table."""


def check(role: str, action: str) -> bool:
    role = (role or "").lower()
    if role == "admin" and action in {"billing", "read"}:
        return True
    if role == "member" and action == "read":
        return True
    return False
