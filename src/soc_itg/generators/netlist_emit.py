from ..model.netlist import Netlist


def _rng(width):
    return f"[{width - 1}:0] " if width > 1 else ""


def emit_netlist(netlist: Netlist):
    lines = []
    if netlist.ports:
        decls = [f"  {p.direction:<6} wire {_rng(p.width)}{p.name}" for p in netlist.ports]
        lines.append(f"module {netlist.top} (")
        lines.append(",\n".join(decls))
        lines.append(");")
    else:
        lines.append(f"module {netlist.top};")
    lines.append("")

    for net in netlist.nets:
        if any(ep.instance == "" for ep in net.endpoints):
            continue
        lines.append(f"  wire {_rng(net.width)}{net.name};")
    for a in netlist.assigns:
        lines.append(f"  assign {a.target} = {a.expr};")
    lines.append("")

    port_net = {}
    for net in netlist.nets:
        for ep in net.endpoints:
            if ep.instance:
                port_net[(ep.instance, ep.port)] = net.name

    ties = {(t.instance, t.port): f"1'b{t.value}" for t in netlist.ties}

    for inst in netlist.instances:
        lines.append(f"  {inst.module} {inst.name} (")
        conns = []
        for p in inst.ports:
            key = (inst.name, p.name)
            expr = ties.get(key) or port_net.get(key) or ""
            conns.append(f"    .{p.name}({expr})")
        lines.append(",\n".join(conns))
        lines.append("  );")
        lines.append("")
    lines.append("endmodule")
    lines.append("")
    return "\n".join(lines)
