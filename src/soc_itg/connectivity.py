from .model import SoC
from .model.ir import Component
from .model.netlist import Netlist, Net, Endpoint, PortSpec, InstanceSpec, TieBinding
from .pinmux.model import Pinmux
from .model.topcsr import TopCSR

APB_PORTS = [
    ("pclk", "input", 1), ("presetn", "input", 1), ("paddr", "input", 8),
    ("psel", "input", 1), ("penable", "input", 1), ("pwrite", "input", 1),
    ("pwdata", "input", 32), ("pstrb", "input", 4), ("prdata", "output", 32),
    ("pready", "output", 1), ("pslverr", "output", 1), ("pprot", "input", 3),
    ("err_irq", "output", 1),
]


def _san(name):
    return "".join(c.lower() if c.isalnum() else "_" for c in name)


def _pad_key(name):
    key = _san(name)
    return key[4:] if key.startswith("pad_") else key


def _split(endpoint):
    return tuple(endpoint.split(".", 1)) if "." in endpoint else (endpoint, "")


def _module_of(comp: Component | None):
    return comp.vlnv.split(":")[2] if comp is not None else "unknown"


def _port_direction(ip_direction):
    return {"out": "input", "in": "output"}.get(ip_direction, "inout")


def _resolve(soc: SoC, cell: str):
    inst, pin = _split(cell)
    comp = soc.component_of(inst) if inst else None
    port = comp.port(pin) if comp is not None else None
    if port is not None:
        return inst, pin, port.direction, port.width
    return inst, pin, "in", 1


def _add_instances(soc: SoC, netlist: Netlist):
    for inst in soc.instances:
        comp = soc.component_of(inst.name)
        ports = [PortSpec(name=p.name, direction=p.direction, width=p.width) for p in (comp.ports if comp else [])]
        netlist.instances.append(InstanceSpec(name=inst.name, module=_module_of(comp), ports=ports))


def _add_pinmux_instance(soc: SoC, pinmux: Pinmux, netlist: Netlist, module_name):
    ports = [PortSpec(name=f"pad_{_pad_key(p.name)}", direction="inout", width=1) for p in pinmux.pads]
    seen = set()
    for entry in pinmux.function_share:
        cells = entry.functions.values()
        for cell in cells:
            inst, pin, direction, width = _resolve(soc, cell)
            sig = f"ip_{_san(inst)}_{_san(pin)}"
            if sig in seen:
                continue
            seen.add(sig)
            ports.append(PortSpec(name=sig, direction=_port_direction(direction), width=width))
    for entry in pinmux.padshare:
        for cell in entry.pins.values():
            inst, pin, direction, width = _resolve(soc, cell)
            sig = f"ip_{_san(inst)}_{_san(pin)}"
            if sig in seen:
                continue
            seen.add(sig)
            ports.append(PortSpec(name=sig, direction=_port_direction(direction), width=width))
    for name, direction, width in APB_PORTS:
        ports.append(PortSpec(name=name, direction=direction, width=width))
    netlist.instances.append(InstanceSpec(name="u_pinmux", module=module_name, ports=ports))


def _add_pad_ports_and_nets(pinmux: Pinmux, netlist: Netlist):
    for pad in pinmux.pads:
        name = f"pad_{_pad_key(pad.name)}"
        netlist.ports.append(PortSpec(name=name, direction="inout", width=1))
        netlist.nets.append(Net(name=name, width=1, tri_state=True, endpoints=[
            Endpoint(instance="", port=name, direction="inout"),
            Endpoint(instance="u_pinmux", port=name, direction="inout"),
        ]))


def _add_interconnections(soc: SoC, netlist: Netlist, used: set):
    for conn in soc.connections:
        if conn.type != "interconnection":
            continue
        a_inst, a_if = _split(conn.a)
        b_inst, b_if = _split(conn.b)
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
            a_port = a_comp.port(a_phys)
            b_port = b_comp.port(b_phys)
            width = a_port.width if a_port else 1
            endpoints = []
            if a_port is not None:
                endpoints.append(Endpoint(instance=a_inst, port=a_phys, direction=a_port.direction))
                used.add((a_inst, a_phys))
            if b_port is not None:
                endpoints.append(Endpoint(instance=b_inst, port=b_phys, direction=b_port.direction))
                used.add((b_inst, b_phys))
            netlist.nets.append(Net(name=f"net_{_san(a_inst)}_{_san(logical)}", width=width, endpoints=endpoints))


