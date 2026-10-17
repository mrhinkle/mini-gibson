import re


def slugify(text):
    """Return a lowercase, hyphen-separated slug."""
    return re.sub(r"[^a-z0-9]", "-", text.lower())
