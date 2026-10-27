from .detect import detect_version
from .adapters import v2009

_PARSERS = {
    "ieee-1685-2009": v2009.parse,
}


def read_component(path):
    version = detect_version(path)
    parser = _PARSERS.get(version)
    if parser is None:
        raise NotImplementedError(f"unsupported IP-XACT version '{version}' for {path}")
    return parser(path)