def _add_pinmux_ip_nets(soc: SoC, pinmux: Pinmux, netlist: Netlist, used: set):
    cells = []
    for entry in pinmux.function_share:
        cells.extend(entry.functions.values())
    for entry in pinmux.padshare:
        cells.extend(entry.pins.values())
    seen = set()
    for cell in cells:
        inst, pin, direction, width = _resolve(soc, cell)
        key = (inst, pin)
        if key in used or key in seen:
            continue
        seen.add(key)
        sig = f"ip_{_san(inst)}_{_san(pin)}"
        netlist.nets.append(Net(name=f"net_{_san(inst)}_{_san(pin)}", width=width, endpoints=[
            Endpoint(instance=inst, port=pin, direction=direction),
            Endpoint(instance="u_pinmux", port=sig, direction=_port_direction(direction)),
        ]))


def _add_top_regs_instance(soc: SoC, topcsr: TopCSR, netlist: Netlist, module_name, used: set):
    ports = [PortSpec(name=n, direction=d, width=w) for n, d, w in APB_PORTS]
    for reg in topcsr.memory_map.registers:
        for field in reg.fields:
            width = field.msb - field.lsb + 1
            if field.access == "ro":
                ports.append(PortSpec(name=f"i_{_san(reg.name)}_{_san(field.name)}", direction="input", width=width))
            else:
                ports.append(PortSpec(name=f"o_{_san(reg.name)}_{_san(field.name)}", direction="output", width=width))
    netlist.instances.append(InstanceSpec(name="u_top_regs", module=module_name, ports=ports))
    for binding in topcsr.bindings:
        is_read = binding.access == "ro"
        sig = f"i_{_san(binding.reg)}_{_san(binding.field)}" if is_read else f"o_{_san(binding.reg)}_{_san(binding.field)}"
        regs_dir = "in" if is_read else "out"
        for target in binding.targets:
            inst, port = _split(target)
            if soc.instance(inst) is None:
                continue
            if (inst, port) in used:
                continue
            used.add((inst, port))
            comp = soc.component_of(inst)
            tp = comp.port(port) if comp is not None else None
            target_dir = tp.direction if tp is not None else "inout"
            netlist.nets.append(Net(
                name=f"net_{_san(binding.reg)}_{_san(binding.field)}_{_san(inst)}_{_san(port)}",
                width=binding.width,
                endpoints=[
                    Endpoint(instance="u_top_regs", port=sig, direction=regs_dir),
                    Endpoint(instance=inst, port=port, direction=target_dir),
                ],
            ))


def _add_ties(soc: SoC, netlist: Netlist, used: set):
    for conn in soc.connections:
        if conn.type not in ("tie", "unconnect"):
            continue
        inst, port = _split(conn.a)
        if not inst or not port or soc.instance(inst) is None:
            continue
        if (inst, port) in used:
            continue
        used.add((inst, port))
        if conn.type == "tie":
            netlist.ties.append(TieBinding(instance=inst, port=port, value=conn.value))


def build_netlist(soc: SoC, pinmux: Pinmux | None = None, topcsr: TopCSR | None = None, pinmux_module: str | None = None, topcsr_module: str | None = None, tool_version="0.1.0"):
    netlist = Netlist(top=soc.top, tool_version=tool_version)
    _add_instances(soc, netlist)
    used = set()
    module_name = pinmux_module or f"{soc.top}_pinmux"
    if pinmux is not None:
        _add_pinmux_instance(soc, pinmux, netlist, module_name)
        _add_pad_ports_and_nets(pinmux, netlist)
    _add_interconnections(soc, netlist, used)
    _add_ties(soc, netlist, used)
    if pinmux is not None:
        _add_pinmux_ip_nets(soc, pinmux, netlist, used)
    if topcsr is not None:
        _add_top_regs_instance(soc, topcsr, netlist, topcsr_module or f"{soc.top}_top_regs", used)
    return netlist
