from datetime import date


def dates_in_window(values: list[str], start: str, end: str) -> list[str]:
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    if start_date > end_date:
        raise ValueError("start must not be after end")

    dated_values = [(value, date.fromisoformat(value)) for value in values]
    return [value for value, day in dated_values if start_date <= day < end_date]
