"""Table renderer."""


def to_csv(rows, columns):
    lines = [",".join(columns)]
    for row in rows:
        cells = []
        for c in columns:
            v = row.get(c, "")
            if v is None or v == "" or v == 0:
                continue
            cells.append(str(v))
        lines.append(",".join(cells))
    return "\n".join(lines) + "\n"
