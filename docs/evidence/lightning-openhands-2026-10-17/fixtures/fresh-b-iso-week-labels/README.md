# Fix ISO week labels

`iso_week_labels(values)` converts ISO `YYYY-MM-DD` date strings to labels of
the form `YYYY-Www-d`, using the ISO week-numbering year, two-digit ISO week,
and ISO weekday (`1` for Monday through `7` for Sunday). Preserve input order.

Change only `iso_week_labels.py`. Run `python3 -m unittest discover -s tests -q`.
