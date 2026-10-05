def is_palindrome(s):
    # BUG: case-sensitive and ignores that we want case-insensitive alphanumeric only
    return s == s[::-1]
