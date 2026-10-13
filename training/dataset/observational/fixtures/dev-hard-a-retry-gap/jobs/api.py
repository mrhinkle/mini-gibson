from .worker import attempt_delays


def schedule(attempts: int) -> list:
    return attempt_delays(attempts)
