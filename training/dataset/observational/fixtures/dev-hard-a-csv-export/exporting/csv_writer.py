"""CSV writer."""


def write_csv(rows, columns):
    def cell(v):
        s = "" if v is None else str(v)
        if any(ch in s for ch in ',"\n'):
            s = '"' + s.replace('"', '""') + '"'
        return s
    lines = [",".join(columns)]
    for row in rows:
        lines.append(",".join(cell(row.get(c, "")) for c in columns))
    return "\n".join(lines) + "\n"
