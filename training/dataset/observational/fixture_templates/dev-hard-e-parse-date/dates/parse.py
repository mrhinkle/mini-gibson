import datetime


def parse_date(s: str):
    return datetime.date.fromisoformat(s)
