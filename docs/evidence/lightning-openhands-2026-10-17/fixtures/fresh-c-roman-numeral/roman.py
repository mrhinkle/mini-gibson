VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def parse_roman(text):
    if not isinstance(text, str) or not text:
        raise ValueError("expected a Roman numeral")
    try:
        return sum(VALUES[character] for character in text)
    except KeyError as error:
        raise ValueError("invalid Roman numeral") from error
