def mapping_diff(before, after):
    if not hasattr(before, "items") or not hasattr(after, "items"):
        raise ValueError("inputs must be mappings")
    return {
        "added": {key: after[key] for key in sorted(after) if key not in before},
        "removed": {key: before[key] for key in sorted(before) if key not in after},
        "changed": {},
    }
