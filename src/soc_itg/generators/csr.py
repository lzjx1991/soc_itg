from ..model import SoC


def generate_csr_header(soc: SoC):
    guard = f"{soc.top.upper()}_CSR_H"
    lines = [f"#ifndef {guard}", f"#define {guard}", ""]
    for inst_name, memory_maps in soc.register_models.items():
        prefix = inst_name.upper()
        for mem_map in memory_maps:
            for reg in mem_map.registers:
                reg_macro = f"{prefix}_{reg.name.upper()}"
                lines.append(f"#define {reg_macro}_OFFSET {reg.offset}u")
                if any(f.security == "secure" for f in reg.fields):
                    lines.append(f"#define {reg_macro}_SECURE 1")
                for field in reg.fields:
                    width = field.msb - field.lsb + 1
                    mask = ((1 << width) - 1) << field.lsb
                    lines.append(f"#define {reg_macro}_{field.name.upper()}_MSK 0x{mask:x}u")
                    lines.append(f"#define {reg_macro}_{field.name.upper()}_POS {field.lsb}u")
                lines.append("")
    lines.append("#endif")
    lines.append("")
    return "\n".join(lines)
