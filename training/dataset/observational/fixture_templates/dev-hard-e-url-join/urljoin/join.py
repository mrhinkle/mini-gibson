def join_url(base, path):
    if not path:
        return base
    if "?" in path:
        path = path.split("?", 1)[0]
    if base.endswith("/"):
        return base + "/" + path.lstrip("/")
    return base + "/" + path.lstrip("/")
