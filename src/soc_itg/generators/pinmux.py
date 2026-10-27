from ..model import SoC
from ..pinmux.model import Pinmux
from ..pinmux.registers import cfg_field_signal, sel_signal


def _san(name):
    return "".join(c.lower() if c.isalnum() else "_" for c in name)


def _pad_key(name):
    key = _san(name)
    return key[4:] if key.startswith("pad_") else key


def _rng(width):
    return f"[{width - 1}:0] " if width > 1 else ""


def _resolve(soc: SoC, cell: str):
    if "." in cell:
        inst, pin = cell.split(".", 1)
    else:
        inst, pin = "", cell
    comp = soc.component_of(inst) if inst else None
    port = comp.port(pin) if comp is not None else None
    if port is not None:
        return inst, pin, port.direction, port.width
    return inst, pin, "in", 1


def _internal_signal(inst, pin):
    return f"ip_{_san(inst)}_{_san(pin)}" if inst else f"ip_{_san(pin)}"


def _port_direction(ip_direction):
    return {"out": "input", "in": "output"}.get(ip_direction, "inout")


def _collect_internal(pinmux: Pinmux, soc: SoC):
    ports = {}
    cells = []
    for entry in pinmux.function_share:
        cells.extend(entry.functions.values())
    for entry in pinmux.padshare:
        cells.extend(entry.pins.values())
    for entry in pinmux.bist_share:
        cells.extend(entry.functions.values())
    for cell in cells:
        inst, pin, direction, width = _resolve(soc, cell)
        ports[_internal_signal(inst, pin)] = (_port_direction(direction), width)
    return ports


def _normal_candidates(pinmux: Pinmux, pad_name):
    for entry in pinmux.function_share:
        if entry.pad == pad_name:
            return sel_signal(entry.group, "func"), list(entry.functions.values())
    for entry in pinmux.padshare:
        if entry.pad == pad_name:
            return sel_signal(entry.pad, "pad"), list(entry.pins.values())
    return None, []


def _bist_candidates(pinmux: Pinmux, pad_name):
    for entry in pinmux.bist_share:
        if entry.pad == pad_name:
            return list(entry.functions.values())
    return []


def _bist_active(pinmux: Pinmux):
    if not pinmux.bist_entries:
        return "1'b0"
    grouped = {}
    for entry in pinmux.bist_entries:
        grouped.setdefault(entry.bist_mode, []).append((entry.pad, entry.value))
    terms = []
    for _, conds in grouped.items():
        and_terms = " & ".join(f"({_san(pad)}_din == 1'b{value})" for pad, value in conds)
        terms.append(f"({and_terms})")
    return " | ".join(terms)


