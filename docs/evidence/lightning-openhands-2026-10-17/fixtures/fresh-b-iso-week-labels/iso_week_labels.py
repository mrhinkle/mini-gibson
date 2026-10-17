from datetime import date


def iso_week_labels(values: list[str]) -> list[str]:
    labels = []
    for value in values:
        parsed = date.fromisoformat(value)
        _, week, weekday = parsed.isocalendar()
        labels.append(f"{parsed.year:04d}-W{week:02d}-{weekday}")
    return labels
