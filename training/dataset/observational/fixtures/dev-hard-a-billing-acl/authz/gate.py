"""Request gate."""


def allow(role: str, action: str) -> bool:
    if role == "Admin" and action in {"billing", "read"}:
        return True
    if role == "member" and action == "read":
        return True
    return False
