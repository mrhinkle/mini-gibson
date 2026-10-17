# Fix `clamp`

`bounds.clamp(value, low, high)` must return `value` when it is inside the
inclusive range, `low` below the range, and `high` above it. It must raise
`ValueError` when `low > high`.

Make the smallest correct change and run `python3 -m unittest -q`.
