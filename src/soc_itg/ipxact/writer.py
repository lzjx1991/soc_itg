from pathlib import Path

from ..model import Component

_NS = "http://www.spiritconsortium.org/XMLSchema/SPIRIT/1685-2009"
_ACCESS = {"rw": "read-write", "ro": "read-only", "wo": "write-only", "rw1": "read-writeOnce", "w1": "writeOnce"}


def _esc(value):
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def write_component(component: Component):
    vendor, library, name, version = (component.vlnv.split(":") + ["", "", "", ""])[:4]
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', f'<spirit:component xmlns:spirit="{_NS}">']
    lines.append(f"  <spirit:vendor>{_esc(vendor)}</spirit:vendor>")
    lines.append(f"  <spirit:library>{_esc(library)}</spirit:library>")
    lines.append(f"  <spirit:name>{_esc(name)}</spirit:name>")
    lines.append(f"  <spirit:version>{_esc(version)}</spirit:version>")

    if component.ports:
        lines.append("  <spirit:model><spirit:ports>")
        for port in component.ports:
            vector = ""
            if port.width > 1:
                vector = f"<spirit:vector><spirit:left>{port.width - 1}</spirit:left><spirit:right>0</spirit:right></spirit:vector>"
            lines.append(f"    <spirit:port><spirit:name>{_esc(port.name)}</spirit:name><spirit:direction>{port.direction}</spirit:direction>{vector}</spirit:port>")
        lines.append("  </spirit:ports></spirit:model>")

    if component.bus_interfaces:
        lines.append("  <spirit:busInterfaces>")
        for bi in component.bus_interfaces:
            mode = "master" if bi.mode == "master" else "slave"
            lines.append("    <spirit:busInterface>")
            lines.append(f"      <spirit:name>{_esc(bi.name)}</spirit:name>")
            if bi.bus_type:
                lines.append(f'      <spirit:busType spirit:name="{_esc(bi.bus_type)}"/>')
            lines.append(f"      <spirit:{mode}/>")
            if bi.port_maps:
                lines.append("      <spirit:portMaps>")
                for logical, physical in bi.port_maps.items():
                    lines.append(
                        "        <spirit:portMap>"
                        f"<spirit:logicalPort><spirit:name>{_esc(logical)}</spirit:name></spirit:logicalPort>"
                        f"<spirit:physicalPort><spirit:name>{_esc(physical)}</spirit:name></spirit:physicalPort>"
                        "</spirit:portMap>")
                lines.append("      </spirit:portMaps>")
            lines.append("    </spirit:busInterface>")
        lines.append("  </spirit:busInterfaces>")

    if component.memory_maps:
        lines.append("  <spirit:memoryMaps>")
        for mm in component.memory_maps:
            lines.append("    <spirit:memoryMap>")
            lines.append(f"      <spirit:name>{_esc(mm.name)}</spirit:name>")
            lines.append("      <spirit:addressBlock>")
            lines.append(f"        <spirit:name>{_esc(mm.name)}_ab</spirit:name><spirit:baseAddress>0</spirit:baseAddress><spirit:range>4096</spirit:range><spirit:width>32</spirit:width>")
            for reg in mm.registers:
                lines.append("        <spirit:register>")
                lines.append(f"          <spirit:name>{_esc(reg.name)}</spirit:name><spirit:addressOffset>{reg.offset}</spirit:addressOffset><spirit:size>32</spirit:size>")
                for field in reg.fields:
                    access = _ACCESS.get(field.access, "read-write")
                    lines.append(
                        "          <spirit:field>"
                        f"<spirit:name>{_esc(field.name)}</spirit:name>"
                        f"<spirit:bitOffset>{field.lsb}</spirit:bitOffset>"
                        f"<spirit:bitWidth>{field.msb - field.lsb + 1}</spirit:bitWidth>"
                        f"<spirit:access>{access}</spirit:access>"
                        f"<spirit:reset><spirit:value>{field.reset}</spirit:value></spirit:reset>"
                        "</spirit:field>")
                lines.append("        </spirit:register>")
            lines.append("      </spirit:addressBlock>")
            lines.append("    </spirit:memoryMap>")
        lines.append("  </spirit:memoryMaps>")

    if component.file_sets:
        lines.append("  <spirit:fileSets>")
        for fs in component.file_sets:
            lines.append(f"    <spirit:fileSet><spirit:name>{_esc(fs.name)}</spirit:name>")
            for item in fs.files:
                ftype = item.file_type or "verilogSource"
                lines.append(f"      <spirit:file><spirit:name>{_esc(item.name)}</spirit:name><spirit:fileType>{_esc(ftype)}</spirit:fileType></spirit:file>")
            lines.append("    </spirit:fileSet>")
        lines.append("  </spirit:fileSets>")

    lines.append("</spirit:component>")
    return "\n".join(lines) + "\n"


def write_component_file(component: Component, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(write_component(component), encoding="utf-8")
    return path
