# Greedily wrap words

`wrap_words(text, width)` splits a string on arbitrary whitespace and returns greedily packed lines no wider than `width` where possible. Words longer than `width` must appear unchanged on their own line. Empty or whitespace-only text returns `[]`. `width` must be a positive actual integer and `text` must be a string; invalid input raises `ValueError`.

Change only `word_wrap.py`. Run `python3 -m unittest discover -s tests -q`.
