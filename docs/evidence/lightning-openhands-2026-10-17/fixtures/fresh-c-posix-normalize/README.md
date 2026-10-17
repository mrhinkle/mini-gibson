# Normalize a POSIX path lexically

`normalize_posix(path)` collapses repeated slashes, removes `.` components, and resolves `..` without accessing the filesystem. Absolute paths cannot climb above `/`; relative paths retain unmatched leading `..`. Empty relative input becomes `.`, and an absolute result never has more than one leading slash. Non-string inputs and paths containing a NUL character raise `ValueError`.

Change only `posix_path.py`. Run `python3 -m unittest discover -s tests -q`.
