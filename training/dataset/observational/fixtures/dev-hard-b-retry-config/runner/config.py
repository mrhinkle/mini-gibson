def load(data):
    data = dict(data or {})
    if "retry_count" not in data:
        return {"retry_count": 1}
    return {"retry_count": data["retry_count"]}
