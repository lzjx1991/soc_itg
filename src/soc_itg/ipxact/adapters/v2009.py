import xml.etree.ElementTree as ET
from ...model import Component, Port, BusInterface, RegisterField, Register, MemoryMap


_ACCESS_MAP = {
    "read-write": "rw", "read-only": "ro", "write-only": "wo",
    "read-writeonce": "rw1", "writeonce": "w1",
    "rw": "rw", "ro": "ro", "wo": "wo",
}
_WRITE_MAP = {
    "onetoclear": "w1c", "onetoset": "w1s", "onetotoggle": "w1t",
    "zerotoclear": "w0c", "zerotoset": "w0s", "zerototoggle": "w0t",
    "clear": "clear", "set": "set", "modify": "modify",
}
_READ_MAP = {"clear": "rc", "set": "rs", "modify": "none"}


def _norm_access(value):
    return _ACCESS_MAP.get(str(value or "rw").strip().lower(), "rw")


def _norm_write(value):
    if value is None:
        return "none"
    return _WRITE_MAP.get(str(value).strip().lower(), "none")


def _norm_read(value):
    if value is None:
        return "none"
    return _READ_MAP.get(str(value).strip().lower(), "none")


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _child(elem, name):
    for c in list(elem):
        if _local(c.tag) == name:
            return c
    return None


def _children(elem, name):
    return [c for c in list(elem) if _local(c.tag) == name]


def _text(elem, name, default=None):
    c = _child(elem, name)
    if c is not None and c.text and c.text.strip():
        return c.text.strip()
    return default


def _attr(elem, name):
    for k, v in elem.attrib.items():
        if _local(k) == name:
            return v
    return None


def _vector_width(elem):
    vec = _child(elem, "vector")
    if vec is None:
        return 1
    left = _text(vec, "left")
    right = _text(vec, "right")
    if left is None or right is None:
        return 1
    return abs(int(left) - int(right)) + 1


def _parse_ports(root):
    model = _child(root, "model")
    if model is None:
        return []
    ports_el = _child(model, "ports")
    if ports_el is None:
        return []
    result = []
    for p in _children(ports_el, "port"):
        result.append(Port(name=_text(p, "name"), direction=_text(p, "direction", "in"), width=_vector_width(p)))
    return result


def _parse_bus_interfaces(root):
    bis_el = _child(root, "busInterfaces")
    if bis_el is None:
        return []
    result = []
    for bi in _children(bis_el, "busInterface"):
        mode = "slave"
        if _child(bi, "master") is not None:
            mode = "master"
        elif _child(bi, "system") is not None:
            mode = "system"
        bt = _child(bi, "busType")
        port_maps = {}
        pms = _child(bi, "portMaps")
        if pms is not None:
            for pm in _children(pms, "portMap"):
                lp = _child(pm, "logicalPort")
                pp = _child(pm, "physicalPort")
                logical = _text(lp, "name") if lp is not None else None
                physical = _text(pp, "name") if pp is not None else None
                if logical and physical:
                    port_maps[logical] = physical
        result.append(BusInterface(name=_text(bi, "name"), mode=mode, bus_type=_attr(bt, "name") if bt is not None else None, port_maps=port_maps))
    return result


def _parse_registers(address_block):
    result = []
    for rg in _children(address_block, "register"):
        offset = _text(rg, "addressOffset", "0")
        try:
            offset = hex(int(offset, 0))
        except ValueError:
            offset = "0x0"
        fields = []
        for fl in _children(rg, "field"):
            bit_offset = int(_text(fl, "bitOffset", "0"), 0)
            bit_width = int(_text(fl, "bitWidth", "1"), 0)
            reset = 0
            res = _child(fl, "reset")
            if res is not None:
                val = _text(res, "value")
                if val:
                    reset = int(val, 0)
            fields.append(RegisterField(
                name=_text(fl, "name"),
                msb=bit_offset + bit_width - 1,
                lsb=bit_offset,
                access=_norm_access(_text(fl, "access", "rw")),
                write_action=_norm_write(_text(fl, "modifiedWriteValue")),
                read_action=_norm_read(_text(fl, "readAction")),
                reset=reset,
            ))
        result.append(Register(name=_text(rg, "name"), offset=offset, fields=fields))
    return result


def _parse_memory_maps(root):
    mms_el = _child(root, "memoryMaps")
    if mms_el is None:
        return []
    result = []
    for mm in _children(mms_el, "memoryMap"):
        registers = []
        for ab in _children(mm, "addressBlock"):
            registers.extend(_parse_registers(ab))
        result.append(MemoryMap(name=_text(mm, "name"), registers=registers))
    return result


def parse(path):
    root = ET.parse(path).getroot()
    vlnv = ":".join([_text(root, "vendor", ""), _text(root, "library", ""), _text(root, "name", ""), _text(root, "version", "")])
    return Component(
        vlnv=vlnv,
        ports=_parse_ports(root),
        bus_interfaces=_parse_bus_interfaces(root),
        memory_maps=_parse_memory_maps(root),
    )
