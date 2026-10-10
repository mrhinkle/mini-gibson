def parse_ints(s):
    # BUG: fails on empty tokens / trailing commas
    return [int(x) for x in s.split(',')]
