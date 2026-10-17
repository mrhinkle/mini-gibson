from settings import GREETING_PREFIX


def greeting(name, excited=False):
    cleaned = name.strip()
    punctuation = "." if excited else "!"
    return f"Hi, {cleaned}{punctuation}"
