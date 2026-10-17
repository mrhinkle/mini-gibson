def dependency_order(graph):
    ordered = []
    seen = set()

    def visit(node):
        if node in seen:
            return
        seen.add(node)
        for dependency in graph.get(node, ()):
            visit(dependency)
        ordered.append(node)

    for node in graph:
        visit(node)
    return ordered
