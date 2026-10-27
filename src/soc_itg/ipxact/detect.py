import xml.etree.ElementTree as ET

_NAMESPACE_TO_VERSION = {
    "http://www.spiritconsortium.org/XMLSchema/SPIRIT/1.4": "spirit-1.4",
    "http://www.spiritconsortium.org/XMLSchema/SPIRIT/1.5": "spirit-1.5",
    "http://www.spiritconsortium.org/XMLSchema/SPIRIT/1685-2009": "ieee-1685-2009",
    "http://www.accellera.org/XMLSchema/IPXACT/1685-2014": "ieee-1685-2014",
    "http://www.accellera.org/XMLSchema/IPXACT/1685-2022": "ieee-1685-2022",
}


def namespace_of(path):
    root = ET.parse(path).getroot()
    tag = root.tag
    if tag.startswith("{"):
        return tag[1:].split("}", 1)[0]
    return ""


def detect_version(path):
    return _NAMESPACE_TO_VERSION.get(namespace_of(path), "unknown")
