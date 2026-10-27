from ..model import SoC


def _module_name(comp):
    return comp.vlnv.split(":")[2] if comp is not None else "unknown"


def _net_width(port):
    return port.width if port is not None else 1


def _collect_nets(soc):
    nets = {}
    ordered = []
    for conn in soc.connections:
        if conn.type != "interconnection":
            continue
        a_inst, a_if = conn.a.split(".", 1)
        b_inst, b_if = conn.b.split(".", 1)
        a_comp = soc.component_of(a_inst)
        b_comp = soc.component_of(b_inst)
        if a_comp is None or b_comp is None:
            continue
        a_bi = a_comp.bus_if(a_if)
        b_bi = b_comp.bus_if(b_if)
        if a_bi is None or b_bi is None:
            continue
        for logical, a_phys in a_bi.port_maps.items():
            if logical not in b_bi.port_maps:
                continue
            b_phys = b_bi.port_maps[logical]
            net = f"net_{a_inst}_{logical}".lower()
            nets[(a_inst, a_phys)] = net
            nets[(b_inst, b_phys)] = net
            if net not in [n for n, _ in ordered]:
                ordered.append((net, _net_width(a_comp.port(a_phys))))
    return nets, ordered


def generate_top_rtl(soc: SoC):
    nets, ordered = _collect_nets(soc)
    lines = [f"module {soc.top};", ""]
    for net, width in ordered:
        rng = f"[{width - 1}:0] " if width > 1 else ""
        lines.append(f"  wire {rng}{net};")
    if ordered:
        lines.append("")
    for inst in soc.instances:
        comp = soc.component_of(inst.name)
        if comp is None:
            continue
        lines.append(f"  {_module_name(comp)} u_{inst.name} (")
        entries = []
        for port in comp.ports:
            net = nets.get((inst.name, port.name))
            entries.append(f"    .{port.name}({net if net else ''})")
        lines.append(",\n".join(entries))
        lines.append("  );")
        lines.append("")
    lines.append("endmodule")
    lines.append("")
    return "\n".join(lines)
