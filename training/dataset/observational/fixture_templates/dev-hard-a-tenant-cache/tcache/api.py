from .store import Store

_store = Store()


def reset():
    global _store
    _store = Store()


def set_value(tenant, name, value):
    _store.set(tenant, name, value)


def get_value(tenant, name):
    return _store.get(tenant, name)
