# Order tasks after dependencies

`dependency_order(graph)` accepts a mapping from task names to iterable direct
dependencies and returns a deterministic topological order. Dependencies must
appear before dependents; when several tasks are ready, choose the
lexicographically smallest name. Include dependency-only nodes. Raise
`ValueError` for a cycle and do not mutate the input.

Change only `dependencies.py`. Run `python3 -m unittest discover -s tests -q`.
