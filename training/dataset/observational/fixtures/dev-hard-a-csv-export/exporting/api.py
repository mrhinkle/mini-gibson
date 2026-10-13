from .render.table import to_csv


def export_rows(rows, columns):
    return to_csv(rows, columns)
