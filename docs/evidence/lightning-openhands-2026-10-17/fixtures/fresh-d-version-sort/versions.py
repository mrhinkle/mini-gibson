def sort_versions(versions):
    if any(version.count(".") != 2 for version in versions):
        raise ValueError("expected MAJOR.MINOR.PATCH")
    return sorted(versions)
