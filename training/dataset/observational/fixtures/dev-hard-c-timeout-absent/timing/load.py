def timeout_seconds(data):
    raw = (data or {}).get("timeout") or "30"
    return int(raw)
