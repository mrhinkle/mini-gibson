# Correct the greeting formatter

`greeter.greeting(name, excited=False)` should use the prefix from `settings.py`,
trim surrounding whitespace from the name, and end with `.` normally or `!`
when `excited=True`. An empty name after trimming must raise `ValueError`.

Make the smallest correct change and run `python3 -m unittest -q`.
