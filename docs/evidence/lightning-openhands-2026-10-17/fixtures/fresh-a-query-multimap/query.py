def parse_query_multimap(query):
    query = query.lstrip("?")
    result = {}
    for field in query.split("&"):
        if not field:
            continue
        key, _, value = field.partition("=")
        result[key] = [value]
    return result
