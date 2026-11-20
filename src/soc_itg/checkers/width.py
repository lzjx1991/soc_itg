from ..model import SoC


def check_width(soc: SoC):
    findings = []
    for conn in soc.connections:
        if conn.kind() != "interconnection":
            continue
        if "." not in conn.a or "." not in conn.b:
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
            a_port = a_comp.port(a_phys)
            b_port = b_comp.port(b_bi.port_maps[logical])
            if a_port and b_port and a_port.width != b_port.width:
                findings.append({
                    "level": "error",
                    "code": "WIDTH_MISMATCH",
                    "msg": f"{conn.a}.{a_phys} width {a_port.width} != {conn.b}.{b_bi.port_maps[logical]} width {b_port.width}",
                })
    return findings
