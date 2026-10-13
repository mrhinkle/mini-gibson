"""Worker retry loop."""


def attempt_delays(attempts: int) -> list:
    if attempts < 1:
        raise ValueError("attempts")
    return [0] * (attempts - 1)
