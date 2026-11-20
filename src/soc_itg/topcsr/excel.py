import re
from pathlib import Path
import openpyxl
from ..model.ir import MemoryMap, Register, RegisterField
from ..model.topcsr import TopCSR, TopCSRBinding
from ..regtypes import resolve_type

_ACCESS = {
    "rw": "rw", "ro": "ro", "wo": "wo", "rw1": "rw1", "w1": "w1",
    "read-write": "rw", "read-only": "ro", "write-only": "wo",
    "read-writeonce": "rw1", "writeonce": "w1",
}
_WRITE = {
    "none": "none", "modify": "modify", "w1c": "w1c", "w1s": "w1s", "w1t": "w1t",
    "w0c": "w0c", "w0s": "w0s", "w0t": "w0t", "clear": "clear", "set": "set",
    "onetoclear": "w1c", "onetoset": "w1s", "onetotoggle": "w1t",
    "zerotoclear": "w0c", "zerotoset": "w0s", "zerototoggle": "w0t",
}
_READ = {"none": "none", "rc": "rc", "rs": "rs", "clear": "rc", "set": "rs", "modify": "none"}

_ALIASES = {
    "block": "block", "block_name": "block", "blockname": "block",
    "reg": "reg", "reg_name": "reg", "regname": "reg",
    "offset": "offset", "address": "offset",
    "field": "field", "field_name": "field",
    "msb": "msb", "lsb": "lsb",
    "access": "access",
    "type": "type",
    "write_action": "write_action", "modified_write_value": "write_action",
    "read_action": "read_action",
    "reset": "reset", "reset_value": "reset",
    "security": "security",
    "bind": "bind",
}


def _norm(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    return value


def _key(value):
    if value is None:
        return ""
    return re.sub(r"\s+", "_", str(value).strip().lower())


def _int(value, default=0):
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(str(value).strip(), 0)
    except ValueError:
        return default


def _header_map(header):
    mapping = {}
    for i, cell in enumerate(header):
        key = _ALIASES.get(_key(cell))
        if key and key not in mapping:
            mapping[key] = i
    return mapping


def _rows(worksheet):
    return [[_norm(c) for c in row] for row in worksheet.iter_rows(values_only=True)]


def _sheet(workbook):
    for title in workbook.sheetnames:
        if title.strip().lower() in ("registers", "register", "top_csr", "topcsr", "regs"):
            return workbook[title]
    return workbook[workbook.sheetnames[0]]


def read_topcsr(path, module="top_regs"):
    workbook = openpyxl.load_workbook(Path(path), data_only=True)
    rows = _rows(_sheet(workbook))
    if not rows:
        return TopCSR(module=module, memory_map=MemoryMap(name=module, registers=[]))
    hmap = _header_map(rows[0])

    def cell(row, key):
        i = hmap.get(key)
        return row[i] if i is not None and i < len(row) else None

    registers = []
    current = None
    bindings = []
    last_block = None
    for row in rows[1:]:
        block = cell(row, "block") or last_block
        last_block = block
        reg_name = cell(row, "reg")
        field_name = cell(row, "field")
        if not reg_name or not field_name:
            continue
        if current is None or current.name != str(reg_name):
            current = Register(name=str(reg_name), offset=hex(_int(cell(row, "offset"), 0)), fields=[])
            registers.append(current)
        msb = _int(cell(row, "msb"), 0)
        lsb = _int(cell(row, "lsb"), 0)
        type_value = cell(row, "type")
        if type_value is not None:
            access, write_action, read_action = resolve_type(type_value)
        else:
            access = _ACCESS.get(_key(cell(row, "access")), "rw")
            write_action = _WRITE.get(_key(cell(row, "write_action")), "none")
            read_action = _READ.get(_key(cell(row, "read_action")), "none")
        security = "secure" if _key(cell(row, "security")) == "secure" else "nonsecure"
        current.fields.append(RegisterField(
            name=str(field_name), msb=msb, lsb=lsb, access=access,
            write_action=write_action, read_action=read_action,
            reset=_int(cell(row, "reset"), 0), security=security,
        ))
        bind = cell(row, "bind")
        if bind:
            targets = [t.strip() for t in str(bind).split(",") if t.strip()]
            bindings.append(TopCSRBinding(reg=str(reg_name), field=str(field_name), access=access, width=msb - lsb + 1, targets=targets))

    return TopCSR(module=module, memory_map=MemoryMap(name=module, registers=registers), bindings=bindings)
