# Expand explicit template placeholders

`expand_template(template, values)` replaces `${name}` placeholders with `str(values[name])` and turns `$$` into one literal dollar sign. Names use ASCII letters, digits, and underscores and cannot begin with a digit. Repeated placeholders are supported. Missing names raise `KeyError`; malformed templates, non-string templates, or non-mapping values raise `ValueError`. No environment variables are read.

Change only `template.py`. Run `python3 -m unittest discover -s tests -q`.
