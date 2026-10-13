_EDGES = {
    "draft": {"submitted", "shipped"},
    "submitted": {"paid", "draft"},
    "paid": {"shipped"},
    "shipped": {"paid"},
}


def can_transition(src, dst):
    return dst in _EDGES.get(src, set())
