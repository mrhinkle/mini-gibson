def expand_template(template, values):
    if not isinstance(template, str) or not hasattr(values, "items"):
        raise ValueError("invalid template input")
    result = template
    for name, value in values.items():
        result = result.replace("${" + name + "}", str(value))
    return result
