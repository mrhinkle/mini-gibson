def slugify(s):
    # BUG: keeps uppercase and spaces
    return s.replace(' ', '-')
