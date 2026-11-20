def generate_ral(soc):
    lines = []
    for inst, mem_maps in soc.register_models.items():
        for memory_map in mem_maps:
            for reg in memory_map.registers:
                class_name = f"{inst}_{reg.name}_reg"
                lines.append(f"class {class_name} extends uvm_reg;")
                lines.append(f"  `uvm_object_utils({class_name})")
                for field in reg.fields:
                    lines.append(f"  rand uvm_reg_field {field.name};")
                lines.append(f'  function new(string name = "{class_name}");')
                lines.append("    super.new(name, 32, UVM_NO_COVERAGE);")
                lines.append("  endfunction")
                lines.append("  virtual function void build();")
                for field in reg.fields:
                    width = field.msb - field.lsb + 1
                    lines.append(f'    {field.name} = uvm_reg_field::type_id::create("{field.name}");')
                    lines.append(f'    {field.name}.configure(this, {width}, {field.lsb}, "RW", 0, {field.reset}, 1, 1, 0);')
                lines.append("  endfunction")
                lines.append("endclass")
                lines.append("")
    return "\n".join(lines) + "\n"
