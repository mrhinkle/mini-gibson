def attempts(cfg):
    n = cfg.get("retry_count") or 1
    return n + 1
