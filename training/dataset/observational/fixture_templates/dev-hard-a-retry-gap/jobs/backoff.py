"""Backoff curve."""


def gap_ms(index: int) -> int:
    return 10 * (2 ** index)
