from ..model import MemoryMap, Register, RegisterField
from .model import Pinmux


def _bits_for(count):
    if count <= 1:
        return 1
    return (count - 1).bit_length()


def _san(name):
    return "".join(c.lower() if c.isalnum() else "_" for c in name)


def build_registers(pinmux: Pinmux):
    registers = []
    cfg_meta = {}
    offset = 0

    def add(reg_name, fields):
        nonlocal offset
        registers.append(Register(name=reg_name, offset=hex(offset), fields=fields))
        offset += 4

    for pad in pinmux.digital_pads():
        fields = []
        lsb = 0
        field_meta = []
        for fname, cf in pad.config.items():
            fields.append(RegisterField(name=fname, msb=lsb + cf.width - 1, lsb=lsb, access="rw", reset=cf.default, security=pad.security))
            field_meta.append((fname, cf.width))
            lsb += cf.width
        if not fields:
            fields.append(RegisterField(name="cfg", msb=0, lsb=0, access="rw", reset=0, security=pad.security))
            field_meta.append(("cfg", 1))
            lsb = 1
        cfg_width = 8 if lsb <= 8 else 16
        reg_name = f"cfg_{pad.name}"
        add(reg_name, fields)
        cfg_meta[pad.name] = {"reg": reg_name, "fields": field_meta, "bits": lsb, "width": cfg_width}

    groups = {}
    for entry in pinmux.function_share:
        groups.setdefault(entry.group, []).append(entry)
    for group, entries in groups.items():
        width = _bits_for(max((len(e.functions) for e in entries), default=1))
        secure = any((pinmux.pad(e.pad) is not None and pinmux.pad(e.pad).security == "secure") for e in entries)
        add(f"sel_{group}", [RegisterField(name="sel", msb=width - 1, lsb=0, access="rw", reset=0, security="secure" if secure else "nonsecure")])

    for entry in pinmux.padshare:
        width = _bits_for(len(entry.pins) or 1)
        pad = pinmux.pad(entry.pad)
        secure = pad.security if pad is not None else "nonsecure"
        add(f"sel_{entry.pad}", [RegisterField(name="sel", msb=width - 1, lsb=0, access="rw", reset=0, security=secure)])

    modes = sorted({e.bist_mode for e in pinmux.bist_entries}) or [0]
    width = _bits_for(len(modes))
    add("bist_mode", [RegisterField(name="bist_mode", msb=width - 1, lsb=0, access="rw", reset=0)])

    return MemoryMap(name="pinmux_regs", registers=registers), cfg_meta


def sel_signal(group_or_pad, kind):
    return f"o_{_san('sel_' + group_or_pad)}_sel"


def cfg_field_signal(reg_name, field_name):
    return f"o_{_san(reg_name)}_{_san(field_name)}"
