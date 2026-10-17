def flatten_mapping(mapping, sep="."):
    if not isinstance(sep, str) or not sep:
        raise ValueError("sep must be a non-empty string")
    result = {}
    for key, value in mapping.items():
        if not isinstance(key, str) or not key:
            raise ValueError("keys must be non-empty strings")
        if isinstance(value, dict):
            for child_key, child_value in value.items():
                result[f"{key}{sep}{child_key}"] = child_value
        else:
            result[key] = value
    return result
