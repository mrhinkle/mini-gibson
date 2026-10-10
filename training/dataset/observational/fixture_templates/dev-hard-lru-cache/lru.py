class LRU:
    def __init__(self, cap):
        self.cap=cap
        self.d={}
    def get(self, k):
        return self.d.get(k)
    def put(self, k, v):
        self.d[k]=v
        if len(self.d)>self.cap:
            # evicts arbitrary first-inserted key, ignores recency of get()
            self.d.pop(next(iter(self.d)))
