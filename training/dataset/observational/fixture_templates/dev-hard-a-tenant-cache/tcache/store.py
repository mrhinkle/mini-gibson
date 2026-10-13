"""Cache store."""
from .legacy.keys import make_key


class Store:
    def __init__(self):
        self._d = {}

    def set(self, tenant, name, value):
        self._d[make_key(tenant, name)] = value

    def get(self, tenant, name):
        return self._d.get(make_key(tenant, name))
