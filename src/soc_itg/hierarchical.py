from dataclasses import dataclass, field

from .design.resolve import build_tree, resolve_path, plan_connection


@dataclass
class HChild:
    name: str
    module: str
    ports: list = field(default_factory=list)


@dataclass
class HModule:
    name: str
    ports: list = field(default_factory=list)
    children: list = field(default_factory=list)
    wires: list = field(default_factory=list)
    conns: list = field(default_factory=list)
    assigns: list = field(default_factory=list)

    def has_port(self, name):
        return any(p["name"] == name for p in self.ports)

    def add_port(self, name, direction="inout", width=1):
        if not self.has_port(name):
            self.ports.append({"name": name, "direction": direction, "width": width})

    def add_wire(self, name, width=1):
        if not any(w[0] == name for w in self.wires):
            self.wires.append((name, width))


def _leaf_child(spec):
    return HChild(name=spec["name"], module=spec.get("module", spec["name"]), ports=spec.get("ports", []))


def _side(modules, ancestor, node, port, net, width):
    if node is ancestor:
        return (None, port)
    cur = node
    cur_port = port
    while cur.parent is not ancestor:
        parent = cur.parent
        pm = modules[parent.name]
        pport = f"{net}_pt"
        wname = f"{net}_w_{parent.name}"
        pm.add_port(pport, "inout", width)
        pm.add_wire(wname, width)
        pm.conns.append((cur.name, cur_port, wname))
        pm.assigns.append((pport, wname))
        cur = parent
        cur_port = pport
    return (cur.name, cur_port)


def build_hierarchy(instances, connections, top_name=None):
    roots, nodes = build_tree(instances)
    modules = {}

    def build(node):
        if not node.children:
            return None
        children = []
        for ch in node.children:
            if ch.children:
                build(ch)
                children.append(HChild(name=ch.name, module=ch.name, ports=modules[ch.name].ports))
            else:
                children.append(_leaf_child(ch.spec))
        modules[node.name] = HModule(name=node.name, children=children)
        return modules[node.name]

    for root in roots:
        build(root)
    top = top_name or (roots[0].name if roots else None)

    for idx, conn in enumerate(connections):
        if isinstance(conn, str):
            a, b = [part.strip() for part in conn.split("=", 1)]
            width = 1
        else:
            a, b = conn["a"], conn["b"]
            width = conn.get("width", 1)
        path_a, port_a = a.rsplit(".", 1)
        path_b, port_b = b.rsplit(".", 1)
        chain_a = resolve_path(nodes, path_a)
        chain_b = resolve_path(nodes, path_b)
        if chain_a is None or chain_b is None:
            continue
        plan = plan_connection(nodes, path_a, path_b)
        if plan is None:
            continue
        ancestor = plan["lca"]
        module = modules.get(ancestor.name)
        if module is None:
            continue
        net = f"net_{idx}"
        module.add_wire(net, width)
        left = _side(modules, ancestor, chain_a[-1], port_a, net, width)
        right = _side(modules, ancestor, chain_b[-1], port_b, net, width)
        for end in (left, right):
            if end[0] is None:
                module.add_port(end[1], "inout", width)
                module.assigns.append((end[1], net))
            else:
                module.conns.append((end[0], end[1], net))
    return modules, top


def _range(width):
    return f"[{width - 1}:0] " if width > 1 else ""


def emit_module(module):
    lines = []
    if module.ports:
        decls = [f"  {p.get('direction', 'inout')} wire {_range(p.get('width', 1))}{p['name']}" for p in module.ports]
        lines.append(f"module {module.name} (")
        lines.append(",\n".join(decls))
        lines.append(");")
    else:
        lines.append(f"module {module.name};")
    for name, width in module.wires:
        lines.append(f"  wire {_range(width)}{name};")
    conn_map = {(child, port): net for child, port, net in module.conns}
    for child in module.children:
        lines.append(f"  {child.module} {child.name} (")
        entries = []
        for port in child.ports:
            net = conn_map.get((child.name, port["name"]))
            entries.append(f"    .{port['name']}({net if net else ''})")
        lines.append(",\n".join(entries))
        lines.append("  );")
    for port, net in module.assigns:
        lines.append(f"  assign {port} = {net};")
    lines.append("endmodule")
    return "\n".join(lines) + "\n"


def emit_hierarchy(modules):
    return {name: emit_module(module) for name, module in modules.items()}
