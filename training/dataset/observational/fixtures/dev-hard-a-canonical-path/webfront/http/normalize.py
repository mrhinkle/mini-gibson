"""Request-path normalizer."""


def canonicalize(path: str) -> str:
    if not path.startswith("/"):
        path = "/" + path
    path = path.replace(" ", "-").replace("_", "-")
    while "--" in path:
        path = path.replace("--", "-")
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return path
