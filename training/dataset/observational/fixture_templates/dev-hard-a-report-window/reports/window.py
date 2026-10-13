"""Window helper."""
import datetime


def last_seven(today: datetime.date) -> list:
    start = today - datetime.timedelta(days=6)
    out = []
    d = start
    while d <= today:
        out.append(d.isoformat())
        d += datetime.timedelta(days=1)
    return out
