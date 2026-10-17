def stable_unique_by(records, key):
    """Keep one record for each value of key."""
    by_value = {record[key]: record for record in records}
    return list(by_value.values())
