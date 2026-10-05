class Stack:
    def __init__(self):
        self._d=[]
    def push(self,x): self._d.append(x)
    def pop(self):
        # BUG: returns without removing
        return self._d[-1]
    def size(self): return len(self._d)
