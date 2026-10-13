from .http.normalize import canonicalize


def canonicalize_path(path: str) -> str:
    return canonicalize(path)
