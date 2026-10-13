def resolve_port(cli_port, environ, file_port):
    env = environ.get("PORT") if environ else None
    if file_port is not None:
        return file_port
    if env is not None:
        return int(env) if env else 0
    if cli_port is not None:
        return cli_port
    return 8080
