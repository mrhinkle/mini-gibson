def join_path(*parts):
    # BUG: naive join duplicates slashes incorrectly for tests expecting posix
    return ''.join(parts)
