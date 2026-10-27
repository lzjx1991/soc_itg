from .model import Pinmux


def _finding(level, code, msg):
    return {"level": level, "code": code, "msg": msg}


def validate(pinmux: Pinmux):
    findings = []
    all_pads = {p.name for p in pinmux.pads}
    digital = {p.name for p in pinmux.digital_pads()}
    normal = {}
    for entry in pinmux.function_share:
        normal.setdefault(entry.pad, set()).add("function_share")
    for entry in pinmux.padshare:
        normal.setdefault(entry.pad, set()).add("padshare")

    for entry in pinmux.function_share + pinmux.padshare:
        if entry.pad not in all_pads:
            findings.append(_finding("error", "PAD_UNKNOWN", f"mode table references unknown pad '{entry.pad}'"))
        elif entry.pad not in digital:
            findings.append(_finding("error", "PAD_ANALOG_IN_MODE", f"analog pad '{entry.pad}' appears in a mode table"))

    for pad, modes in normal.items():
        if len(modes) > 1:
            findings.append(_finding("error", "PAD_MULTI_MODE", f"pad '{pad}' appears in both function_share and padshare"))

    bist_pads = {entry.pad for entry in pinmux.bist_share}
    for pad in digital:
        if pad not in normal:
            findings.append(_finding("error", "PAD_NO_MODE", f"digital pad '{pad}' has no normal mode"))
        if pad not in bist_pads:
            findings.append(_finding("warning", "PAD_NO_BIST", f"digital pad '{pad}' missing in bist_share"))

    for pad, count in _duplicates(pinmux.function_share).items():
        findings.append(_finding("error", "DUP_FUNCTION", f"pad '{pad}' duplicated in function_share"))
    for pad, count in _duplicates(pinmux.padshare).items():
        findings.append(_finding("error", "DUP_PADSHARE", f"pad '{pad}' duplicated in padshare"))
    for pad, count in _duplicates(pinmux.bist_share).items():
        findings.append(_finding("error", "DUP_BIST", f"pad '{pad}' duplicated in bist_share"))

    return findings


def _duplicates(entries):
    result = {}
    for entry in entries:
        result[entry.pad] = result.get(entry.pad, 0) + 1
    return {pad: count for pad, count in result.items() if count > 1}
