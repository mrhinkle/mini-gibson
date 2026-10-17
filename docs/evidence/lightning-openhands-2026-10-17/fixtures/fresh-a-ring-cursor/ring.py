class RingCursor:
    def __init__(self, items):
        self.items = tuple(items)
        self.index = 0

    @property
    def current(self):
        return self.items[self.index]

    def advance(self, steps=1):
        self.index = (self.index + steps) % (len(self.items) - 1)
        return self.current
