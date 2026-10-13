def emit(kind, ts_ms):
    return {"kind": kind, "ts": ts_ms // 1000}
