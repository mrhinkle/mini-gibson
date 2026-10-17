def luhn_valid(number):
    if not isinstance(number, str):
        return False
    digits = [int(character) for character in number if character.isdigit()]
    if not digits:
        return False
    total = 0
    for index, digit in enumerate(digits):
        if index % 2 == 0:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0
