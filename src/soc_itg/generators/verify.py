def generate_tb(netlist):
    top = netlist.top
    lines = ["`timescale 1ns/1ps", f"module tb_{top};"]
    for port in netlist.ports:
        kind = "wire" if port.direction in ("inout", "output") else "reg"
        rng = f"[{port.width - 1}:0] " if port.width > 1 else ""
        lines.append(f"  {kind} {rng}{port.name};")
    lines.append(f"  {top} u_dut (")
    conns = [f"    .{port.name}({port.name})" for port in netlist.ports]
    lines.append(",\n".join(conns))
    lines.append("  );")
    lines.append("  initial begin")
    lines.append(f'    $display("[tb] {top} started");')
    lines.append("    #1000;")
    lines.append("    $finish;")
    lines.append("  end")
    lines.append("endmodule")
    return "\n".join(lines) + "\n"
