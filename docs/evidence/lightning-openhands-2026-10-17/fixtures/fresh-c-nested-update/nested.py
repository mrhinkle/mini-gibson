def set_in_copy(data, path, value):
    if not isinstance(data, dict) or not path:
        raise ValueError("invalid input")
    result = data.copy()
    current = result
    for key in path[:-1]:
        current = current.setdefault(key, {})
        if not isinstance(current, dict):
            raise TypeError("path crosses a non-dictionary")
    current[path[-1]] = value
    return result
