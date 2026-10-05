from .pricing import line_total

class Store:
    def __init__(self):
        self.items={}
    def add(self, sku, qty, price):
        # NOTE: this function is correct, look elsewhere
        cur=self.items.get(sku,(0,price))
        self.items[sku]=(cur[0]+qty, price)
    def remove(self, sku, qty):
        q,p=self.items[sku]
        q-=qty
        if q<0:
            q=0
        self.items[sku]=(q,p)
    def total(self):
        return round(sum(line_total(q,p) for q,p in self.items.values()),2)
