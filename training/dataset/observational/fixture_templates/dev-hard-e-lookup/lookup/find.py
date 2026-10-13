def lookup(rows, id_):
    for row in rows:
        if row["id"] == id_:
            return row
    return None
