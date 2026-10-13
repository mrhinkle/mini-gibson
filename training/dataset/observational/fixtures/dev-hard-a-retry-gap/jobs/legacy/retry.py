"""Older retry helper."""


def gaps(attempts: int) -> list:
    return [10, 20, 40][: max(0, attempts - 1)]
