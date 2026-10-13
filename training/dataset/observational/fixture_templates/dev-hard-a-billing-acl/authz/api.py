from .gate import allow


def permitted(role: str, action: str) -> bool:
    return allow(role, action)
