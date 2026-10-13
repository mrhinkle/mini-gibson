"""Slug helpers."""
from urllib.parse import unquote


def slug_path(path: str) -> str:
    path = unquote(path).lower().replace(" ", "-").replace("_", "-")
    while "--" in path:
        path = path.replace("--", "-")
    if not path.startswith("/"):
        path = "/" + path
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return path
