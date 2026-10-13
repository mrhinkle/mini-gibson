def build_config(user):
    cfg = {"theme": "light", "plugins": ["core"]}
    user = user or {}
    if "plugins" in user:
        cfg["plugins"] = list(cfg["plugins"]) + list(user["plugins"])
    for k, v in user.items():
        if k != "plugins":
            cfg[k] = v
    cfg["theme"] = "light"
    return cfg
