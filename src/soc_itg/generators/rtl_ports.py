import re

_MODULE = re.compile(r"\bmodule\s+(\w+)\s*(?:#\s*\([^;]*?\))?\s*\((.*?)\)\s*;", re.S)
_PORT = re.compile(r"\b(input|output|inout)\b\s*(?:wire|reg|logic)?\s*(?:\[([^\]]+)\])?\s*([A-Za-z_]\w*)")


def _width(range_text):
    if not range_text:
        return 1
    parts = range_text.split(":")
    if len(parts) != 2:
        return 1
    try:
        return abs(int(parts[0].strip()) - int(parts[1].strip())) + 1
    except ValueError:
        return 1


def extract_ports(text, module=None):
    match = _MODULE.search(text)
    if match is None:
        return None, []
    name = match.group(1)
    if module and name != module:
        return name, []
    ports = []
    for pm in _PORT.finditer(match.group(2)):
        ports.append({"name": pm.group(3), "direction": pm.group(1), "width": _width(pm.group(2))})
    return name, ports
