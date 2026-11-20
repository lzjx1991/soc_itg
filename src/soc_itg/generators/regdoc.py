def generate_regdoc(soc):
    lines = [f"# Register map: {soc.top}", ""]
    for inst, mem_maps in soc.register_models.items():
        for memory_map in mem_maps:
            for reg in memory_map.registers:
                lines.append(f"## {inst}.{reg.name} @ {reg.offset}")
                lines.append("")
                lines.append("| field | bits | access | reset |")
                lines.append("|---|---|---|---|")
                for field in reg.fields:
                    lines.append(f"| {field.name} | {field.msb}:{field.lsb} | {field.access} | {field.reset} |")
                lines.append("")
    return "\n".join(lines)
