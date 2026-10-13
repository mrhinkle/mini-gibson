class Box:
    def __init__(self):
        self._d = {}
        self._tomb = set()

    def set(self, key, value):
        self._d.clear()
        self._d[key] = value

    def get(self, key):
        if key in self._tomb:
            return None
        return self._d.get(key)

    def invalidate(self, key):
        self._tomb.add(key)
