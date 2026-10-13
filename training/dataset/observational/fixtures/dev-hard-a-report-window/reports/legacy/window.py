"""Legacy rolling window."""
import datetime


def days_back(today, n):
    return [(today - datetime.timedelta(days=i)).isoformat() for i in range(n, -1, -1)]
