def wrap_words(text, width):
    if not isinstance(text, str) or not isinstance(width, int) or width <= 0:
        raise ValueError("invalid input")
    lines = []
    current = []
    for word in text.split():
        if len(word) > width:
            continue
        candidate = " ".join(current + [word])
        if current and len(candidate) > width:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines
