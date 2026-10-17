# Fix slug normalization

`text_utils.slugify(text)` should lowercase input, replace each run of
non-alphanumeric characters with one hyphen, and remove leading or trailing
hyphens. Empty or punctuation-only input should return an empty string.

Make the smallest correct change and run `python3 -m unittest -q`.
