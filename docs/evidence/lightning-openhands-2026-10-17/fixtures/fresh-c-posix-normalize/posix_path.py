import posixpath


def normalize_posix(path):
    if not isinstance(path, str):
        raise ValueError("path must be a string")
    return posixpath.normpath(path)
