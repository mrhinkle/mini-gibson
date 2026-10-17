def validate_port(value: object) -> int:
    if not isinstance(value, int):
        raise TypeError("port must be an integer")
    if not 1 <= value <= 65535:
        raise ValueError("port must be between 1 and 65535")
    return value
