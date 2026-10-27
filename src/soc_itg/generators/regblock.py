from ..model import MemoryMap


def _offset(reg):
    return int(reg.offset, 0)


def _reg_secure(reg):
    return any(f.security == "secure" for f in reg.fields)


def _width(field):
    return field.msb - field.lsb + 1


def _name(reg, field):
    return f"{reg.name.lower()}_{field.name.lower()}"


def _is_ro(field):
    return field.access == "ro"


def _is_write_once(field):
    return field.access in ("rw1", "w1")


def _declare(reg, field):
    width = _width(field)
    rng = f"[{width - 1}:0] " if width > 1 else ""
    if _is_ro(field):
        return f"  input  wire {rng}i_{_name(reg, field)}"
    return f"  output reg  {rng}o_{_name(reg, field)}"


def _write_mask(field):
    bits = []
    for i in range(_width(field) - 1, -1, -1):
        bits.append(f"pstrb[{(field.lsb + i) // 8}]")
    return "{" + ", ".join(bits) + "}" if _width(field) > 1 else bits[0]


def _new_value(reg, field):
    width = _width(field)
    base = f"o_{_name(reg, field)}"
    src = f"pwdata[{field.msb}:{field.lsb}]"
    action = field.write_action
    if action in ("none", "modify"):
        return src
    if action == "w1c":
        return f"({base} & ~{src})"
    if action == "w1s":
        return f"({base} | {src})"
    if action == "w1t":
        return f"({base} ^ {src})"
    if action == "w0c":
        return f"({base} & {src})"
    if action == "w0s":
        return f"({base} | ~{src})"
    if action == "w0t":
        return f"({base} ^ ~{src})"
    if action == "clear":
        return f"{width}'d0"
    if action == "set":
        return f"{width}'d{(1 << width) - 1}"
    return src


def _read_value(reg, field):
    if _is_ro(field):
        return f"i_{_name(reg, field)}"
    if field.access == "wo":
        return f"{_width(field)}'d0"
    return f"o_{_name(reg, field)}"


def generate_regblock(module_name, memory_map: MemoryMap, addr_width=8, data_width=32):
    regs = memory_map.registers
    pstrb_w = (data_width + 7) // 8
    ports = [
        "  input  wire pclk",
        "  input  wire presetn",
        f"  input  wire [{addr_width - 1}:0] paddr",
        "  input  wire psel",
        "  input  wire penable",
        "  input  wire pwrite",
        f"  input  wire [{data_width - 1}:0] pwdata",
        f"  input  wire [{pstrb_w - 1}:0] pstrb",
        f"  output reg  [{data_width - 1}:0] prdata",
        "  output wire pready",
        "  output reg  pslverr",
        "  input  wire [2:0] pprot",
        "  output reg  err_irq",
    ]
    for reg in regs:
        for field in reg.fields:
            ports.append(_declare(reg, field))

    lines = [f"module {module_name} (", ",\n".join(ports), ");", ""]
    lines.append("  assign pready = 1'b1;")
    lines.append("")
    for reg in regs:
        lines.append(f"  localparam integer OFF_{reg.name.upper()} = {_offset(reg)};")
    lines.append("")
    for reg in regs:
        r = reg.name.lower()
        lines.append(f"  wire wr_{r} = psel & penable & pwrite & (paddr == OFF_{reg.name.upper()});")
        lines.append(f"  wire rd_{r} = psel & penable & ~pwrite & (paddr == OFF_{reg.name.upper()});")
        lines.append(f"  wire sec_ok_{r} = " + ("~pprot[1];" if _reg_secure(reg) else "1'b1;"))
    lines.append("")

    for reg in regs:
        for field in reg.fields:
            if _is_ro(field):
                continue
            base = _name(reg, field)
            lines.append(f"  wire [{_width(field) - 1}:0] wmask_{base} = {_write_mask(field)};")
            if _is_write_once(field):
                lines.append(f"  reg done_{base};")
    lines.append("")

    lines.append("  always @(posedge pclk or negedge presetn) begin")
    lines.append("    if (!presetn) begin")
    for reg in regs:
        for field in reg.fields:
            if _is_ro(field):
                continue
            base = _name(reg, field)
            lines.append(f"      o_{base} <= {_width(field)}'d{field.reset};")
            if _is_write_once(field):
                lines.append(f"      done_{base} <= 1'b0;")
    lines.append("    end else begin")
    for reg in regs:
        writable = [f for f in reg.fields if not _is_ro(f)]
        r = reg.name.lower()
        if writable:
            lines.append(f"      if (wr_{r} & sec_ok_{r}) begin")
            for field in writable:
                base = _name(reg, field)
                expr = f"(o_{base} & ~wmask_{base}) | ({_new_value(reg, field)} & wmask_{base})"
                if _is_write_once(field):
                    lines.append(f"        if (~done_{base}) begin")
                    lines.append(f"          o_{base} <= {expr};")
                    lines.append(f"          done_{base} <= 1'b1;")
                    lines.append("        end")
                else:
                    lines.append(f"        o_{base} <= {expr};")
            lines.append("      end")
        read_fields = [f for f in reg.fields if not _is_ro(f) and f.read_action in ("rc", "rs")]
        if read_fields:
            lines.append(f"      if (rd_{r} & sec_ok_{r}) begin")
            for field in read_fields:
                base = _name(reg, field)
                width = _width(field)
                value = f"{width}'d0" if field.read_action == "rc" else f"{width}'d{(1 << width) - 1}"
                lines.append(f"        o_{base} <= {value};")
            lines.append("      end")
    lines.append("    end")
    lines.append("  end")
    lines.append("")

    lines.append("  always @(*) begin")
    lines.append(f"    prdata = {{{data_width}{{1'b0}}}};")
    lines.append("    pslverr = 1'b0;")
    lines.append("    case (paddr)")
    for reg in regs:
        secure_expr = "pprot[1]" if _reg_secure(reg) else "1'b0"
        lines.append(f"      OFF_{reg.name.upper()}: begin")
        lines.append(f"        if ({secure_expr}) begin")
        lines.append("          pslverr = 1'b1;")
        lines.append("        end else begin")
        for field in reg.fields:
            lines.append(f"          prdata[{field.msb}:{field.lsb}] = {_read_value(reg, field)};")
        lines.append("        end")
        lines.append("      end")
    lines.append("      default: begin")
    lines.append(f"        prdata = {{{data_width}{{1'b0}}}};")
    lines.append("      end")
    lines.append("    endcase")
    lines.append("  end")
    lines.append("")

    secure_regs = [r for r in regs if _reg_secure(r)]
    if secure_regs:
        terms = " | ".join(f"(paddr == OFF_{r.name.upper()})" for r in secure_regs)
        lines.append(f"  wire sec_violation = ({terms}) & pprot[1];")
    else:
        lines.append("  wire sec_violation = 1'b0;")
    lines.append("  always @(posedge pclk or negedge presetn) begin")
    lines.append("    if (!presetn) begin")
    lines.append("      err_irq <= 1'b0;")
    lines.append("    end else begin")
    lines.append("      err_irq <= psel & penable & ~pwrite & sec_violation;")
    lines.append("    end")
    lines.append("  end")
    lines.append("")
    lines.append("endmodule")
    lines.append("")
    return "\n".join(lines)
