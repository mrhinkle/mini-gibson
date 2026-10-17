def redact_token(token, visible=4):
    if not isinstance(token, str):
        raise ValueError("token must be a string")
    if len(token) <= visible:
        return token
    return "*" * (len(token) - visible) + token[-visible:]
