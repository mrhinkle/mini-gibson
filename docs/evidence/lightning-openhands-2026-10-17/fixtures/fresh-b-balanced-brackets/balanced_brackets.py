def brackets_balanced(text: str) -> bool:
    counts = {"(": 0, "[": 0, "{": 0}
    pairs = {")": "(", "]": "[", "}": "{"}
    for character in text:
        if character in counts:
            counts[character] += 1
        elif character in pairs:
            counts[pairs[character]] -= 1
    return all(count == 0 for count in counts.values())
