from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class InstanceNode:
    name: str
    parent: "InstanceNode | None" = None
    children: list["InstanceNode"] = field(default_factory=list)
    spec: dict = field(default_factory=dict)

    def path(self):
        parts = []
        node = self
        while node is not None:
            parts.append(node.name)
            node = node.parent
        return ".".join(reversed(parts))


def build_tree(instances):
    nodes = {}
    for spec in instances:
        name = spec["name"]
        nodes[name] = InstanceNode(name=name, spec=spec)
    roots = []
    for spec in instances:
        node = nodes[spec["name"]]
        parent_name = spec.get("parent")
        if parent_name:
            parent = nodes.get(parent_name)
            if parent is None:
                raise KeyError(f"instance '{spec['name']}' parent '{parent_name}' not found")
            node.parent = parent
            parent.children.append(node)
        else:
            roots.append(node)
    return roots, nodes


def resolve_path(nodes, path):
    parts = path.split(".")
    node = nodes.get(parts[0])
    if node is None:
        return None
    chain = [node]
    for segment in parts[1:]:
        child = next((c for c in node.children if c.name == segment), None)
        if child is None:
            return None
        chain.append(child)
        node = child
    return chain


def lca(chain_a, chain_b):
    common = 0
    for a, b in zip(chain_a, chain_b):
        if a is b:
            common += 1
        else:
            break
    return chain_a[common - 1] if common else None


def plan_connection(nodes, path_a, path_b):
    chain_a = resolve_path(nodes, path_a)
    chain_b = resolve_path(nodes, path_b)
    if chain_a is None or chain_b is None:
        return None
    ancestor = lca(chain_a, chain_b)
    if ancestor is None:
        return None
    index = 0
    for i, a in enumerate(chain_a):
        if a is ancestor:
            index = i
            break
    side_a = chain_a[index + 1:-1]
    side_b = chain_b[index + 1:-1]
    return {
        "lca": ancestor,
        "endpoint_a": chain_a[-1],
        "endpoint_b": chain_b[-1],
        "side_a": side_a,
        "side_b": side_b,
    }
