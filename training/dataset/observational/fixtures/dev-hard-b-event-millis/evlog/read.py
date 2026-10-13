def read_event(payload):
    ts = payload["ts"]
    return {"kind": payload["kind"], "ts_ms": ts // 1000}