def generate_pinmux(soc: SoC, pinmux: Pinmux, reg_map, cfg_meta, addr_width=8, data_width=32):
    module = f"{soc.top}_pinmux"
    internal = _collect_internal(pinmux, soc)
    ports = [
        "  input  wire pclk",
        "  input  wire presetn",
        f"  input  wire [{addr_width - 1}:0] paddr",
        "  input  wire psel",
        "  input  wire penable",
        "  input  wire pwrite",
        f"  input  wire [{data_width - 1}:0] pwdata",
        f"  input  wire [{(data_width // 8) - 1}:0] pstrb",
        f"  output wire [{data_width - 1}:0] prdata",
        "  output wire pready",
        "  output wire pslverr",
        "  input  wire [2:0] pprot",
        "  output wire err_irq",
    ]
    for pad in pinmux.pads:
        ports.append(f"  inout  wire pad_{_pad_key(pad.name)}")
    for signal, (direction, width) in internal.items():
        ports.append(f"  {direction:<6} wire {_rng(width)}{signal}")

    lines = [f"module {module} (", ",\n".join(ports), ");", ""]

    for reg in reg_map.registers:
        for field in reg.fields:
            sig = cfg_field_signal(reg.name, field.name)
            width = field.msb - field.lsb + 1
            lines.append(f"  wire {_rng(width)}{sig};")
    lines.append("")

    for pad in pinmux.digital_pads():
        meta = cfg_meta.get(pad.name)
        if not meta:
            continue
        pieces = [cfg_field_signal(meta["reg"], fname) for fname, _ in meta["fields"]]
        high_to_low = ", ".join(reversed(pieces))
        pad_total = meta["bits"]
        cfg_width = meta["width"]
        pad_expr = "{" + high_to_low + "}"
        if cfg_width > pad_total:
            pad_expr = "{{" + str(cfg_width - pad_total) + "{1'b0}}, " + pad_expr + "}"
        lines.append(f"  wire [{cfg_width - 1}:0] cfg_{_pad_key(pad.name)} = {pad_expr};")
    lines.append("")

    active = _bist_active(pinmux)
    lines.append(f"  wire bist_active = {active};")
    lines.append("")

    for pad in pinmux.digital_pads():
        p = _pad_key(pad.name)
        normal_sel, normal_cells = _normal_candidates(pinmux, pad.name)
        bist_cells = _bist_candidates(pinmux, pad.name)
        conditions = []
        for idx, cell in enumerate(normal_cells):
            inst, pin, direction, width = _resolve(soc, cell)
            sig = _internal_signal(inst, pin)
            cond = f"c_{p}_n{idx}"
            lines.append(f"  wire {cond} = ~bist_active & ({normal_sel} == {idx});")
            conditions.append((cond, sig, direction, width))
        for idx, cell in enumerate(bist_cells):
            inst, pin, direction, width = _resolve(soc, cell)
            sig = _internal_signal(inst, pin)
            cond = f"c_{p}_b{idx}"
            lines.append(f"  wire {cond} = bist_active & (o_bist_mode_bist_mode == {idx});")
            conditions.append((cond, sig, direction, width))
        out_terms = [f"({cond} ? {sig} : 1'b0)" for cond, sig, direction, _ in conditions if direction == "out"]
        oe_terms = [cond for cond, _, direction, _ in conditions if direction == "out"]
        lines.append(f"  assign {p}_dout = " + (" | ".join(out_terms) if out_terms else "1'b0") + ";")
        lines.append(f"  assign {p}_oe = " + (" | ".join(oe_terms) if oe_terms else "1'b0") + ";")
        lines.append(f"  assign {p}_ie = ~{p}_oe;")
        for cond, sig, direction, width in conditions:
            if direction == "in":
                z = f"{width}'bz" if width > 1 else "1'bz"
                lines.append(f"  assign {sig} = {cond} ? {p}_din : {z};")
        lines.append("")

    lines.append(f"  {module}_regs u_regs (")
    conns = [
        ".pclk(pclk)", ".presetn(presetn)", ".paddr(paddr)", ".psel(psel)",
        ".penable(penable)", ".pwrite(pwrite)", ".pwdata(pwdata)", ".pstrb(pstrb)", ".prdata(prdata)",
        ".pready(pready)", ".pslverr(pslverr)", ".pprot(pprot)", ".err_irq(err_irq)",
    ]
    for reg in reg_map.registers:
        for field in reg.fields:
            sig = cfg_field_signal(reg.name, field.name)
            conns.append(f".{sig}({sig})")
    lines.append(",\n".join("    " + c for c in conns))
    lines.append("  );")
    lines.append("")

    for pad in pinmux.digital_pads():
        p = _pad_key(pad.name)
        meta = cfg_meta.get(pad.name)
        if not meta:
            continue
        lines.append(f"  pad_wrapper #(.CFG_W({meta['width']})) u_pad_{p} (")
        lines.append(f"    .pad(pad_{p}),")
        lines.append(f"    .data_i({p}_dout),")
        lines.append(f"    .data_o({p}_din),")
        lines.append(f"    .oe({p}_oe),")
        lines.append(f"    .ie({p}_ie),")
        lines.append(f"    .cfg(cfg_{p})")
        lines.append("  );")
        lines.append("")
    for pad in pinmux.pads:
        if pad.type == "analog":
            p = _pad_key(pad.name)
            lines.append(f"  ana_pad_wrapper u_pad_{p} (.pad(pad_{p}));")
    lines.append("")
    lines.append("endmodule")
    lines.append("")
    return "\n".join(lines)
